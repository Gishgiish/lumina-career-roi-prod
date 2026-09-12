# src/utils/api_data_loader.py
"""
Data loader for the API layer.

Loads Gold layer parquet marts and returns them as JSON-serializable
Python dicts. Used by the FastAPI endpoints.
"""
import logging

import polars as pl

from src.utils.paths import GOLD_DIR

logger = logging.getLogger(__name__)


def _read_gold_mart(filename: str) -> pl.DataFrame | None:
    """Read a Gold parquet mart, or None if it doesn't exist."""
    path = GOLD_DIR / filename
    if not path.exists():
        return None
    return pl.read_parquet(path)


def get_single_skill_roi_data() -> list[dict]:
    """All skills with ROI metrics, sorted by salary premium descending."""
    df = _read_gold_mart("single_skill_roi_mart.parquet")
    if df is None:
        raise FileNotFoundError("Gold layer Single Skill ROI Mart not found. Run the pipeline first.")
    df = df.sort("salary_premium", descending=True)
    return _records_with_rounded_floats(df)


def get_skill_by_name(skill_name: str) -> dict | None:
    """Fetch a specific skill's ROI data (case-insensitive)."""
    all_data = get_single_skill_roi_data()
    for item in all_data:
        if item["skill"].lower() == skill_name.lower():
            return item
    return None


def get_skill_overlap_data(limit: int | None = None) -> list[dict]:
    """Skill combos with combined ROI, sorted by premium."""
    df = _read_gold_mart("skill_overlap_mart.parquet")
    if df is None:
        raise FileNotFoundError("Gold layer Skill Overlap Mart not found.")
    df = df.sort("combo_premium", descending=True)
    if limit:
        df = df.head(limit)
    return _records_with_rounded_floats(df)


def compare_skills(skills: list[str]) -> list[dict]:
    """Return ROI data for a specific list of skills."""
    all_data = get_single_skill_roi_data()
    lower_names = {s.lower() for s in skills}
    return [item for item in all_data if item["skill"].lower() in lower_names]


def get_related_skills(skill_name: str, limit: int = 10) -> list[dict]:
    """Get related skills for a skill based on co-occurrence."""
    df = _read_gold_mart("skill_related_mart.parquet")
    if df is None:
        return []

    df = df.filter(
        (pl.col("skill_a").str.to_lowercase() == skill_name.lower())
        | (pl.col("skill_b").str.to_lowercase() == skill_name.lower())
    )
    related = []
    for row in df.iter_rows(named=True):
        if row["skill_a"].lower() == skill_name.lower():
            related.append({"skill": row["skill_b"], "co_occurrence_count": row["co_occurrence_count"]})
        else:
            related.append({"skill": row["skill_a"], "co_occurrence_count": row["co_occurrence_count"]})
    related.sort(key=lambda x: x["co_occurrence_count"], reverse=True)
    return related[:limit]


def get_market_overview() -> dict:
    """Market-level statistics."""
    df = _read_gold_mart("market_overview_mart.parquet")
    top = _read_gold_mart("top_skills_mart.parquet")
    if df is None:
        raise FileNotFoundError("Gold layer Market Overview Mart not found.")
    metrics = {row["metric"]: row["value"] for row in df.iter_rows(named=True)}
    top_skills = top.to_dicts() if top is not None else []
    return {"metrics": metrics, "top_skills": top_skills}


def get_salary_distribution(skill_name: str | None = None) -> list[dict]:
    """Salary buckets either globally or for a specific skill."""
    df = _read_gold_mart("salary_distribution_mart.parquet")
    if df is None:
        return []
    if skill_name:
        df = df.filter(pl.col("skill").str.to_lowercase() == skill_name.lower())
    return df.to_dicts()


def get_skills_list() -> list[str]:
    """Get all available skill names for autocomplete."""
    data = get_single_skill_roi_data()
    return [item["skill"] for item in data]


def _records_with_rounded_floats(df: pl.DataFrame) -> list[dict]:
    """Convert a DataFrame to dicts with floats rounded to 2 decimals."""
    records = []
    for row in df.iter_rows(named=True):
        record = {}
        for key, value in row.items():
            if isinstance(value, float):
                record[key] = round(value, 2)
            else:
                record[key] = value
        records.append(record)
    return records