"""Subprocess smoke test for the seed script."""

import os
import subprocess
import sys

import polars as pl

from src.utils.paths import PROJECT_ROOT

MART_NAMES = [
    "single_skill_roi_mart",
    "skill_demand_mart",
    "skill_overlap_mart",
    "market_overview_mart",
    "top_skills_mart",
    "skill_related_mart",
    "salary_distribution_mart",
]


def _run_seed(data_dir):
    env = os.environ.copy()
    env["LUMINA_DATA_DIR"] = str(data_dir)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return subprocess.run(
        [sys.executable, "scripts/seed_data.py"],
        env=env,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        check=False,
    )


def test_seed_writes_valid_marts(tmp_path):
    result = _run_seed(tmp_path)
    assert result.returncode == 0, result.stderr

    gold_dir = tmp_path / "gold"
    for name in MART_NAMES:
        assert (gold_dir / f"{name}.parquet").is_file(), name

    assert (tmp_path / "silver" / "jobs_silver.parquet").is_file()

    market = pl.read_parquet(gold_dir / "market_overview_mart.parquet")
    assert market["metric"].to_list() == [
        "total_jobs",
        "jobs_with_salary",
        "salary_coverage_rate",
        "total_unique_skills",
        "average_salary_usd",
        "median_salary_usd",
        "top_source_count",
    ]

    silver = pl.read_parquet(tmp_path / "silver" / "jobs_silver.parquet")
    assert "has_salary" in silver.columns
    assert not silver["has_salary"].all()  # seed exercises the salary-less path
    assert silver["expected_salary_usd"].null_count() > 0

    demand = pl.read_parquet(gold_dir / "skill_demand_mart.parquet")
    assert demand.columns == ["skill", "job_demand_count", "job_share"]
    assert demand["job_demand_count"].is_sorted(descending=True)

    related = pl.read_parquet(gold_dir / "skill_related_mart.parquet")
    assert (related["skill_a"] != related["skill_b"]).all()
    assert (related["co_occurrence_count"] >= 2).all()

    top = pl.read_parquet(gold_dir / "top_skills_mart.parquet")
    assert top.height == 10
    assert top.columns == [
        "skill",
        "avg_salary",
        "job_demand_count",
        "salary_premium",
    ]

    allowed_buckets = {
        "< $50k",
        "$50k - $75k",
        "$75k - $100k",
        "$100k - $125k",
        "$125k - $150k",
        "$150k - $200k",
        "$200k+",
    }
    distribution = pl.read_parquet(gold_dir / "salary_distribution_mart.parquet")
    assert set(distribution["salary_bucket"].to_list()) <= allowed_buckets
