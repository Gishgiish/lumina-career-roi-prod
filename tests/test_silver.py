# tests/test_silver.py
"""Unit tests for Silver-layer normalization helpers."""

import polars as pl

from src.transformation.silver import (
    _add_salary_metrics,
    _extract_skills_list,
    _standardize_title,
)


class TestStandardizeTitle:
    def test_title_cases_plain_titles(self):
        df = pl.DataFrame({"title": ["software engineer", "  data scientist  "]})
        result = df.with_columns(_standardize_title())
        assert result["title"].to_list() == ["Software Engineer", "Data Scientist"]

    def test_preserves_acronyms(self):
        titles = [
            "AWS Solutions Architect",
            "Senior ML Engineer",
            "API Platform Engineer",
            "SQL ETL Developer",
            "QA Automation Engineer",
        ]
        df = pl.DataFrame({"title": titles})
        result = df.with_columns(_standardize_title())
        assert result["title"].to_list() == titles

    def test_preserves_mixed_case_product_names(self):
        titles = ["DevOps Lead", "iOS Developer", "JavaScript Engineer"]
        df = pl.DataFrame({"title": titles})
        result = df.with_columns(_standardize_title())
        assert result["title"].to_list() == titles


class TestExtractSkillsList:
    def test_ambiguous_prose_is_ignored(self):
        assert "Go" not in _extract_skills_list([], "We go to market.")
        assert "C" not in _extract_skills_list([], "Experience selling to C-suite.")

    def test_tags_are_authoritative(self):
        assert "Go" in _extract_skills_list(["go"], "We go to market.")

    def test_recruiting_uses_title_context(self):
        text = "You will support the recruiting process."
        assert "Recruiting" not in _extract_skills_list([], text)
        assert "Recruiting" in _extract_skills_list([], text, "Technical Recruiter")
        assert "Recruiting" not in _extract_skills_list([], text, "Software Engineer")

    def test_recruiting_explicit_phrase_needs_no_title(self):
        assert "Recruiting" in _extract_skills_list(
            [], "Technical recruiting experience.", "Software Engineer"
        )

    def test_recruiting_tags_stay_authoritative(self):
        assert "Recruiting" in _extract_skills_list(["recruiting"], "", "Software Engineer")


class TestAddSalaryMetrics:
    def test_midpoint_of_min_and_max(self):
        df = pl.DataFrame({"min_salary_usd": [100_000.0], "max_salary_usd": [140_000.0]})
        result = _add_salary_metrics(df)

        assert result["expected_salary_usd"].to_list() == [120_000.0]
        assert result["has_salary"].to_list() == [True]

    def test_keeps_salary_less_rows_and_flags_them(self):
        df = pl.DataFrame({
            "min_salary_usd": [100_000.0, None],
            "max_salary_usd": [140_000.0, None],
        })
        result = _add_salary_metrics(df)

        assert result.height == 2  # row is retained for demand statistics
        assert result["expected_salary_usd"].to_list() == [120_000.0, None]
        assert result["has_salary"].to_list() == [True, False]

    def test_min_only_falls_back_to_min(self):
        df = pl.DataFrame({"min_salary_usd": [90_000.0], "max_salary_usd": [None]})
        result = _add_salary_metrics(df)

        assert result["expected_salary_usd"].to_list() == [90_000.0]
        assert result["has_salary"].to_list() == [True]

    def test_max_only_falls_back_to_max(self):
        df = pl.DataFrame({"min_salary_usd": [None], "max_salary_usd": [110_000.0]})
        result = _add_salary_metrics(df)

        assert result["expected_salary_usd"].to_list() == [110_000.0]
        assert result["has_salary"].to_list() == [True]
