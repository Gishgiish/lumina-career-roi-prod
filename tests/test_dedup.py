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