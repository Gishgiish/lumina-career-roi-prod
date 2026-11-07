"""Tests for the deduplication engine."""

import polars as pl

from src.transformation.dedup import _normalize_title, deduplicate_jobs


def _make_df(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows)


class TestNormalizeTitle:
    def test_strips_noise(self):
        assert _normalize_title("Senior Software Engineer (Remote)") == "senior software engineer"
        assert _normalize_title("Backend Engineer [Contract]") == "backend engineer"
        assert _normalize_title("  Frontend Engineer  ") == "frontend engineer"

    def test_lowercase(self):
        assert _normalize_title("MACHINE LEARNING ENGINEER") == "machine learning engineer"


class TestDeduplicateJobs:
    def test_exact_duplicates_removed(self):
        df = _make_df([
            {"title": "Software Engineer", "company": "Acme", "location": "Remote",
             "source": "remoteok", "external_id": "1"},
            {"title": "Software Engineer", "company": "Acme", "location": "Remote",
             "source": "lever", "external_id": "2"},
        ])
        result = deduplicate_jobs(df)
        assert len(result) == 1
        # Higher trust source kept (remoteok rank 5 > lever rank 4)
        assert result["source"][0] == "remoteok"

    def test_different_jobs_kept(self):
        df = _make_df([
            {"title": "Data Engineer", "company": "Acme", "location": "Remote",
             "source": "remoteok", "external_id": "1"},
            {"title": "Frontend Engineer", "company": "Beta", "location": "New York, NY",
             "source": "lever", "external_id": "2"},
        ])
        result = deduplicate_jobs(df)
        assert len(result) == 2

    def test_empty_df(self):
        df = pl.DataFrame({
            "title": [], "company": [], "location": [], "source": [], "external_id": [],
        })
        result = deduplicate_jobs(df)
        assert result.is_empty()

    def test_three_distinct_jobs_not_collapsed(self):
        """Regression for D-02: a shared location or company alone is not a duplicate."""
        df = _make_df([
            {"title": "Software Engineer", "company": "Acme", "location": "Remote",
             "source": "remoteok", "external_id": "1"},
            {"title": "Software Engineer", "company": "Other Co", "location": "Remote",
             "source": "remoteok", "external_id": "2"},
            {"title": "Software Engineer", "company": "Acme", "location": "Berlin",
             "source": "remoteok", "external_id": "3"},
        ])
        result = deduplicate_jobs(df)
        assert len(result) == 3
        assert set(result["external_id"].to_list()) == {"1", "2", "3"}

    def test_fuzzy_duplicate_requires_both_company_and_location(self):
        df = _make_df([
            {"title": "Senior Software Engineer", "company": "Acme", "location": "Remote",
             "source": "remoteok", "external_id": "1"},
            {"title": "Senior Software Engineers", "company": "Acme", "location": "Remote",
             "source": "lever", "external_id": "2"},
        ])
        result = deduplicate_jobs(df)
        assert len(result) == 1
        assert result["source"][0] == "remoteok"

    def test_fills_missing_salary_from_lower_trust_duplicate(self):
        df = _make_df([
            {"title": "Senior Software Engineer", "company": "Acme", "location": "Remote",
             "source": "remoteok", "external_id": "1",
             "min_salary_usd": None, "max_salary_usd": None, "salary_raw": None},
            {"title": "Senior Software Engineers", "company": "Acme", "location": "Remote",
             "source": "lever", "external_id": "2",
             "min_salary_usd": 90_000.0, "max_salary_usd": 110_000.0,
             "salary_raw": "$90k - $110k"},
        ])
        result = deduplicate_jobs(df)
        assert len(result) == 1
        row = result.row(0, named=True)
        assert row["source"] == "remoteok"
        assert row["min_salary_usd"] == 90_000.0
        assert row["max_salary_usd"] == 110_000.0
        assert row["salary_raw"] == "$90k - $110k"

    def test_does_not_overwrite_existing_salary_during_merge(self):
        df = _make_df([
            {"title": "Senior Software Engineer", "company": "Acme", "location": "Remote",
             "source": "remoteok", "external_id": "1",
             "min_salary_usd": 120_000.0, "max_salary_usd": 140_000.0},
            {"title": "Senior Software Engineers", "company": "Acme", "location": "Remote",
             "source": "lever", "external_id": "2",
             "min_salary_usd": 90_000.0, "max_salary_usd": 110_000.0},
        ])
        result = deduplicate_jobs(df)
        assert len(result) == 1
        row = result.row(0, named=True)
        assert row["min_salary_usd"] == 120_000.0
        assert row["max_salary_usd"] == 140_000.0

    def test_does_not_merge_identity_columns(self):
        df = _make_df([
            {"title": "Senior Software Engineer", "company": "Acme", "location": "Remote",
             "source": "remoteok", "external_id": None},
            {"title": "Senior Software Engineers", "company": "Acme", "location": "Remote",
             "source": "lever", "external_id": "lever-2"},
        ])
        result = deduplicate_jobs(df)
        assert len(result) == 1
        row = result.row(0, named=True)
        assert row["source"] == "remoteok"
        assert row["external_id"] is None

    def test_tie_break_is_deterministic_across_input_order(self):
        rows = [
            {"title": "Data Engineer", "company": "Acme", "location": "Remote",
             "source": "remoteok", "external_id": "b"},
            {"title": "Data Engineer", "company": "Acme", "location": "Remote",
             "source": "remoteok", "external_id": "a"},
        ]
        forward = deduplicate_jobs(_make_df(rows))
        backward = deduplicate_jobs(_make_df(list(reversed(rows))))
        assert forward["external_id"].to_list() == ["a"]
        assert backward["external_id"].to_list() == ["a"]

    def test_exact_key_prefers_specific_location_over_country(self):
        df = _make_df([
            {"title": "Data Engineer", "company": "Acme", "location": "Berlin",
             "country": "DE", "source": "remoteok", "external_id": "1"},
            {"title": "Data Engineer", "company": "Acme", "location": "Munich",
             "country": "DE", "source": "lever", "external_id": "2"},
        ])
        result = deduplicate_jobs(df)
        assert len(result) == 2
