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

    def test_parse_numbers_space_grouped_thousands(self):
        nums = _parse_salary_numbers("120 000 kr (Stockholm)")
        assert nums == [120_000.0]

    def test_parse_numbers_does_not_steal_k_from_kr(self):
        # "kr" (SEK) must not be read as a "k" shorthand → 120_000, not 120_000_000
        assert _parse_salary_numbers("120,000 kr (Stockholm)") == [120_000.0]

    def test_sek_salary_parsed_to_usd(self):
        min_v, max_v, cur, stype = _parse_salary("120 000 kr (Stockholm)")
        assert cur == "SEK"
        assert min_v == pytest.approx(120_000 * 0.095, rel=1e-3)
        assert max_v == pytest.approx(120_000 * 0.095, rel=1e-3)
        assert stype == "unknown"

    def test_currency_detection(self):
        assert _detect_currency("$100k") == "USD"
        assert _detect_currency("€80k") == "EUR"
        assert _detect_currency("£70k") == "GBP"

    def test_explicit_adapter_currency_wins_over_symbol(self):
        # Adzuna used to prefix every salary with "$"; the adapter-supplied ISO
        # currency must win so a "$"-prefixed GBP job is not read as USD.
        min_v, max_v, cur, _ = _parse_salary("$70,000 - $90,000", "GBP", "annual")
        assert cur == "GBP"
        assert min_v == pytest.approx(70_000 * 1.27, rel=1e-3)
        assert max_v == pytest.approx(90_000 * 1.27, rel=1e-3)

    def test_iso_eur_prefix_parsed_to_usd_not_zar(self):
        min_v, max_v, cur, stype = _parse_salary("EUR 80k")
        assert cur == "EUR"
        assert min_v == pytest.approx(80_000 * 1.08, rel=1e-3)
        assert max_v == pytest.approx(80_000 * 1.08, rel=1e-3)
        assert stype == "unknown"

    def test_iso_inr_prefix_parsed_to_usd_not_zar(self):
        min_v, max_v, cur, _ = _parse_salary("INR 1,200,000")
        assert cur == "INR"
        assert min_v == pytest.approx(1_200_000 * 0.012, rel=1e-3)
        assert max_v == pytest.approx(1_200_000 * 0.012, rel=1e-3)

    def test_iso_eur_suffix_parsed(self):
        min_v, _max_v, cur, _ = _parse_salary("80 000 EUR")
        assert cur == "EUR"
        assert min_v == pytest.approx(80_000 * 1.08, rel=1e-3)

    def test_cny_salary_converted_with_fx_rate(self):
        min_v, max_v, cur, _ = _parse_salary("¥100,000 (China)")
        assert cur == "CNY"
        assert min_v == pytest.approx(100_000 * 0.14, rel=1e-3)
        assert max_v == pytest.approx(100_000 * 0.14, rel=1e-3)

    def test_symbol_detected_when_adapter_currency_is_absent(self):
        # HackerNews parses free-text salaries that may be EUR or GBP; leaving
        # salary_currency unset must let the symbol drive conversion.
        min_v, _max_v, cur, _ = _parse_salary("€80k", None, "annual")
        assert cur == "EUR"
        assert min_v == pytest.approx(80_000 * 1.08, rel=1e-3)

        min_v, _max_v, cur, _ = _parse_salary("£70k", None, "annual")
        assert cur == "GBP"
        assert min_v == pytest.approx(70_000 * 1.27, rel=1e-3)

    def test_zarr_rand_standalone_tokens(self):
        for raw in ("R 500 000", "500 000 R"):
            min_v, max_v, cur, _ = _parse_salary(raw)
            assert cur == "ZAR"
            assert min_v == pytest.approx(500_000 * 0.054, rel=1e-3)
            assert max_v == pytest.approx(500_000 * 0.054, rel=1e-3)


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


class TestCurrencyDetection:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("$120k", "USD"),
            ("$120,000 - $150,000", "USD"),
            ("€80k - €95k", "EUR"),
            ("£70k", "GBP"),
            ("₹500k", "INR"),
            ("C$ 120,000", "CAD"),
            ("A$ 90k", "AUD"),
            ("R$ 12,000", "BRL"),
            ("zł 15,000", "PLN"),
            ("R 40,000", "ZAR"),
            ("R 500 000", "ZAR"),
            ("500 000 R", "ZAR"),
            ("USD 120,000", "USD"),
            ("GBP 70k", "GBP"),
            ("EUR 80,000", "EUR"),
            ("EUR 80k", "EUR"),
            ("INR 500000", "INR"),
            ("INR 1,200,000", "INR"),
            ("ZAR 500 000", "ZAR"),
            ("80 000 EUR", "EUR"),
            ("1,200,000 INR", "INR"),
            ("₦6,000,000", "NGN"),
            ("KSh 500,000", "KES"),
            ("CHF 100k", "CHF"),
            ("500 kr", "SEK"),
            ("120 000 kr (Stockholm)", "SEK"),
            ("¥100,000", "JPY"),
            ("¥100,000 (China)", "CNY"),
            ("Stockholm", None),
            ("no salary info here", None),
            ("", None),
        ],
    )
    def test_detects_expected_currency(self, text, expected):
        assert _detect_currency(text) == expected

    def test_detected_currency_wins_over_fallback(self):
        assert _detect_currency("€80k", "USD") == "EUR"
        assert _detect_currency("120 000 kr (Stockholm)", "USD") == "SEK"

    def test_fallback_when_no_symbol_present(self):
        assert _detect_currency("Competitive") is None
        assert _detect_currency("Competitive", "USD") == "USD"
        assert _detect_currency("", "USD") == "USD"

    def test_single_letter_alpha_requires_digits(self):
        # "R" (ZAR) is single-letter alpha: must only match adjacent to digits,
        # never an arbitrary 'R' inside prose.
        assert _detect_currency("Senior Python Developer") is None
        assert _detect_currency("R 40,000") == "ZAR"
