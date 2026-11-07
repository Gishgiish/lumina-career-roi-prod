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
import logging
import re
from datetime import UTC, datetime

import polars as pl

logger = logging.getLogger(__name__)

# Rough FY2025/2026 exchange rates (USD base).
#
# Decision (Step 2.1, 2026-11-07): keep these static for the prototype. They
# are deterministic, work offline, and need no API key, which keeps tests and
# seed runs reproducible. They are still an approximation and must be moved to
# configuration or a live FX source before any production launch; treat the
# converted USD values as directional, not financially precise.
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
    "CNY": 0.14,
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

# ISO 4217 codes we can convert. Symbols are checked after these so that the
# single-letter "R" (ZAR) can never match the "R" inside "EUR" or "INR".
ISO_CURRENCY_CODES = frozenset(FX_RATES_TO_USD)

# Salary plausibility bounds in USD. Anything outside these is treated as a
# parsing artifact (URL ids, page numbers, HTML-entity fragments) rather than a
# salary. This is deliberately broad: it rejects quadrillion-scale noise while
# keeping senior/executive compensation.
MIN_ANNUAL_USD = 1_000
MAX_ANNUAL_USD = 10_000_000

# Word-boundary patterns for salary period hints. Substring matching is unsafe:
# "hr" appears inside "href"/"https", which misclassified HTML comments as
# hourly and multiplied their numbers by 2,080.
HOURLY_HINTS = [re.compile(pattern, re.IGNORECASE) for pattern in (
    r"\bper\s+hour\b",
    r"\ban\s+hour\b",
    r"\bhourly\b",
    r"\bhours?\b",
    r"\bhrs?\b",
    r"/\s*h(?:r)?\b",
)]
ANNUAL_HINTS = [re.compile(pattern, re.IGNORECASE) for pattern in (
    r"\bper\s+year\b",
    r"\bannual(?:ly)?\b",
    r"\bannum\b",
    r"\byearly\b",
    r"/\s*(?:yr|year)\b",
)]


# "$250-325K", "$150-$250k", and "$200 to 300k" mean both bounds share the
# trailing suffix. Currency symbols are preserved when either bound has one.
_RANGE_SUFFIX_RE = re.compile(
    r"([€£$]?)\s*(\d+(?:\.\d+)?)\s*(?:-|to)\s*"
    r"([€£$]?)\s*(\d+(?:\.\d+)?)\s*(k|m)\b",
    re.IGNORECASE,
)


def _propagate_range_suffix(text: str) -> str:
    """Apply a trailing k/m suffix to both bounds of a salary range."""

    def _replacement(match: re.Match) -> str:
        low_symbol, low, high_symbol, high, suffix = match.groups()
        return f"{low_symbol}{low}{suffix} - {high_symbol}{high}{suffix}"

    return _RANGE_SUFFIX_RE.sub(_replacement, text)


def _parse_salary_numbers(salary_str: str, min_threshold: float = 10_000) -> list[float]:
    """
    Extract numeric salary values from a messy string.
    Handles: "100k", "$100,000", "120 000 kr", "1.2", "100 - 150", "€80k - €95k", "90k - 110k"
    Returns a list of numbers (as float, already un-k'd).

    :param min_threshold: Minimum value to consider a real salary. Annual
        salaries should be > 10k; hourly rates can be as low as $10.
    """
    if not salary_str:
        return []

    # Normalize common separators
    text = salary_str.replace(",", "").replace("–", "-").replace("—", "-")
    # "$250-325K" only labels the upper bound with "K"; make both bounds share it.
    text = _propagate_range_suffix(text)

    # Find all numeric tokens that could be salaries.
    # Catches: 100k, 100000, 95.5k, 120 — plus space-grouped thousands like
    # "120 000" (common in SE/DK/NO/DE listings) as a single number.
    # The trailing \b stops the k/m shorthand from stealing the leading letter
    # of words like "kr" (so "120 000 kr" stays 120_000, not 120_000_000).
    matches = re.findall(r"(\d+(?:\.\d+)?(?:\s\d{3})*)\s*(k|m|K|M)?\b", text, re.IGNORECASE)

    numbers = []
    for value, suffix in matches:
        try:
            num = float("".join(value.split()))
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
    """Detect the currency from a salary string using context-aware matching.

    Heuristics:
     - Check ISO 4217 codes first as whole tokens, so "EUR 80k" and
       "1,200,000 INR" are read as EUR/INR rather than letting the single-letter
       "R" (ZAR) rule match the R inside the code.
     - Then iterate symbols longest-first (so 'C$' is checked before '$').
     - Require symbols to appear in currency positions (adjacent to digits or
       as a standalone token) to avoid accidental substring matches.
     - Disambiguate '¥' -> CNY if the text mentions China/CNY, else JPY.
     - For the single-letter "R" (ZAR), require a standalone/number-adjacent
       token that is not preceded by a letter.
    """

    if not salary_str:
        return fallback

    text = salary_str

    # 1. ISO codes are the least ambiguous signal: match them as whole tokens.
    for code in sorted(ISO_CURRENCY_CODES, key=len, reverse=True):
        pattern = rf"(?<![A-Za-z]){re.escape(code)}(?![A-Za-z])"
        if re.search(pattern, text, re.IGNORECASE):
            return code

    # 2. Symbols, longest-first so multi-character symbols win over their
    #    single-character prefixes ("C$" before "$", "R$" before "R").
    for symbol in sorted(CURRENCY_SYMBOLS.keys(), key=len, reverse=True):
        code = CURRENCY_SYMBOLS[symbol]
        esc = re.escape(symbol)

        # "R" (ZAR) is the riskiest symbol: it must be a standalone token or
        # adjacent to digits, and it must not be preceded by another letter.
        # This keeps "R 500 000" and "500 000 R" working while rejecting the
        # R in "EUR"/"INR".
        if symbol == "R":
            pattern = r"(?<![A-Za-z])R(?=\s*\d)|(?<=\d)\s*R(?![A-Za-z])"
            if re.search(pattern, text, re.IGNORECASE):
                return code
            continue

        # Build flexible patterns:
        # - symbol directly before digits e.g. "C$ 120,000" or "$120k"
        # - digits directly before symbol e.g. "120,000 kr"
        # - standalone token e.g. "CHF"
        prefix_digits = rf"{esc}\s*\d"  # symbol then digits
        suffix_digits = rf"\d\s*{esc}"  # digits then symbol
        standalone = rf"\b{esc}\b"      # whole token match

        if symbol.isalpha():
            # Alphabetic symbols must be a standalone token or touch a number;
            # never match arbitrary substrings (e.g. "kr" inside "Krakow").
            pattern = rf"({prefix_digits}|{suffix_digits}|{standalone})"
        else:
            pattern = rf"({prefix_digits}|{suffix_digits}|{esc})"

        if re.search(pattern, text, re.IGNORECASE):
            # special-case: '¥' could be JPY or CNY — prefer CNY if context mentions China/CNY
            if symbol == "¥":
                low = text.lower()
                if "cny" in low or 'china' in low or "cn" in low:
                    return "CNY"
                return "JPY"
            return code

    if fallback:
        return fallback
    return None


def _detect_salary_type(salary_str: str) -> str:
    """Detect whether the salary is hourly, monthly, or annual.

    Uses word-boundary patterns rather than substring checks so HTML fragments
    such as ``href``/``https`` cannot be read as ``hr`` (hourly).
    """
    if any(pattern.search(salary_str) for pattern in HOURLY_HINTS):
        return "hourly"
    if any(pattern.search(salary_str) for pattern in ANNUAL_HINTS):
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

    # Prefer the adapter-supplied ISO currency over symbol sniffing. Adzuna, for
    # example, knows the country currency but historically emitted "$" in every
    # salary string; trusting the symbol would mis-convert GBP/EUR/INR salaries.
    explicit_currency = currency.upper() if currency else None
    if explicit_currency and explicit_currency not in ISO_CURRENCY_CODES:
        explicit_currency = None
    detected_currency = explicit_currency or _detect_currency(salary_raw) or "USD"
    detected_type = _detect_salary_type(salary_raw) if salary_type == "unknown" else salary_type

    # Hourly rates can be as low as $5; annual salaries should be > $10k
    threshold = 10 if detected_type == "hourly" else 10_000
    numbers = _parse_salary_numbers(salary_raw, min_threshold=threshold)
    if not numbers:
        return None, None, detected_currency, detected_type

    # Annualize and convert each candidate, then drop implausible values. This
    # keeps a stray URL id or page number from setting the min/max and prevents
    # the quadrillion-scale averages seen in the first live run.
    usd_values: list[float] = []
    for number in numbers[:8]:
        annual = _annualize(number, detected_type)
        usd = _normalize_to_usd(annual, detected_currency)
        if MIN_ANNUAL_USD <= usd <= MAX_ANNUAL_USD:
            usd_values.append(usd)

    if not usd_values:
        return None, None, detected_currency, detected_type

    # Preserve the original "first two numbers form the range" semantics.
    selected = usd_values[:2]
    return min(selected), max(selected), detected_currency, detected_type


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
    # Adapters that know the salary period (for example an hourly API field)
    # must not have that knowledge discarded. Unknown/absent values fall back
    # to text detection inside _parse_salary.
    type_col = (
        df.get_column("salary_type").to_list()
        if "salary_type" in df.columns
        else ["unknown"] * df.height
    )

    for raw, cur, stype in zip(salary_raw_col, currency_col, type_col):
        declared_type = getattr(stype, "value", stype) or "unknown"
        min_v, max_v, currency, s_type = _parse_salary(raw, cur, declared_type)
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

    raw_present = sum(1 for raw in salary_raw_col if raw)
    parsed = sum(1 for lo, hi in zip(min_salaries, max_salaries) if lo is not None or hi is not None)
    if source and raw_present:
        logger.info(
            "%s: parsed %d/%d salary strings (%d unparsed or implausible)",
            source,
            parsed,
            raw_present,
            raw_present - parsed,
        )

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
