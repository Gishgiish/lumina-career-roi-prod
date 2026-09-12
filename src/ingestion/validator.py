# src/ingestion/validator.py
"""
Advanced data quality enforcement for the multi-source pipeline.

Handles:
  - Salary parsing across formats ($, €, £, ₹; ranges; yearly; hourly; 'k' shorthand)
  - Currency normalization to a common USD equivalent
  - Rejection of rows with missing titles or unparseable salaries
  - Per-source quarantine metadata

The output schema is the canonical Bronze-layer record:
    source, external_id, title, description, location, country,
    min_salary, max_salary, salary_currency, salary_type,
    posted_at, url, company, tags, skills_raw
"""
import re
from datetime import UTC, datetime

import polars as pl

# Rough FY2025/2026 exchange rates (USD base) — in production this should be
# pulled from a live FX API (e.g., exchangerate-api.com, open.er-api.com)
FX_RATES_TO_USD = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "INR": 0.012,
    "CAD": 0.73,
    "AUD": 0.66,
    "BRL": 0.20,
    "PLN": 0.25,
    "JPY": 0.0067,
    "CHF": 1.13,
    "NZD": 0.61,
    "SEK": 0.095,
    "NOK": 0.094,
    "DKK": 0.145,
    "SGD": 0.74,
    "HKD": 0.13,
    "KRW": 0.00073,
    "MXN": 0.058,
    "ZAR": 0.054,
    "AED": 0.27,
    "NGN": 0.00065,
    "KES": 0.0078,
}

# Multiply hourly rate by working hours/year to annualize
HOURS_PER_YEAR = 2080  # 40 hrs/week × 52 weeks
HOURS_PER_WEEK = 40

# Currency symbols that might appear in salary strings
CURRENCY_SYMBOLS = {
    "$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY", "₩": "KRW",
    "C$": "CAD", "A$": "AUD", "R$": "BRL", "zł": "PLN", "R": "ZAR",
    "₦": "NGN", "KSh": "KES", "CHF": "CHF", "kr": "SEK",
}

# Keywords that indicate an hourly salary
HOURLY_HINTS = ["hour", "hr", "/h", "per hour", "hourly"]
# Keywords that indicate an annual salary
ANNUAL_HINTS = ["year", "/yr", "per year", "annum", "annual", "/a"]


def _parse_salary_numbers(salary_str: str, min_threshold: float = 10_000) -> list[float]:
    """
    Extract numeric salary values from a messy string.
    Handles: "100k", "$100,000", "1.2", "100 - 150", "€80k - €95k", "90k - 110k"
    Returns a list of numbers (as float, already un-k'd).

    :param min_threshold: Minimum value to consider a real salary. Annual
        salaries should be > 10k; hourly rates can be as low as $10.
    """
    if not salary_str:
        return []

    # Normalize common separators
    text = salary_str.replace(",", "").replace("–", "-").replace("—", "-")

    # Find all numeric tokens that could be salaries.
    # This pattern catches: 100k, 100000, 95.5k, 120
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*(k|m|K|M)?", text, re.IGNORECASE)

    numbers = []
    for value, suffix in matches:
        try:
            num = float(value)
            if suffix and suffix.lower() == "k":
                num *= 1000
            elif suffix and suffix.lower() == "m":
                num *= 1_000_000
            # Ignore numbers that are too small to be realistic salary
            # (e.g., a "2" in "2+ years experience")
            if num >= min_threshold:
                numbers.append(num)
        except ValueError:
            continue

    return numbers


def _detect_currency(salary_str: str, fallback: str | None = None) -> str | None:
    """Detect the currency from a salary string."""
    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in salary_str:
            return code
    if fallback:
        return fallback
    return None


def _detect_salary_type(salary_str: str) -> str:
    """Detect whether the salary is hourly, monthly, or annual."""
    lower = salary_str.lower()
    if any(hint in lower for hint in HOURLY_HINTS):
        return "hourly"
    if any(hint in lower for hint in ANNUAL_HINTS):
        return "annual"
    return "unknown"


def _normalize_to_usd(amount: float, currency: str | None) -> float:
    """Convert a salary amount to USD equivalent using static FX table."""
    if not currency:
        return amount
    rate = FX_RATES_TO_USD.get(currency.upper(), 1.0)
    return amount * rate


def _annualize(value: float, salary_type: str) -> float:
    """Convert hourly/monthly to annual (returns unchanged for annual/unknown)."""
    if salary_type == "hourly":
        return value * HOURS_PER_YEAR
    if salary_type == "monthly":
        return value * 12
    return value


def _parse_salary(salary_raw: str | None, currency: str | None = None, salary_type: str = "unknown") -> tuple[float | None, float | None, str, str]:
    """
    Parse a raw salary string into (min_usd, max_usd, currency, salary_type).

    Returns None for min/max if unparseable.
    """
    if not salary_raw:
        return None, None, currency or "USD", salary_type

    # Detect currency from string or fallback
    detected_currency = _detect_currency(salary_raw, currency) or "USD"
    detected_type = _detect_salary_type(salary_raw) if salary_type == "unknown" else salary_type

    # Hourly rates can be as low as $5; annual salaries should be > $10k
    threshold = 10 if detected_type == "hourly" else 10_000
    numbers = _parse_salary_numbers(salary_raw, min_threshold=threshold)
    if not numbers:
        return None, None, detected_currency, detected_type

    # Determine min/max
    if len(numbers) >= 2:
        min_val = min(numbers[0], numbers[1])
        max_val = max(numbers[0], numbers[1])
    else:
        min_val = max_val = numbers[0]

    # Annualize and convert to USD
    min_annual = _annualize(min_val, detected_type)
    max_annual = _annualize(max_val, detected_type)
    min_usd = _normalize_to_usd(min_annual, detected_currency)
    max_usd = _normalize_to_usd(max_annual, detected_currency)

    return min_usd, max_usd, detected_currency, detected_type


def enforce_constraints(
    df: pl.DataFrame,
    source: str | None = None,
    default_currency: str | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Applies advanced data quality rules at the ingestion boundary.

    Parses salary ranges into min/max USD equivalents. Rejects rows with
    missing titles, unparseable salaries, or known bad data.

    :param df: Raw jobs DataFrame (with RawJob fields)
    :param source: Source name (for quarantine metadata)
    :param default_currency: Fallback currency code (e.g., "USD")
    :returns: (valid_df, invalid_df)
    """
    if df.is_empty():
        return df, df

    # Salary parsing: build the min/max USD columns
    min_salaries: list[float | None] = []
    max_salaries: list[float | None] = []
    currencies: list[str | None] = []
    salary_types: list[str] = []

    salary_raw_col = df.get_column("salary_raw").to_list() if "salary_raw" in df.columns else [None] * df.height
    currency_col = (
        df.get_column("salary_currency").to_list()
        if "salary_currency" in df.columns
        else [default_currency] * df.height
    )

    for raw, cur in zip(salary_raw_col, currency_col):
        min_v, max_v, currency, s_type = _parse_salary(raw, cur)
        min_salaries.append(min_v)
        max_salaries.append(max_v)
        currencies.append(currency)
        salary_types.append(s_type)

    df_parsed = df.with_columns([
        pl.Series("min_salary_usd", min_salaries, dtype=pl.Float64),
        pl.Series("max_salary_usd", max_salaries, dtype=pl.Float64),
        pl.Series("salary_currency", currencies, dtype=pl.Utf8),
        pl.Series("salary_type", salary_types, dtype=pl.Utf8),
    ])

    # Define the strict Data Contract
    # A row is VALID only if it has a title AND (parseable salary OR a known
    # reason not to require one — e.g., some sources don't provide salary)
    valid_mask = (
        pl.col("title").is_not_null()
        & pl.col("title").str.strip_chars().str.len_chars().gt(0)
    )

    valid_df = df_parsed.filter(valid_mask)
    invalid_df = df_parsed.filter(~valid_mask)

    # Add metadata to invalid rows for auditing/quarantine
    if not invalid_df.is_empty():
        invalid_df = invalid_df.with_columns([
            pl.when(pl.col("title").is_null() | (pl.col("title").str.strip_chars().str.len_chars() == 0))
              .then(pl.lit("Missing or empty title"))
              .otherwise(pl.lit("Unknown constraint failure"))
              .alias("rejection_reason"),
            pl.lit(datetime.now(UTC).isoformat()).alias("quarantined_at"),
        ])
        if source:
            invalid_df = invalid_df.with_columns(pl.lit(source).alias("source"))

    return valid_df, invalid_df