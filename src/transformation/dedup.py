# src/transformation/dedup.py
"""
Deduplication engine for multi-source job data.

Uses a hybrid strategy:
  1. Exact match on canonical fields (normalized title + company + location)
  2. Fuzzy match using rapidfuzz on title/company for near-duplicates
  3. Trust-based conflict resolution — higher-trust source wins

Trust ranking (higher = more reliable):
  Adzuna: 5, USAJobs: 5, RemoteOK: 5, Remotive: 4,
  Greenhouse: 4, Lever: 4, HackerNews: 4, Arbeitnow: 3
"""
import logging
import re

import polars as pl
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Two records are duplicates if normalized title similarity is above this
FUZZY_THRESHOLD = 88

# Trust ranking per source
TRUST_RANK = {
    "usajobs": 5,
    "adzuna": 5,
    "remoteok": 5,
    "remotive": 4,
    "greenhouse": 4,
    "lever": 4,
    "hackernews": 4,
    "arbeitnow": 3,
}


def _normalize_title(title: str) -> str:
    """Normalize a job title for matching."""
    if not title:
        return ""
    title = title.lower().strip()
    # Remove noise tokens and parentheticals
    title = re.sub(r"(remote|onsite|hybrid|contract|full.?time|part.?time)", "", title)
    title = re.sub(r"\([^)]*\)", "", title)
    title = re.sub(r"\[[^\]]*\]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _normalize_text(value: str | None) -> str:
    """Lowercase and collapse whitespace for company/location comparison."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).lower().strip())


def _company_key(row: dict, company_col: str) -> str:
    return _normalize_text(row.get(company_col))


def _location_key(row: dict, location_col: str, country_col: str) -> str:
    """Prefer the specific location; fall back to country only when it is absent."""
    return _normalize_text(row.get(location_col)) or _normalize_text(row.get(country_col))


def _canonical_key(
    row: dict,
    title_col: str = "title",
    company_col: str = "company",
    location_col: str = "location",
    country_col: str = "country",
) -> tuple[str, str, str]:
    """Build a canonical dedup key: normalized title + company + location."""
    title = _normalize_title(row.get(title_col) or "")
    company = _company_key(row, company_col)
    location = _location_key(row, location_col, country_col)
    return title, company, location


# Columns that describe which record won, not the job itself; never merge them.
_NON_MERGE_COLUMNS = frozenset({"source", "external_id", "trust_rank", "__lumina_dedup_order"})

# Internal ordering column used for a deterministic tie-break.
_ORDER_COLUMN = "__lumina_dedup_order"


def _is_missing(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _merge_missing(target: dict, duplicate: dict) -> None:
    """Fill missing fields on the kept row from a lower-trust duplicate.

    Existing values always win; this only fills gaps (for example a salary that
    the higher-trust record did not publish).
    """
    for column, value in duplicate.items():
        if column in _NON_MERGE_COLUMNS or not _is_missing(target.get(column)):
            continue
        if not _is_missing(value):
            target[column] = value


def deduplicate_jobs(
    df: pl.DataFrame,
    source_col: str = "source",
    title_col: str = "title",
    company_col: str = "company",
    location_col: str = "location",
    country_col: str = "country",
) -> pl.DataFrame:
    """
    Deduplicate a DataFrame of jobs using exact + fuzzy matching.

    :param df: Jobs DataFrame to deduplicate
    :returns: Deduplicated DataFrame
    """
    if df.is_empty():
        return df

    # Add trust rank and a stable input-order column for deterministic ties.
    df = df.with_columns(
        pl.col(source_col)
        .cast(pl.Utf8)
        .map_elements(
            lambda s: TRUST_RANK.get(s, 0),
            return_dtype=pl.Int64,
        )
        .alias("trust_rank"),
        pl.int_range(0, pl.len()).alias(_ORDER_COLUMN),
    )

    # Highest trust first; ties break on source, then external_id, then input
    # order. This makes the surviving record reproducible across runs.
    sort_columns = ["trust_rank"]
    sort_descending = [True]
    for column in (source_col, "external_id"):
        if column in df.columns:
            sort_columns.append(column)
            sort_descending.append(False)
    sort_columns.append(_ORDER_COLUMN)
    sort_descending.append(False)
    df = df.sort(sort_columns, descending=sort_descending, nulls_last=True)

    rows = df.to_dicts()
    seen_exact: dict[tuple[str, str, str], dict] = {}
    seen_fuzzy: list[dict] = []
    unique_rows: list[dict] = []
    merged_count = 0

    for row in rows:
        key = _canonical_key(row, title_col, company_col, location_col, country_col)
        title, company, location = key

        # 1. Exact match on the full normalized key.
        if key in seen_exact:
            _merge_missing(seen_exact[key], row)
            merged_count += 1
            continue

        # 2. Fuzzy match against accepted rows. Require BOTH company and
        #    location to agree: a shared location alone wrongly merged distinct
        #    employers, and a shared company alone wrongly merged different
        #    cities. Missing company/location is not enough evidence either.
        matched = None
        if title and company and location:
            for accepted in seen_fuzzy:
                accepted_title = _normalize_title(accepted.get(title_col) or "")
                if not accepted_title:
                    continue
                if fuzz.ratio(title, accepted_title) < FUZZY_THRESHOLD:
                    continue

                accepted_company = _company_key(accepted, company_col)
                accepted_location = _location_key(accepted, location_col, country_col)
                if company == accepted_company and location == accepted_location:
                    matched = accepted
                    break

        if matched is not None:
            _merge_missing(matched, row)
            # Future exact duplicates of this row should merge into the kept one.
            seen_exact.setdefault(key, matched)
            merged_count += 1
            continue

        # Accept the row
        seen_exact[key] = row
        seen_fuzzy.append(row)
        unique_rows.append(row)

    result = pl.DataFrame(unique_rows)
    # Always remove the temporary columns.
    drop_columns = [c for c in ("trust_rank", _ORDER_COLUMN) if c in result.columns]
    if drop_columns:
        result = result.drop(drop_columns)

    logger.info(
        "Dedup: %d rows -> %d unique (%d duplicate rows merged)",
        df.height,
        len(unique_rows),
        merged_count,
    )
    return result
