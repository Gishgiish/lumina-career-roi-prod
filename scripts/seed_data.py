# scripts/seed_data.py
"""
Generates realistic seed data for the Silver/Gold layers so the product
works out-of-the-box without needing to run live API ingestion.

Run:  uv run python scripts/seed_data.py
"""
import random
from datetime import UTC, datetime, timedelta

import polars as pl

from src.utils.paths import GOLD_DIR, SILVER_DIR, ensure_directories

# Compact seed skill data: (avg_salary, popularity_weight)
SEED_SKILLS = {
    "Python": (128_000, 95), "JavaScript": (115_000, 92), "TypeScript": (125_000, 85),
    "Java": (118_000, 80), "Go": (135_000, 60), "Rust": (145_000, 42),
    "C++": (122_000, 55), "C#": (108_000, 50), "SQL": (105_000, 78),
    "Bash": (98_000, 45), "React": (120_000, 88), "Vue.js": (108_000, 40),
    "Angular": (112_000, 38), "Svelte": (119_000, 20), "Tailwind CSS": (113_000, 45),
    "Django": (122_000, 35), "Flask": (115_000, 25), "FastAPI": (127_000, 30),
    "Express.js": (110_000, 42), "NestJS": (121_000, 28), "Spring Boot": (115_000, 30),
    "GraphQL": (128_000, 48), "REST APIs": (112_000, 70), "Microservices": (135_000, 65),
    "AWS": (135_000, 90), "Azure": (128_000, 55), "Google Cloud": (130_000, 45),
    "Docker": (122_000, 85), "Kubernetes": (140_000, 75), "Terraform": (138_000, 60),
    "CI/CD": (125_000, 65), "GitHub Actions": (126_000, 50), "Linux": (112_000, 55),
    "Monitoring": (132_000, 35), "PostgreSQL": (118_000, 70), "MySQL": (105_000, 50),
    "MongoDB": (112_000, 55), "Redis": (118_000, 40), "DynamoDB": (125_000, 35),
    "Elasticsearch": (122_000, 25), "Pinecone": (138_000, 18),
    "Pandas": (118_000, 50), "NumPy": (117_000, 42), "Polars": (125_000, 22),
    "Apache Spark": (132_000, 45), "Apache Kafka": (135_000, 40),
    "Apache Airflow": (128_000, 30), "Snowflake": (140_000, 42),
    "Databricks": (138_000, 30), "BigQuery": (130_000, 28), "dbt": (132_000, 25),
    "Tableau": (105_000, 35), "Power BI": (102_000, 32), "ETL": (120_000, 40),
    "Data Warehousing": (125_000, 30),
    "Machine Learning": (140_000, 60), "Deep Learning": (145_000, 40),
    "PyTorch": (145_000, 45), "TensorFlow": (135_000, 35),
    "Scikit-learn": (125_000, 30), "LangChain": (150_000, 25),
    "OpenAI": (155_000, 22), "Hugging Face": (147_000, 20),
    "RAG": (152_000, 28), "Natural Language Processing": (140_000, 25),
    "Computer Vision": (142_000, 22), "Large Language Models": (156_000, 35),
    "MLOps": (148_000, 30), "Prompt Engineering": (145_000, 20),
    "AI Agents": (155_000, 25),
    "React Native": (118_000, 35), "Flutter": (120_000, 28),
    "Swift": (125_000, 20), "Kotlin": (122_000, 22),
    "Android Development": (115_000, 25), "iOS Development": (128_000, 22),
    "Git": (110_000, 75), "System Design": (142_000, 40),
    "Cybersecurity": (135_000, 35), "DevSecOps": (140_000, 25),
    "Agile": (115_000, 55), "Product Management": (140_000, 30),
}

JOB_TITLES = [
    "Senior Software Engineer", "Software Engineer", "Backend Engineer",
    "Frontend Engineer", "Full Stack Engineer", "Data Engineer",
    "Machine Learning Engineer", "DevOps Engineer", "Site Reliability Engineer",
    "Data Scientist", "Platform Engineer", "Cloud Engineer",
    "Security Engineer", "Mobile Engineer", "QA Engineer",
    "AI Engineer", "ML Ops Engineer", "Engineering Manager", "Staff Engineer",
]

SOURCES = ["remoteok", "remotive", "greenhouse", "lever", "hackernews", "arbeitnow"]
COMPANIES = [
    "TechCorp", "CloudWorks", "DataSphere", "AIVenture", "WebFlow Labs",
    "NeuralNine", "DevBridge", "OpenSpace", "KuberKit", "Pyramid Systems",
    "InnovateIO", "CloudNova", "SkillsFirst", "Quantify", "ByteWorks",
]
COUNTRIES = ["US", "US", "US", "GB", "DE", "CA", "IN", "AU", "NL", "FR"]
LOCATIONS = [
    "San Francisco, CA", "New York, NY", "Austin, TX", "Seattle, WA",
    "London, UK", "Berlin, Germany", "Toronto, Canada", "Remote",
    "Bangalore, India", "Amsterdam, Netherlands", "Paris, France",
    "Remote (US)", "Remote (Europe)", "Chicago, IL", "Boston, MA",
]


def generate_seed_jobs(num_jobs: int = 800) -> pl.DataFrame:
    """Generate realistic job postings from the seed skill data."""
    random.seed(42)
    now = datetime.now(UTC)
    rows = []
    skill_names = list(SEED_SKILLS.keys())
    weights = [SEED_SKILLS[s][1] for s in skill_names]

    for i in range(num_jobs):
        num_skills = random.randint(2, 4)
        job_skills = random.choices(skill_names, weights=weights, k=num_skills)
        primary = job_skills[0]
        base_salary = SEED_SKILLS[primary][0]
        avg_salary = base_salary * random.uniform(0.90, 1.15)
        min_salary = avg_salary * random.uniform(0.85, 0.95)
        max_salary = avg_salary * random.uniform(1.05, 1.20)

        title = random.choice(JOB_TITLES)
        company = random.choice(COMPANIES)
        source = random.choice(SOURCES)
        country = random.choice(COUNTRIES)
        location = random.choice(LOCATIONS)

        desc = (
            f"{title} at {company}. We are looking for a skilled engineer with "
            f"experience in {', '.join(job_skills)}. "
            "You will be working on exciting projects."
        )
        posted_at = (now - timedelta(days=random.randint(0, 30))).isoformat()

        rows.append({
            "external_id": f"seed_{i}",
            "source": source,
            "title": title,
            "description": desc,
            "location": location,
            "country": country,
            "min_salary_usd": round(min_salary, 2),
            "max_salary_usd": round(max_salary, 2),
            "expected_salary_usd": round(avg_salary, 2),
            "salary_currency": "USD",
            "salary_type": "annual",
            "posted_at": posted_at,
            "url": f"https://example.com/jobs/seed_{i}",
            "company": company,
            "tags": job_skills[:3],
            "skills_list": job_skills,
        })

    return pl.DataFrame(rows)


def generate_seed_gold(silver_df: pl.DataFrame) -> None:
    """Build Gold marts directly from the seed Silver data."""
    ensure_directories()

    salary_col = "expected_salary_usd"
    overall_avg = silver_df.select(pl.col(salary_col).mean()).item()
    df_exploded = silver_df.explode("skills_list", empty_as_null=True)

    # Skill ROI Mart
    df_skill = (
        df_exploded
        .group_by("skills_list")
        .agg(
            pl.col(salary_col).mean().alias("avg_salary"),
            pl.col("external_id").count().alias("job_demand_count"),
        )
        .with_columns((pl.col("avg_salary") - overall_avg).alias("salary_premium"))
        .rename({"skills_list": "skill"})
        .sort("salary_premium", descending=True)
    )
    df_skill.write_parquet(GOLD_DIR / "single_skill_roi_mart.parquet")

    # Overlap Mart
    df_overlap = (
        silver_df
        .filter(pl.col("skills_list").list.len() >= 2)
        .with_columns(
            pl.col("skills_list").list.sort().list.join(", ").alias("skill_combo")
        )
        .group_by("skill_combo")
        .agg(
            pl.col(salary_col).mean().alias("combo_avg_salary"),
            pl.col("external_id").count().alias("combo_demand_count"),
        )
        .with_columns((pl.col("combo_avg_salary") - overall_avg).alias("combo_premium"))
        .sort("combo_premium", descending=True)
    )
    df_overlap.write_parquet(GOLD_DIR / "skill_overlap_mart.parquet")

    # Market overview (all values as float to avoid mixed-type issues)
    df_market = pl.DataFrame({
        "metric": ["total_jobs", "total_unique_skills", "average_salary_usd", "median_salary_usd"],
        "value": [
            float(len(silver_df)),
            float(df_skill.height),
            round(float(overall_avg), 2),
            round(float(silver_df.select(pl.col(salary_col).median()).item()), 2),
        ],
    })
    df_market.write_parquet(GOLD_DIR / "market_overview_mart.parquet")

    # Top skills by demand
    df_skill.sort("job_demand_count", descending=True).head(10) \
        .write_parquet(GOLD_DIR / "top_skills_mart.parquet")

    # Related skills (co-occurrence)
    df_related = (
        df_exploded.rename({"skills_list": "skill_a"})
        .join(
            df_exploded.select(["external_id", "skills_list"]).rename({"skills_list": "skill_b"}),
            on="external_id",
            how="inner",
        )
        .filter(pl.col("skill_a") != pl.col("skill_b"))
        .group_by(["skill_a", "skill_b"])
        .agg(pl.len().alias("co_occurrence_count"))
        .sort("co_occurrence_count", descending=True)
    )
    df_related.write_parquet(GOLD_DIR / "skill_related_mart.parquet")

    # Salary distribution
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
        .agg(pl.len().alias("job_count"))
        .rename({"skills_list": "skill"})
        .sort(["skill", "salary_bucket"])
    )
    df_salary_dist.write_parquet(GOLD_DIR / "salary_distribution_mart.parquet")


def main():
    print("🌱 Generating seed data...")
    ensure_directories()

    silver_df = generate_seed_jobs(800)
    SILVER_DIR.mkdir(parents=True, exist_ok=True)
    silver_df.write_parquet(SILVER_DIR / "jobs_silver.parquet")
    print(f"   -> Saved {len(silver_df)} seed jobs to Silver")

    generate_seed_gold(silver_df)
    print("   -> Saved all Gold data marts")

    print("\n✅ Seed data generation complete!")
    print("   Start the API: `uv run uvicorn main:app --reload`")


if __name__ == "__main__":
    main()