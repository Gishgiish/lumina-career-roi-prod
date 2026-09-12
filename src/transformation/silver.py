# src/transformation/silver.py
"""
Silver layer transformation: Bronze -> Silver.

Reads raw NDJSON batches from Bronze (one file per source per run),
normalizes strings, extracts skills using the taxonomy, deduplicates
across sources, calculates expected salary, and writes optimized
Parquet to Silver.
"""
import logging

import polars as pl

from src.ingestion.skills_taxonomy import extract_skills
from src.transformation.dedup import deduplicate_jobs
from src.utils.paths import BRONZE_DIR, SILVER_DIR

logger = logging.getLogger(__name__)


def _extract_skills_list(tags: list[str], description: str) -> list[str]:
    """Extract canonical skills from tags + description."""
    return extract_skills(description, extra_terms=tags)


def transform_bronze_to_silver() -> bool:
    """
    Reads parsed NDJSON from Bronze, normalizes strings, parses skills into
    lists, calculates the expected salary midpoint, deduplicates, and writes
    optimized Parquet to Silver.

    :returns: True if data was processed, False if Bronze was empty.
    """
    print("🥈 Starting Silver Transformation...")

    # Read all Bronze NDJSON files (one per source per run)
    bronze_files = list(BRONZE_DIR.glob("jobs_raw_*.json"))
    if not bronze_files:
        print("   -> No Bronze data found. Skipping Silver transformation.")
        return False

    print(f"   -> Found {len(bronze_files)} Bronze file(s)")

    # Read and concatenate all batches
    frames = [pl.read_ndjson(f) for f in bronze_files]
    df_bronze = pl.concat(frames, how="vertical_relaxed")

    if df_bronze.is_empty():
        print("   -> Bronze data is empty. Skipping Silver transformation.")
        return False

    # --- Deduplicate across sources (keep highest-trust record) ---
    print(f"   -> Deduplicating {len(df_bronze)} records...")
    df_deduped = deduplicate_jobs(df_bronze)
    print(f"      -> After dedup: {len(df_deduped)} unique records")

    # --- Transform ---
    df_silver = (
        df_deduped
        .with_columns([
            # 1. Calculate expected salary (midpoint of min/max USD)
            pl.when(
                pl.col("min_salary_usd").is_not_null()
                & pl.col("max_salary_usd").is_not_null()
            )
            .then((pl.col("min_salary_usd") + pl.col("max_salary_usd")) / 2)
            .otherwise(pl.col("min_salary_usd"))
            .alias("expected_salary_usd"),

            # 2. Standardize job titles (Title Case for readability)
            pl.col("title")
                .str.to_lowercase()
                .str.strip_chars()
                .str.to_titlecase(),

            # 3. Standardize locations (lowercase for grouping later)
            pl.col("location")
                .fill_null("")
                .str.to_lowercase()
                .str.strip_chars(),

            # 4. Extract skills from tags + description
            pl.struct(["tags", "description"])
                .map_elements(
                    lambda row: _extract_skills_list(row["tags"] or [], row["description"] or ""),
                    return_dtype=pl.List(pl.Utf8),
                )
                .alias("skills_list"),
        ])
        # Keep non-null expected salary rows — we can't compute ROI without it
        .filter(pl.col("expected_salary_usd").is_not_null())
    )

    # Save as Parquet (optimized for Silver/Gold)
    silver_path = SILVER_DIR / "jobs_silver.parquet"
    df_silver.write_parquet(silver_path)
    print(f"   -> Saved {len(df_silver)} cleaned records to {silver_path}\n")

    # Quick schema preview
    print("   -> Silver Schema Preview:")
    print(df_silver.schema)

    return True