# tests/test_validator.py
"""Unit tests for the multi-source validator."""

import polars as pl
import pytest

from src.ingestion.validator import (
    _detect_currency,
    _parse_salary,
    _parse_salary_numbers,
    enforce_constraints,
)


class TestSalaryParsing:
    def test_usd_range(self):
        min_v, max_v, cur, _ = _parse_salary("$100,000 - $150,000", "USD", "annual")
        assert min_v == 100_000
        assert max_v == 150_000
        assert cur == "USD"

    def test_k_shorthand(self):
        min_v, max_v, _, _ = _parse_salary("$90k - $110k", "USD", "annual")
        assert min_v == 90_000
        assert max_v == 110_000

    def test_hourly(self):
        min_v, _max_v, _, stype = _parse_salary("$50 - $70 per hour", "USD")
        assert stype == "hourly"
        assert min_v == pytest.approx(104_000, rel=1e-3)  # 50 * 2080

    def test_eur_currency(self):
        min_v, _max_v, cur, _ = _parse_salary("€80,000 - €95,000", "EUR", "annual")
        assert cur == "EUR"
        assert min_v == pytest.approx(80_000 * 1.08, rel=1e-3)

    def test_unparseable(self):
        min_v, max_v, _, _ = _parse_salary("Competitive", "USD", "annual")
        assert min_v is None
        assert max_v is None

    def test_parse_numbers_ignores_small(self):
        nums = _parse_salary_numbers("2+ years experience, $120k salary")
        assert 120_000 in nums
        assert 2 not in nums

    def test_currency_detection(self):
        assert _detect_currency("$100k") == "USD"
        assert _detect_currency("€80k") == "EUR"
        assert _detect_currency("£70k") == "GBP"


class TestEnforceConstraints:
    def test_valid_rows(self):
        df = pl.DataFrame({
            "title": ["Software Engineer", "Data Engineer"],
            "salary_raw": ["$120,000 - $150,000", "$110,000"],
            "salary_currency": ["USD", "USD"],
            "salary_type": ["annual", "annual"],
        })
        valid, invalid = enforce_constraints(df, source="test")
        assert len(valid) == 2
        assert len(invalid) == 0

    def test_invalid_rows(self):
        df = pl.DataFrame({
            "title": ["Software Engineer", None, ""],
            "salary_raw": ["$120,000", "$110,000", "$100,000"],
            "salary_currency": ["USD", "USD", "USD"],
            "salary_type": ["annual", "annual", "annual"],
        })
        valid, invalid = enforce_constraints(df, source="test")
        assert len(valid) == 1
        assert len(invalid) == 2
        assert "rejection_reason" in invalid.columns

    def test_empty_df(self):
        df = pl.DataFrame({
            "title": [],
            "salary_raw": [],
            "salary_currency": [],
            "salary_type": [],
        })
        valid, invalid = enforce_constraints(df)
        assert valid.is_empty()
        assert invalid.is_empty()