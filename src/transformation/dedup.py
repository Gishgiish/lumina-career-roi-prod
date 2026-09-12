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


def _canonical_key(row: dict) -> str:
    """Build a canonical dedup key: normalized title + company + location."""
    title = _normalize_title(row.get("title") or "")
    company = (row.get("company") or "").lower().strip()
    location = (row.get("country") or row.get("location") or "").lower().strip()
    return f"{title}|{company}|{location}"


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

    # Add trust rank column for sorting
    df = df.with_columns(
        pl.col(source_col)
        .cast(pl.Utf8)
        .map_elements(
            lambda s: TRUST_RANK.get(s, 0),
            return_dtype=pl.Int64,
        )
        .alias("trust_rank")
    )

    df = df.sort("trust_rank", descending=True)

    rows = df.to_dicts()
    seen_exact: set[str] = set()
    seen_fuzzy: list[dict] = []
    unique_rows: list[dict] = []

    for row in rows:
        key = _canonical_key(row)
        lower_title = _normalize_title(row.get(title_col) or "")

        # 1. Exact match
        if key in seen_exact:
            continue

        # 2. Fuzzy match against accepted rows
        is_duplicate = False
        for accepted in seen_fuzzy:
            accepted_title = _normalize_title(accepted.get(title_col) or "")
            if not lower_title or not accepted_title:
                continue

            similarity = fuzz.ratio(lower_title, accepted_title)
            if similarity >= FUZZY_THRESHOLD:
                same_company = (
                    (row.get(company_col) or "").lower().strip()
                    == (accepted.get(company_col) or "").lower().strip()
                    and (row.get(company_col) or "").strip() != ""
                )
                same_location = (
                    (row.get(location_col) or row.get(country_col) or "").lower().strip()
                    == (accepted.get(location_col) or accepted.get(country_col) or "").lower().strip()
                    and (row.get(location_col) or row.get(country_col) or "").strip() != ""
                )
                if same_company or same_location:
                    is_duplicate = True
                    break

        if is_duplicate:
            continue

        # Accept the row
        seen_exact.add(key)
        seen_fuzzy.append(row)
        unique_rows.append(row)

    result = pl.DataFrame(unique_rows)
    # Always remove the temporary trust_rank column
    if "trust_rank" in result.columns:
        result = result.drop("trust_rank")

    logger.info("Dedup: %d rows -> %d unique", df.height, len(unique_rows))
    return result