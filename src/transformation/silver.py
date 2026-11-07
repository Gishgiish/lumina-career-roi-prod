# src/transformation/silver.py
"""
Silver layer transformation: Bronze -> Silver.

Reads raw NDJSON batches from Bronze (one file per source per run),
normalizes strings, extracts skills using the taxonomy, deduplicates
across sources, calculates expected salary, and writes optimized
Parquet to Silver.

Salary-less jobs are retained (``has_salary = False``) so demand statistics
cover the whole market; salary-based Gold marts filter them out.
"""
import logging
import re

import polars as pl

from src.ingestion.skills_taxonomy import extract_skills
from src.transformation.dedup import deduplicate_jobs
from src.utils.paths import BRONZE_DIR, SILVER_DIR

logger = logging.getLogger(__name__)

# Acronyms and product names that title-casing would otherwise mangle
# ("AWS" -> "Aws", "DevOps" -> "Devops", "iOS" -> "Ios").
TITLE_ACRONYMS = {
    "ai": "AI",
    "api": "API",
    "aws": "AWS",
    "bi": "BI",
    "cd": "CD",
    "ci": "CI",
    "css": "CSS",
    "csv": "CSV",
    "devops": "DevOps",
    "etl": "ETL",
    "gcp": "GCP",
    "github": "GitHub",
    "gitlab": "GitLab",
    "html": "HTML",
    "http": "HTTP",
    "https": "HTTPS",
    "ios": "iOS",
    "javascript": "JavaScript",
    "json": "JSON",
    "llm": "LLM",
    "ml": "ML",
    "nlp": "NLP",
    "qa": "QA",
    "saas": "SaaS",
    "sdk": "SDK",
    "sql": "SQL",
    "sre": "SRE",
    "typescript": "TypeScript",
    "ui": "UI",
    "ux": "UX",
    "xml": "XML",
    "yaml": "YAML",
}


def _standardize_title(title_col: str = "title") -> pl.Expr:
    """Title-case a job title while preserving known acronyms and product names."""
    expr = (
        pl.col(title_col)
        .str.to_lowercase()
        .str.strip_chars()
        .str.to_titlecase()
    )
    for token, replacement in TITLE_ACRONYMS.items():
        expr = expr.str.replace_all(rf"\b{re.escape(token.title())}\b", replacement)
    return expr


def _extract_skills_list(tags: list[str], description: str) -> list[str]:
    """Extract canonical skills from tags + description."""
    return extract_skills(description, extra_terms=tags)


def _add_salary_metrics(df: pl.DataFrame) -> pl.DataFrame:
    """Add ``expected_salary_usd`` (or null) and a ``has_salary`` flag.

    Salary-less jobs are deliberately kept in Silver for demand statistics;
    the salary-based Gold marts filter on ``has_salary``.
    """
    return (
        df.with_columns(
            pl.when(
                pl.col("min_salary_usd").is_not_null()
                & pl.col("max_salary_usd").is_not_null()
            )
            .then((pl.col("min_salary_usd") + pl.col("max_salary_usd")) / 2)
            .when(pl.col("min_salary_usd").is_not_null())
            .then(pl.col("min_salary_usd"))
            .otherwise(pl.col("max_salary_usd"))
            .alias("expected_salary_usd")
        )
        .with_columns(
            pl.col("expected_salary_usd").is_not_null().alias("has_salary")
        )
    )


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
        _add_salary_metrics(df_deduped)
        .with_columns([
            # 1. Standardize job titles (Title Case, preserving acronyms)
            _standardize_title(),

            # 2. Standardize locations (lowercase for grouping later)
            pl.col("location")
                .fill_null("")
                .str.to_lowercase()
                .str.strip_chars(),

            # 3. Extract skills from tags + description
            pl.struct(["tags", "description"])
                .map_elements(
                    lambda row: _extract_skills_list(row["tags"] or [], row["description"] or ""),
                    return_dtype=pl.List(pl.Utf8),
                )
                .alias("skills_list"),
        ])
    )

    # Salary-less jobs are kept for demand statistics. Log the coverage
    # explicitly so the bias in salary-based marts is visible.
    total_jobs = df_silver.height
    jobs_with_salary = int(df_silver["has_salary"].sum())
    jobs_without_salary = total_jobs - jobs_with_salary
    coverage = (jobs_with_salary / total_jobs * 100) if total_jobs else 0.0
    print(
        f"   -> Salary coverage: {jobs_with_salary}/{total_jobs} jobs "
        f"({coverage:.1f}%); {jobs_without_salary} kept for demand statistics"
    )

    # Save as Parquet (optimized for Silver/Gold)
    silver_path = SILVER_DIR / "jobs_silver.parquet"
    df_silver.write_parquet(silver_path)
    print(f"   -> Saved {len(df_silver)} cleaned records to {silver_path}\n")

    # Quick schema preview
    print("   -> Silver Schema Preview:")
    print(df_silver.schema)

    return True
