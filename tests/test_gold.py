"""Tests for the Gold-layer builders."""

import polars as pl
import pytest

from src.transformation.gold import (
    build_gold_marts,
    build_market_overview,
    build_salary_distribution,
    build_single_skill_roi,
    build_skill_demand,
    build_skill_overlap,
    build_skill_related,
    build_top_skills,
)


@pytest.fixture
def silver():
    return pl.DataFrame({
        "source": ["a", "a", "b", "b", "b"],
        "external_id": ["1", "2", "3", "4", "5"],
        "skills_list": [
            ["Python", "SQL"],
            ["Python", "SQL"],
            ["Python"],
            ["Go", "Rust"],
            ["Go"],
        ],
        "expected_salary_usd": [100_000.0, 120_000.0, 140_000.0, 160_000.0, 90_000.0],
    })


def _rows_by(df: pl.DataFrame, key: str) -> dict:
    return {row[key]: row for row in df.to_dicts()}


@pytest.fixture
def silver_with_soft():
    return pl.DataFrame({
        "source": ["a", "a", "b", "b", "b"],
        "external_id": ["1", "2", "3", "4", "5"],
        "skills_list": [
            ["Python", "SQL", "Communication"],
            ["Python", "SQL", "Communication"],
            ["Python", "Mentoring"],
            ["Go", "Rust"],
            ["Recruiting"],
        ],
        "expected_salary_usd": [100_000.0, 120_000.0, 140_000.0, 160_000.0, 90_000.0],
    })


class TestSingleSkillRoi:
    def test_metrics(self, silver):
        result = build_single_skill_roi(silver)
        rows = _rows_by(result, "skill")

        assert set(rows) == {"Python", "SQL", "Go", "Rust"}

        python = rows["Python"]
        assert python["avg_salary"] == pytest.approx(120_000.0)
        assert python["job_demand_count"] == 3
        assert python["salary_premium"] == pytest.approx(-2_000.0)

        sql = rows["SQL"]
        assert sql["avg_salary"] == pytest.approx(110_000.0)
        assert sql["job_demand_count"] == 2
        assert sql["salary_premium"] == pytest.approx(-12_000.0)

        go = rows["Go"]
        assert go["avg_salary"] == pytest.approx(125_000.0)
        assert go["job_demand_count"] == 2
        assert go["salary_premium"] == pytest.approx(3_000.0)

        rust = rows["Rust"]
        assert rust["avg_salary"] == pytest.approx(160_000.0)
        assert rust["job_demand_count"] == 1
        assert rust["salary_premium"] == pytest.approx(38_000.0)

    def test_sorted_by_premium_descending(self, silver):
        result = build_single_skill_roi(silver)
        assert result["skill"].to_list() == ["Rust", "Go", "Python", "SQL"]


class TestSkillOverlap:
    def test_only_jobs_with_two_or_more_skills(self, silver):
        result = build_skill_overlap(silver)
        rows = _rows_by(result, "skill_combo")

        assert set(rows) == {"Python, SQL", "Go, Rust"}

        python_sql = rows["Python, SQL"]
        assert python_sql["combo_avg_salary"] == pytest.approx(110_000.0)
        assert python_sql["combo_demand_count"] == 2
        assert python_sql["combo_premium"] == pytest.approx(-12_000.0)
        assert python_sql["combo_size"] == 2

        go_rust = rows["Go, Rust"]
        assert go_rust["combo_avg_salary"] == pytest.approx(160_000.0)
        assert go_rust["combo_demand_count"] == 1
        assert go_rust["combo_premium"] == pytest.approx(38_000.0)
        assert go_rust["combo_size"] == 2

    def test_combo_is_the_full_skill_set_not_pairwise(self):
        df = pl.DataFrame({
            "source": ["a"],
            "external_id": ["1"],
            "skills_list": [["Python", "SQL", "AWS"]],
            "expected_salary_usd": [150_000.0],
        })
        result = build_skill_overlap(df)

        assert result.height == 1
        row = result.row(0, named=True)
        assert row["skill_combo"] == "AWS, Python, SQL"
        assert row["combo_size"] == 3


class TestSkillHygiene:
    def test_drops_null_and_empty_skills(self):
        df = pl.DataFrame({
            "source": ["a", "a", "b"],
            "external_id": ["1", "2", "3"],
            "skills_list": [["Python", None, "", "SQL"], [], None],
            "expected_salary_usd": [100_000.0, 120_000.0, 140_000.0],
        })
        result = build_single_skill_roi(df)

        assert set(result["skill"].to_list()) == {"Python", "SQL"}
        assert result.height == 2
        assert result["skill"].is_null().sum() == 0

    def test_jobs_without_skills_are_excluded_from_skill_marts(self):
        df = pl.DataFrame({
            "source": ["a", "b"],
            "external_id": ["1", "2"],
            "skills_list": [[], None],
            "expected_salary_usd": [100_000.0, 120_000.0],
        })
        assert build_single_skill_roi(df).is_empty()
        assert build_skill_demand(df).is_empty()
        assert build_skill_overlap(df).is_empty()
        assert build_skill_related(df).is_empty()
        assert build_salary_distribution(df).is_empty()


class TestSkillDemand:
    def test_counts_all_jobs_including_salary_less(self):
        df = pl.DataFrame({
            "source": ["a", "b", "c"],
            "external_id": ["1", "2", "3"],
            "skills_list": [["Python", "SQL"], ["Python"], ["Go"]],
            "expected_salary_usd": [100_000.0, None, 80_000.0],
        })
        result = _rows_by(build_skill_demand(df), "skill")

        assert result["Python"]["job_demand_count"] == 2
        assert result["Python"]["job_share"] == pytest.approx(2 / 3)
        assert result["SQL"]["job_demand_count"] == 1
        assert result["Go"]["job_demand_count"] == 1

    def test_sorted_by_demand_descending(self):
        df = pl.DataFrame({
            "source": ["a", "b", "c"],
            "external_id": ["1", "2", "3"],
            "skills_list": [["Go"], ["Python"], ["Python"]],
            "expected_salary_usd": [100_000.0, 110_000.0, 120_000.0],
        })
        result = build_skill_demand(df)
        assert result["skill"].to_list() == ["Python", "Go"]


class TestSalaryCoveragePolicy:
    def test_roi_marts_use_only_salaried_jobs(self):
        df = pl.DataFrame({
            "source": ["a", "b", "c"],
            "external_id": ["1", "2", "3"],
            "skills_list": [["Python", "SQL"], ["Python", "SQL"], ["Go"]],
            "expected_salary_usd": [100_000.0, None, 80_000.0],
        })

        roi = _rows_by(build_single_skill_roi(df), "skill")
        assert roi["Python"]["job_demand_count"] == 1
        assert roi["SQL"]["job_demand_count"] == 1
        assert "Go" in roi

        assert build_salary_distribution(df).filter(
            pl.col("skill") == "Python"
        ).height == 1

    def test_related_pairs_use_all_jobs(self):
        df = pl.DataFrame({
            "source": ["a", "b"],
            "external_id": ["1", "2"],
            "skills_list": [["Python", "SQL"], ["Python", "SQL"]],
            "expected_salary_usd": [100_000.0, None],
        })
        result = build_skill_related(df)
        assert result.height == 1
        assert result.row(0, named=True)["co_occurrence_count"] == 2

    def test_market_overview_reports_coverage(self):
        df = pl.DataFrame({
            "source": ["a", "b", "c"],
            "external_id": ["1", "2", "3"],
            "skills_list": [["Python"], ["Python"], ["Go"]],
            "expected_salary_usd": [100_000.0, None, 80_000.0],
        })
        market = build_market_overview(df)
        metrics = dict(zip(market["metric"].to_list(), market["value"].to_list()))

        assert metrics["total_jobs"] == 3.0
        assert metrics["jobs_with_salary"] == 2.0
        assert metrics["salary_coverage_rate"] == pytest.approx(2 / 3, abs=1e-4)

    def test_salary_less_only_dataset_still_builds_demand(self, tmp_path):
        df = pl.DataFrame({
            "source": ["a", "b"],
            "external_id": ["1", "2"],
            "skills_list": [["Python"], ["Go", "Rust"]],
            "expected_salary_usd": [None, None],
        })
        marts = build_gold_marts(df, tmp_path)

        assert marts["skill_demand_mart"].height == 3
        assert marts["single_skill_roi_mart"].is_empty()
        assert marts["skill_overlap_mart"].is_empty()
        assert marts["salary_distribution_mart"].is_empty()

        metrics = dict(zip(
            marts["market_overview_mart"]["metric"].to_list(),
            marts["market_overview_mart"]["value"].to_list(),
        ))
        assert metrics["jobs_with_salary"] == 0.0
        assert metrics["salary_coverage_rate"] == 0.0


class TestMarketOverview:
    def test_metrics(self, silver):
        result = build_market_overview(silver)
        metrics = dict(zip(result["metric"].to_list(), result["value"].to_list()))

        assert metrics == {
            "total_jobs": 5.0,
            "jobs_with_salary": 5.0,
            "salary_coverage_rate": 1.0,
            "total_unique_skills": 4.0,
            "average_salary_usd": pytest.approx(122_000.0),
            "median_salary_usd": pytest.approx(120_000.0),
            "top_source_count": 2.0,
        }

    def test_total_unique_skills_includes_salary_less_jobs(self):
        df = pl.DataFrame({
            "source": ["a", "b"],
            "external_id": ["1", "2"],
            "skills_list": [["Python"], ["Go"]],
            "expected_salary_usd": [100_000.0, None],
        })
        result = build_market_overview(df)
        metrics = dict(zip(result["metric"].to_list(), result["value"].to_list()))

        assert metrics["total_unique_skills"] == 2.0

    def test_all_values_are_float(self, silver):
        result = build_market_overview(silver)
        assert result["value"].dtype == pl.Float64


class TestTopSkills:
    def test_top_ten_columns_and_order(self, silver):
        result = build_top_skills(build_single_skill_roi(silver))

        assert result.columns == [
            "skill",
            "avg_salary",
            "job_demand_count",
            "salary_premium",
        ]
        assert result.height == 4
        assert result["skill"].to_list()[0] == "Python"
        assert result["job_demand_count"].to_list()[0] == 3


class TestSkillRelated:
    def test_pairs_require_two_occurrences_and_no_self_pairs(self, silver):
        result = build_skill_related(silver)

        assert result.height == 1
        row = result.row(0, named=True)
        assert row["skill_a"] == "Python"
        assert row["skill_b"] == "SQL"
        assert row["co_occurrence_count"] == 2

        assert (result["skill_a"] != result["skill_b"]).all()
        assert (result["co_occurrence_count"] >= 2).all()

    def test_pair_is_canonicalized_and_not_mirrored(self, silver):
        result = build_skill_related(silver)
        pairs = set(zip(result["skill_a"].to_list(), result["skill_b"].to_list()))
        assert pairs == {("Python", "SQL")}
        assert ("SQL", "Python") not in pairs

    def test_single_job_pair_is_not_promoted_by_the_mirrored_join(self):
        df = pl.DataFrame({
            "source": ["a"],
            "external_id": ["1"],
            "skills_list": [["Go", "Rust"]],
            "expected_salary_usd": [100_000.0],
        })
        result = build_skill_related(df)
        assert result.is_empty()

    def test_same_external_id_in_different_sources_counts_as_two_jobs(self):
        """Job identity is (source, external_id), not external_id alone."""
        df = pl.DataFrame({
            "source": ["a", "b"],
            "external_id": ["1", "1"],
            "skills_list": [["Python", "SQL"], ["Python", "SQL"]],
            "expected_salary_usd": [100_000.0, 120_000.0],
        })
        result = build_skill_related(df)

        assert result.height == 1
        assert result.row(0, named=True)["co_occurrence_count"] == 2


class TestSalaryDistribution:
    def test_bucket_assignment(self, silver):
        result = build_salary_distribution(silver)
        rows = {
            (row["skill"], row["salary_bucket"]): row["job_count"]
            for row in result.to_dicts()
        }

        assert rows[("Python", "$100k - $125k")] == 2
        assert rows[("Python", "$125k - $150k")] == 1
        assert rows[("Rust", "$150k - $200k")] == 1
        assert rows[("Go", "$75k - $100k")] == 1
        assert rows[("Go", "$150k - $200k")] == 1

    def test_bucket_boundaries(self):
        salaries = [49_999.0, 50_000.0, 75_000.0, 100_000.0, 125_000.0, 150_000.0, 200_000.0]
        df = pl.DataFrame({
            "source": ["a"] * len(salaries),
            "external_id": [str(i) for i in range(len(salaries))],
            "skills_list": [["Python"]] * len(salaries),
            "expected_salary_usd": salaries,
        })

        result = build_salary_distribution(df)
        buckets = dict(zip(result["salary_bucket"].to_list(), result["job_count"].to_list()))

        assert buckets == {
            "< $50k": 1,
            "$50k - $75k": 1,
            "$75k - $100k": 1,
            "$100k - $125k": 1,
            "$125k - $150k": 1,
            "$150k - $200k": 1,
            "$200k+": 1,
        }

    def test_buckets_are_returned_in_numeric_order(self):
        salaries = [200_000.0, 49_999.0, 75_000.0, 100_000.0]
        df = pl.DataFrame({
            "source": ["a"] * len(salaries),
            "external_id": [str(i) for i in range(len(salaries))],
            "skills_list": [["Python"]] * len(salaries),
            "expected_salary_usd": salaries,
        })

        result = build_salary_distribution(df)

        assert result["salary_bucket"].to_list() == [
            "< $50k",
            "$75k - $100k",
            "$100k - $125k",
            "$200k+",
        ]
        assert result["bucket_order"].to_list() == [0, 2, 3, 6]


class TestSalaryColumnFallback:
    def test_uses_expected_salary_when_usd_column_absent(self, silver):
        fallback = silver.drop("expected_salary_usd").with_columns(
            silver["expected_salary_usd"].alias("expected_salary")
        )

        direct = build_single_skill_roi(silver)
        via_fallback = build_single_skill_roi(fallback)

        assert direct.sort("skill").equals(via_fallback.sort("skill"))


class TestBuildGoldMarts:
    def test_writes_all_seven_marts(self, silver, tmp_path):
        marts = build_gold_marts(silver, tmp_path)

        assert set(marts) == {
            "single_skill_roi_mart",
            "skill_demand_mart",
            "skill_overlap_mart",
            "market_overview_mart",
            "top_skills_mart",
            "skill_related_mart",
            "salary_distribution_mart",
        }
        for name in marts:
            assert (tmp_path / f"{name}.parquet").is_file()

        market = marts["market_overview_mart"]
        assert market.height == 7
        assert market["metric"].to_list() == [
            "total_jobs",
            "jobs_with_salary",
            "salary_coverage_rate",
            "total_unique_skills",
            "average_salary_usd",
            "median_salary_usd",
            "top_source_count",
        ]

    def test_missing_required_column_raises(self, silver, tmp_path):
        with pytest.raises(ValueError, match="skills_list"):
            build_gold_marts(silver.drop("skills_list"), tmp_path)

    def test_missing_salary_column_raises(self, silver, tmp_path):
        with pytest.raises(ValueError, match="salary column"):
            build_gold_marts(silver.drop("expected_salary_usd"), tmp_path)


class TestTechnicalOnlyMarts:
    def test_roi_excludes_soft_skills(self, silver_with_soft):
        rows = _rows_by(build_single_skill_roi(silver_with_soft), "skill")
        assert set(rows) == {"Python", "SQL", "Go", "Rust"}

    def test_demand_excludes_soft_skills_and_narrows_denominator(
        self, silver_with_soft
    ):
        rows = _rows_by(build_skill_demand(silver_with_soft), "skill")

        assert set(rows) == {"Python", "SQL", "Go", "Rust"}
        # Job 5 only has a soft skill, so it is not in the denominator.
        assert rows["Python"]["job_share"] == pytest.approx(3 / 4)
        assert rows["SQL"]["job_share"] == pytest.approx(2 / 4)

    def test_overlap_uses_technical_skills_only(self, silver_with_soft):
        rows = _rows_by(build_skill_overlap(silver_with_soft), "skill_combo")

        assert set(rows) == {"Python, SQL", "Go, Rust"}
        assert rows["Python, SQL"]["combo_size"] == 2

    def test_related_pairs_use_technical_skills_only(self, silver_with_soft):
        pairs = build_skill_related(silver_with_soft)

        assert pairs.select(["skill_a", "skill_b"]).rows() == [("Python", "SQL")]
        assert pairs["co_occurrence_count"].to_list() == [2]

    def test_salary_distribution_excludes_soft_skills(self, silver_with_soft):
        skills = set(build_salary_distribution(silver_with_soft)["skill"].to_list())
        assert skills == {"Python", "SQL", "Go", "Rust"}

    def test_market_overview_counts_technical_skills_only(self, silver_with_soft):
        market = build_market_overview(silver_with_soft)
        metrics = dict(zip(market["metric"].to_list(), market["value"].to_list()))

        assert metrics["total_jobs"] == 5.0
        assert metrics["total_unique_skills"] == 4.0

    def test_gold_marts_are_technical_only(self, silver_with_soft, tmp_path):
        marts = build_gold_marts(silver_with_soft, tmp_path)

        assert set(marts["skill_demand_mart"]["skill"].to_list()) == {
            "Python",
            "SQL",
            "Go",
            "Rust",
        }
