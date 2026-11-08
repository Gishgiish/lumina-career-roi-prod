# src/transformation/gold.py
"""
Gold layer transformation: Silver -> Gold.

Reads clean Parquet from Silver, calculates business aggregates
(Data Marts), and writes to Gold.

Data marts:
  1. single_skill_roi_mart — ROI per individual skill (salaried jobs)
  2. skill_demand_mart — demand per skill across all jobs (incl. salary-less)
  3. skill_overlap_mart — ROI for complete skill sets (salaried jobs)
  4. market_overview_mart — broad market stats and salary coverage
  5. top_skills_mart — top skills by salaried demand
  6. skill_related_mart — related skills via co-occurrence (all jobs)
  7. salary_distribution_mart — per-skill salary histograms (salaried jobs)

The builders are pure (DataFrame in, DataFrame out); `build_gold_marts`
is the only writer. Both the pipeline and the seed script use this module.

Gold marts rank technical skills only. Soft skills remain in Silver, so a
soft-inclusive view can be rebuilt without re-ingesting.
"""
import logging
from pathlib import Path

import polars as pl

from src.ingestion.skills_taxonomy import TECHNICAL_SKILLS
from src.utils.paths import GOLD_DIR, SILVER_DIR

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ("external_id", "skills_list", "source")
SALARY_COLUMNS = ("expected_salary_usd", "expected_salary")

# Sorted once so ``list.eval`` membership checks are deterministic.
_TECHNICAL_LIST = sorted(TECHNICAL_SKILLS)

# Integer ordering for salary buckets. Labels are the user-facing strings; the
# integer lets the mart and the API return buckets in numeric order instead of
# lexicographic order ("$100k" sorting before "$75k").
SALARY_BUCKET_ORDER = {
    "< $50k": 0,
    "$50k - $75k": 1,
    "$75k - $100k": 2,
    "$100k - $125k": 3,
    "$125k - $150k": 4,
    "$150k - $200k": 5,
    "$200k+": 6,
}


def _clean_skills(df_silver: pl.DataFrame) -> pl.DataFrame:
    """Drop null/empty skill entries and jobs with no usable skills.

    Without this, ``explode`` turns an empty list into a null skill row, which
    then reaches Gold and breaks the API's ``skill.lower()`` lookups.
    """
    return (
        df_silver.with_columns(
            pl.col("skills_list")
            .cast(pl.List(pl.Utf8))
            .list.eval(pl.element().str.strip_chars())
            .list.eval(pl.element().filter(pl.element().str.len_chars() > 0))
            .alias("skills_list")
        )
        .filter(
            pl.col("skills_list").is_not_null()
            & (pl.col("skills_list").list.len() > 0)
        )
    )


def _technical_only(df_silver: pl.DataFrame) -> pl.DataFrame:
    """Keep only technical skills and drop jobs left without any.

    Soft skills stay in Silver; the default Gold marts rank technical demand
    only. Call after :func:`_clean_skills` so null/empty entries are gone.
    Order inside ``skills_list`` is preserved.
    """
    return (
        df_silver.with_columns(
            pl.col("skills_list")
            .list.eval(pl.element().filter(pl.element().is_in(_TECHNICAL_LIST)))
            .alias("skills_list")
        )
        .filter(pl.col("skills_list").list.len() > 0)
    )


def _explode_skills(df_silver: pl.DataFrame) -> pl.DataFrame:
    """Clean, keep technical skills, and explode ``skills_list``."""
    return _technical_only(_clean_skills(df_silver)).explode(
        "skills_list", empty_as_null=False
    )



def _require_columns(df: pl.DataFrame, columns: tuple[str, ...]) -> None:
    """Raise a clear error when a required Silver column is missing."""
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(
            f"Silver data is missing required columns: {', '.join(missing)}"
        )


def _resolve_salary_column(df: pl.DataFrame) -> str:
    """Return the salary column, preferring the USD-normalized one."""
    for column in SALARY_COLUMNS:
        if column in df.columns:
            return column
    raise ValueError(
        "Silver data is missing a salary column: expected one of "
        f"{', '.join(SALARY_COLUMNS)}"
    )


def _overall_average(df_silver: pl.DataFrame, salary_col: str) -> float | None:
    """Mean salary, or ``None`` when no row carries a salary."""
    return df_silver.select(pl.col(salary_col).mean()).item()


def _salary_rows(df_silver: pl.DataFrame, salary_col: str) -> pl.DataFrame:
    """Rows usable for salary metrics (salary-less rows are demand-only)."""
    return df_silver.filter(pl.col(salary_col).is_not_null())


def _count_unique_skills(df_silver: pl.DataFrame) -> int:
    """Count distinct technical skills across jobs with usable skills.

    Uses every job, not just salaried ones, so skills that only appear in
    salary-less postings are not dropped from the market totals. Soft skills
    are excluded so "tracked skills" matches the default marts.
    """
    df_all = _technical_only(_clean_skills(df_silver))
    if df_all.is_empty():
        return 0
    return int(
        df_all.select(
            pl.col("skills_list").explode(empty_as_null=False).n_unique()
        ).item()
    )


def build_single_skill_roi(
    df_silver: pl.DataFrame,
    salary_col: str | None = None,
    overall_avg_salary: float | None = None,
) -> pl.DataFrame:
    """ROI metrics per individual technical skill, using salaried jobs only."""
    salary_col = salary_col or _resolve_salary_column(df_silver)
    df_paid = _salary_rows(df_silver, salary_col)
    if overall_avg_salary is None:
        overall_avg_salary = _overall_average(df_paid, salary_col)

    return (
        _explode_skills(df_paid)
        .group_by("skills_list")
        .agg(
            pl.col(salary_col).mean().alias("avg_salary"),
            pl.col("external_id").count().alias("job_demand_count"),
        )
        .with_columns(
            (pl.col("avg_salary") - overall_avg_salary).alias("salary_premium")
        )
        .rename({"skills_list": "skill"})
        .sort("salary_premium", descending=True)
    )


def build_skill_overlap(
    df_silver: pl.DataFrame,
    salary_col: str | None = None,
    overall_avg_salary: float | None = None,
) -> pl.DataFrame:
    """ROI metrics for the complete technical skill set of each job (2+ skills).

    ``skill_combo`` is the job's full sorted technical skill set, not a
    pairwise combination; ``combo_size`` makes the set size explicit. A job
    with four technical skills produces one four-skill combo, not six pairs.
    Jobs left with fewer than two technical skills are excluded.
    """
    salary_col = salary_col or _resolve_salary_column(df_silver)
    df_paid = _salary_rows(df_silver, salary_col)
    if overall_avg_salary is None:
        overall_avg_salary = _overall_average(df_paid, salary_col)

    return (
        _technical_only(_clean_skills(df_paid))
        .filter(pl.col("skills_list").list.len() >= 2)
        .with_columns(
            pl.col("skills_list").list.len().alias("combo_size"),
            pl.col("skills_list").list.sort().list.join(", ").alias("skill_combo"),
        )
        .group_by("skill_combo")
        .agg(
            pl.col(salary_col).mean().alias("combo_avg_salary"),
            pl.col("external_id").count().alias("combo_demand_count"),
            pl.col("combo_size").first().alias("combo_size"),
        )
        .with_columns(
            (pl.col("combo_avg_salary") - overall_avg_salary).alias("combo_premium")
        )
        .sort(
            ["combo_premium", "combo_demand_count", "skill_combo"],
            descending=[True, True, False],
        )
    )


def build_market_overview(
    df_silver: pl.DataFrame,
    salary_col: str | None = None,
    overall_avg_salary: float | None = None,
) -> pl.DataFrame:
    """Broad market statistics as metric/value rows.

    Headcount metrics count every job in Silver. Salary metrics use only jobs
    with a salary; ``salary_coverage_rate`` makes the resulting coverage gap
    explicit instead of silently dropping rows. ``total_unique_skills`` counts
    technical skills across all jobs, including salary-less postings.
    """
    salary_col = salary_col or _resolve_salary_column(df_silver)
    df_paid = _salary_rows(df_silver, salary_col)
    if overall_avg_salary is None:
        overall_avg_salary = _overall_average(df_paid, salary_col)

    total_jobs = float(len(df_silver))
    paid_jobs = float(len(df_paid))
    average_salary = round(float(overall_avg_salary), 2) if overall_avg_salary is not None else 0.0
    median_salary_raw = df_paid.select(pl.col(salary_col).median()).item() if df_paid.height else None
    median_salary = round(float(median_salary_raw), 2) if median_salary_raw is not None else 0.0
    coverage_rate = round(paid_jobs / total_jobs, 4) if total_jobs else 0.0

    return pl.DataFrame({
        "metric": [
            "total_jobs",
            "jobs_with_salary",
            "salary_coverage_rate",
            "total_unique_skills",
            "average_salary_usd",
            "median_salary_usd",
            "top_source_count",
        ],
        "value": [
            total_jobs,
            paid_jobs,
            coverage_rate,
            float(_count_unique_skills(df_silver)),
            average_salary,
            median_salary,
            float(df_silver.select(pl.col("source").n_unique()).item()),
        ],
    })


def build_top_skills(skill_mart: pl.DataFrame) -> pl.DataFrame:
    """Top 10 skills by job demand."""
    return (
        skill_mart
        .sort("job_demand_count", descending=True)
        .head(10)
        .select(["skill", "avg_salary", "job_demand_count", "salary_premium"])
    )


def build_skill_demand(df_silver: pl.DataFrame) -> pl.DataFrame:
    """Per-skill demand across ALL jobs, including salary-less postings.

    ``job_share`` is the fraction of jobs with at least one technical skill
    that mention the skill. The salary-based ``single_skill_roi_mart``
    intentionally covers only jobs with a salary; this mart is the unbiased
    technical-demand view.
    """
    df_all = _technical_only(_clean_skills(df_silver))
    if df_all.is_empty():
        return pl.DataFrame(
            schema={
                "skill": pl.Utf8,
                "job_demand_count": pl.Int64,
                "job_share": pl.Float64,
            }
        )

    total_jobs = df_all.height
    return (
        df_all
        .explode("skills_list", empty_as_null=False)
        .group_by("skills_list")
        .agg(pl.col("external_id").count().alias("job_demand_count"))
        .rename({"skills_list": "skill"})
        .with_columns(
            (pl.col("job_demand_count") / total_jobs).alias("job_share")
        )
        .sort(["job_demand_count", "skill"], descending=[True, False])
    )


def build_skill_related(df_silver: pl.DataFrame) -> pl.DataFrame:
    """Co-occurring technical skill pairs, keeping pairs seen in 2+ jobs.

    Pairs are canonicalized so ``skill_a < skill_b`` and each unordered pair is
    emitted once. The count is the number of distinct jobs containing the pair,
    not the number of mirrored join rows.
    """
    df_exploded = _explode_skills(df_silver)

    return (
        df_exploded
        .rename({"skills_list": "skill_a"})
        .join(
            df_exploded.select(["source", "external_id", "skills_list"]).rename({"skills_list": "skill_b"}),
            on=["source", "external_id"],
            how="inner",
        )
        .filter(pl.col("skill_a") != pl.col("skill_b"))
        .with_columns(
            pl.when(pl.col("skill_a") < pl.col("skill_b"))
            .then(pl.col("skill_a"))
            .otherwise(pl.col("skill_b"))
            .alias("skill_a"),
            pl.when(pl.col("skill_a") < pl.col("skill_b"))
            .then(pl.col("skill_b"))
            .otherwise(pl.col("skill_a"))
            .alias("skill_b"),
        )
        .group_by(["skill_a", "skill_b"])
        .agg(
            pl.struct(["source", "external_id"]).n_unique().alias("co_occurrence_count"),
        )
        .filter(pl.col("co_occurrence_count") >= 2)
        .sort(
            ["co_occurrence_count", "skill_a", "skill_b"],
            descending=[True, False, False],
        )
    )


def build_salary_distribution(
    df_silver: pl.DataFrame,
    salary_col: str | None = None,
) -> pl.DataFrame:
    """Per-skill salary bucket counts for technical-skill histograms.

    Salary-less jobs are excluded: a null salary would otherwise fall through
    the ``when`` chain into the highest bucket.
    """
    salary_col = salary_col or _resolve_salary_column(df_silver)
    df_paid = _salary_rows(df_silver, salary_col)

    return (
        _explode_skills(df_paid)
        .with_columns(
            pl.when(pl.col(salary_col) < 50_000).then(pl.lit("< $50k"))
            .when(pl.col(salary_col) < 75_000).then(pl.lit("$50k - $75k"))
            .when(pl.col(salary_col) < 100_000).then(pl.lit("$75k - $100k"))
            .when(pl.col(salary_col) < 125_000).then(pl.lit("$100k - $125k"))
            .when(pl.col(salary_col) < 150_000).then(pl.lit("$125k - $150k"))
            .when(pl.col(salary_col) < 200_000).then(pl.lit("$150k - $200k"))
            .otherwise(pl.lit("$200k+"))
            .alias("salary_bucket")
        )
        .with_columns(
            pl.col("salary_bucket")
            .replace_strict(SALARY_BUCKET_ORDER, return_dtype=pl.Int64)
            .alias("bucket_order")
        )
        .group_by(["skills_list", "salary_bucket", "bucket_order"])
        .agg(
            pl.len().alias("job_count"),
        )
        .rename({"skills_list": "skill"})
        .sort(["skill", "bucket_order"])
    )


def build_gold_marts(
    df_silver: pl.DataFrame,
    gold_dir: Path,
) -> dict[str, pl.DataFrame]:
    """Build every Gold mart from Silver and write them to ``gold_dir``.

    :returns: Mapping of mart name (without extension) to DataFrame.
    """
    _require_columns(df_silver, REQUIRED_COLUMNS)
    salary_col = _resolve_salary_column(df_silver)
    gold_dir = Path(gold_dir)
    gold_dir.mkdir(parents=True, exist_ok=True)

    df_paid = _salary_rows(df_silver, salary_col)
    overall_avg_salary = _overall_average(df_paid, salary_col)

    print("   -> Building Single Skill ROI Mart...")
    if overall_avg_salary is None:
        print("      -> No salaried jobs; salary ROI metrics will be empty")
    else:
        print(f"      -> Overall Market Average Salary: ${overall_avg_salary:,.2f}")
    df_skill_mart = build_single_skill_roi(
        df_silver, salary_col, overall_avg_salary
    )
    df_skill_mart.write_parquet(gold_dir / "single_skill_roi_mart.parquet")
    print(f"      -> Saved Single Skill ROI Mart: {len(df_skill_mart)} skills")

    print("   -> Building Skill Demand Mart...")
    df_demand = build_skill_demand(df_silver)
    df_demand.write_parquet(gold_dir / "skill_demand_mart.parquet")
    print(f"      -> Saved Skill Demand Mart: {len(df_demand)} skills")

    print("   -> Building Skill Overlap Mart...")
    df_overlap = build_skill_overlap(df_silver, salary_col, overall_avg_salary)
    df_overlap.write_parquet(gold_dir / "skill_overlap_mart.parquet")
    print(f"      -> Saved Skill Overlap Mart: {len(df_overlap)} combos")

    print("   -> Building Market Overview Mart...")
    df_market = build_market_overview(df_silver, salary_col, overall_avg_salary)
    df_market.write_parquet(gold_dir / "market_overview_mart.parquet")

    top_skills = build_top_skills(df_skill_mart)
    top_skills.write_parquet(gold_dir / "top_skills_mart.parquet")
    print("      -> Saved Market Overview + Top Skills marts")

    print("   -> Building Skill Related Mart...")
    df_related = build_skill_related(df_silver)
    df_related.write_parquet(gold_dir / "skill_related_mart.parquet")
    print(f"      -> Saved Skill Related Mart: {len(df_related)} pairs")

    print("   -> Building Salary Distribution Mart...")
    df_salary_dist = build_salary_distribution(df_silver, salary_col)
    df_salary_dist.write_parquet(gold_dir / "salary_distribution_mart.parquet")
    print(f"      -> Saved Salary Distribution Mart: {len(df_salary_dist)} buckets")

    return {
        "single_skill_roi_mart": df_skill_mart,
        "skill_demand_mart": df_demand,
        "skill_overlap_mart": df_overlap,
        "market_overview_mart": df_market,
        "top_skills_mart": top_skills,
        "skill_related_mart": df_related,
        "salary_distribution_mart": df_salary_dist,
    }


def transform_silver_to_gold() -> bool:
    """Build Gold data marts from Silver Parquet."""
    print("🥇 Starting Gold Transformation...")

    silver_path = SILVER_DIR / "jobs_silver.parquet"
    if not silver_path.exists():
        print("   -> No Silver data found. Skipping Gold transformation.")
        return False

    df_silver = pl.read_parquet(silver_path)
    marts = build_gold_marts(df_silver, GOLD_DIR)

    print("\n   -> Single Skill Gold Data Preview:")
    print(marts["single_skill_roi_mart"].head(5))

    print("\n✅ Gold Transformation Completed Successfully!\n")
    return True


if __name__ == "__main__":
    transform_silver_to_gold()
