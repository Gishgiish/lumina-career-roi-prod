# src/transformation/gold.py
"""
Gold layer transformation: Silver -> Gold.

Reads clean Parquet from Silver, calculates business aggregates
(Data Marts), and writes to Gold.

Data marts:
  1. single_skill_roi_mart — ROI per individual skill
  2. skill_overlap_mart — ROI for skill combinations
  3. market_overview_mart — broad market stats
  4. skill_related_mart — related skills via co-occurrence
"""
import logging

import polars as pl

from src.utils.paths import GOLD_DIR, SILVER_DIR

logger = logging.getLogger(__name__)


def transform_silver_to_gold() -> bool:
    """Build Gold data marts from Silver Parquet."""
    print("🥇 Starting Gold Transformation...")

    silver_path = SILVER_DIR / "jobs_silver.parquet"
    if not silver_path.exists():
        print("   -> No Silver data found. Skipping Gold transformation.")
        return False

    df_silver = pl.read_parquet(silver_path)

    # The expected salary column is now expected_salary_usd
    salary_col = "expected_salary_usd" if "expected_salary_usd" in df_silver.columns else "expected_salary"

    # ==========================================
    # Data Mart 1: Single Skill ROI Mart
    # ==========================================
    print("   -> Building Single Skill ROI Mart...")

    overall_avg_salary = df_silver.select(pl.col(salary_col).mean()).item()
    print(f"      -> Overall Market Average Salary: ${overall_avg_salary:,.2f}")

    df_exploded = df_silver.explode("skills_list", empty_as_null=True)

    df_skill_mart = (
        df_exploded
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

    gold_skill_path = GOLD_DIR / "single_skill_roi_mart.parquet"
    df_skill_mart.write_parquet(gold_skill_path)
    print(f"      -> Saved Single Skill ROI Mart: {len(df_skill_mart)} skills")

    # ==========================================
    # Data Mart 2: Skill Overlap Mart (combos)
    # ==========================================
    print("   -> Building Skill Overlap Mart...")

    df_overlap = (
        df_silver
        .filter(pl.col("skills_list").list.len() >= 2)
        .with_columns(
            pl.col("skills_list").list.sort().list.join(", ").alias("skill_combo")
        )
        .group_by("skill_combo")
        .agg(
            pl.col(salary_col).mean().alias("combo_avg_salary"),
            pl.col("external_id").count().alias("combo_demand_count"),
        )
        .with_columns(
            (pl.col("combo_avg_salary") - overall_avg_salary).alias("combo_premium")
        )
        .sort("combo_premium", descending=True)
    )

    gold_overlap_path = GOLD_DIR / "skill_overlap_mart.parquet"
    df_overlap.write_parquet(gold_overlap_path)
    print(f"      -> Saved Skill Overlap Mart: {len(df_overlap)} combos")

    # ==========================================
    # Data Mart 3: Market Overview Mart
    # ==========================================
    print("   -> Building Market Overview Mart...")

    df_market = pl.DataFrame({
        "metric": [
            "total_jobs",
            "total_unique_skills",
            "average_salary_usd",
            "median_salary_usd",
            "top_source_count",
        ],
        "value": [
            len(df_silver),
            df_skill_mart.height,
            round(overall_avg_salary, 2),
            round(df_silver.select(pl.col(salary_col).median()).item(), 2),
            df_silver.select(pl.col("source").n_unique()).item(),
        ],
    })

    # Top skills by demand
    top_skills = (
        df_skill_mart
        .sort("job_demand_count", descending=True)
        .head(10)
        .select(["skill", "avg_salary", "job_demand_count", "salary_premium"])
    )

    gold_market_path = GOLD_DIR / "market_overview_mart.parquet"
    df_market.write_parquet(gold_market_path)

    gold_top_skills_path = GOLD_DIR / "top_skills_mart.parquet"
    top_skills.write_parquet(gold_top_skills_path)
    print("      -> Saved Market Overview + Top Skills marts")

    # ==========================================
    # Data Mart 4: Skill Related Mart (co-occurrence)
    # ==========================================
    print("   -> Building Skill Related Mart...")

    # For each skill, find skills that co-occur in the same job
    # Simple approach: explode, self-join on job id, count pairs
    df_exploded = df_silver.explode("skills_list", empty_as_null=True)

    df_related = (
        df_exploded
        .rename({"skills_list": "skill_a"})
        .join(
            df_exploded.select(["external_id", "skills_list"]).rename({"skills_list": "skill_b"}),
            on="external_id",
            how="inner",
        )
        .filter(pl.col("skill_a") != pl.col("skill_b"))
        .group_by(["skill_a", "skill_b"])
        .agg(
            pl.len().alias("co_occurrence_count"),
        )
        .sort("co_occurrence_count", descending=True)
        .filter(pl.col("co_occurrence_count") >= 2)
    )

    gold_related_path = GOLD_DIR / "skill_related_mart.parquet"
    df_related.write_parquet(gold_related_path)
    print(f"      -> Saved Skill Related Mart: {len(df_related)} pairs")

    # ==========================================
    # Data Mart 5: Salary Distribution Mart
    # ==========================================
    print("   -> Building Salary Distribution Mart...")

    # Build salary buckets per skill for histogram rendering
    df_exploded = df_silver.explode("skills_list", empty_as_null=True)

    df_salary_dist = (
        df_exploded
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
        .group_by(["skills_list", "salary_bucket"])
        .agg(
            pl.len().alias("job_count"),
        )
        .rename({"skills_list": "skill"})
        .sort(["skill", "salary_bucket"])
    )

    gold_salary_path = GOLD_DIR / "salary_distribution_mart.parquet"
    df_salary_dist.write_parquet(gold_salary_path)
    print(f"      -> Saved Salary Distribution Mart: {len(df_salary_dist)} buckets")

    print("\n   -> Single Skill Gold Data Preview:")
    print(df_skill_mart.head(5))

    print("\n✅ Gold Transformation Completed Successfully!\n")
    return True


if __name__ == "__main__":
    transform_silver_to_gold()