# src/ingestion/sources/hackernews.py
"""
HackerNews "Who's Hiring" source adapter.

Extracts job postings from the monthly "Who is hiring?" threads on
HackerNews using the official Firebase API.

Note: HN's Why is Hiring threads are high-quality but unstructured —
job posts are top-level comments. We parse the comment text to extract
title, company, location, salary, and skills. This is a best-effort
parser.

API endpoints:
  - Algolia search: https://hn.algolia.com/api/v1/search_by_date?tags=story&query=Who%20is%20hiring
  - Item retrieval: https://hacker-news.firebaseio.com/v0/item/{id}.json
"""
import html
import logging
import re

import httpx

from src.ingestion.sources.base import BaseSource, SourceError
from src.schemas import JobSource, RawJob, RawJobBatch, SalaryType

logger = logging.getLogger(__name__)

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"
ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

# Patterns specific enough to trust anywhere in a comment: currency ranges and
# amounts explicitly tied to a pay period.
EXPLICIT_SALARY_PATTERNS = [
    # $100k - $150k, $100K, $100k/year, etc.
    r"\$([\d,]+)\s*(?:k|K)?\s*(?:-|to|–)\s*\$?([\d,]+)\s*(?:k|K)?",
    r"\$([\d,]+)\s*(?:k|K)?\s*(?:/|per)?\s*(?:yr|year|annum)",
    # € numbers
    r"€([\d,]+)\s*(?:k|K)?\s*(?:-|to|–)\s*€?([\d,]+)\s*(?:k|K)?",
    # £ numbers
    r"£([\d,]+)\s*(?:k|K)?\s*(?:-|to|–)\s*£?([\d,]+)\s*(?:k|K)?",
]

# A bare currency amount ("$190k"). On its own it is ambiguous: comments also
# mention funding rounds, revenue, and savings, so it is trusted only in a
# header or on a line that uses payroll vocabulary.
BARE_SALARY_PATTERN = r"[€£$]\s?\d[\d,]*(?:\.\d+)?\s*(?:k|K|m|M)?"

# Payroll vocabulary. Keep this salary-specific: generic words such as
# "annual" also match "annual revenue" and would re-introduce the bug.
SALARY_CUE_RE = re.compile(
    r"\b(?:salary|salaries|compensation|comp|ote|"
    r"base\s+pay|base\s+salary|pay|rate|wage|stipend|"
    r"total\s+comp|cash\s+comp)\b"
    r"|/\s*(?:yr|year|hr|hour)\b"
    r"|\bper\s+(?:year|hour|annum|month)\b"
    r"|\bannually\b",
    re.IGNORECASE,
)

# Algolia returns comment HTML ("<p>", "<a href=...>") rather than newlines.
# Convert block tags to line breaks and strip inline tags before parsing.
BLOCK_TAG_RE = re.compile(r"<\s*/?\s*(?:br|p|div|li)\s*/?\s*>", re.IGNORECASE)
INLINE_TAG_RE = re.compile(r"<[^>]+>")

MAX_TITLE_LEN = 200
MAX_SALARY_RAW_LEN = 80


def _html_to_text(raw: str) -> str:
    """Convert an HN comment body to plain, line-delimited text."""
    if not raw:
        return ""
    text = BLOCK_TAG_RE.sub("\n", raw)
    text = INLINE_TAG_RE.sub(" ", text)
    text = html.unescape(text).replace("\xa0", " ")
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def _truncate(value: str, limit: int) -> str:
    """Trim a value to ``limit`` characters without cutting mid-word."""
    value = value.strip()
    if len(value) <= limit:
        return value
    cut = value[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{cut}…"


class HackerNewsSource(BaseSource):
    """Adapter for HackerNews 'Who is hiring?' threads."""

    name = "hackernews"
    trust_rank = 4

    def _validate_config(self):
        return

    def _fetch_threads(self) -> list[dict]:
        """Find the most recent 'Who is hiring?' threads."""
        try:
            response = httpx.get(
                ALGOLIA_URL,
                params={
                    "tags": "story",
                    "query": "Who is hiring",
                    "hitsPerPage": 10,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            hits = data.get("hits", [])
            # Filter to actual "Ask HN: Who is hiring? (Month YYYY)" threads
            threads = [
                hit
                for hit in hits
                if hit.get("title", "").startswith("Ask HN: Who is hiring")
            ]
            return threads
        except Exception as exc:
            raise SourceError(f"HackerNews thread fetch failed: {exc}") from exc

    def _fetch_comments(self, thread_id: int) -> list[int]:
        """Fetch top-level comment IDs for a thread."""
        try:
            response = httpx.get(ITEM_URL.format(thread_id), timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("kids", [])
        except Exception as exc:
            raise SourceError(f"HackerNews comment fetch failed: {exc}") from exc

    def _fetch_comment(self, comment_id: int) -> dict | None:
        """Fetch a single comment by ID."""
        try:
            response = httpx.get(ITEM_URL.format(comment_id), timeout=30)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            return None

    @staticmethod
    def _parse_job_comment(text: str) -> dict | None:
        """Extract structured job info from an HN comment.

        Algolia comment bodies are HTML, so normalize block tags to newlines
        first. Only the header line is parsed into fields, and salary text is
        reduced to an explicit salary token; arbitrary description text must
        never become ``salary_raw``.
        """
        # First line typically: "CompanyName | Job Title | Location | $Salary" or
        # "[Company] | [Title] ([Location]) - $Salary"
        text = _html_to_text(text)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return None

        first_line = lines[0]

        # Try pipe-delimited format: Company | Title | Location | $Salary
        parts = [p.strip() for p in first_line.split("|")]
        if len(parts) >= 2:
            company = parts[0].strip("[] ")
            title = _truncate(parts[1].strip("[] "), MAX_TITLE_LEN)
            location = parts[2].strip() if len(parts) > 2 else None
            salary_raw = None
            if len(parts) > 3:
                match = HackerNewsSource._extract_salary(parts[3])
                if match:
                    salary_raw = _truncate(match, MAX_SALARY_RAW_LEN)
            return {
                "company": company,
                "title": title,
                "location": location,
                "salary_raw": salary_raw,
                "description": text,
            }

        # Try format: "Title (Location) - Company"
        m = re.match(r"^(.+?)\s*\((.+?)\)\s*(?:-|–|at)\s*(.+)$", first_line)
        if m:
            return {
                "title": _truncate(m.group(1).strip(), MAX_TITLE_LEN),
                "location": m.group(2).strip(),
                "company": m.group(3).strip(),
                "salary_raw": None,
                "description": text,
            }

        # Fallback: title is everything
        return {
            "title": _truncate(first_line, MAX_TITLE_LEN),
            "company": None,
            "location": None,
            "salary_raw": None,
            "description": text,
        }

    @staticmethod
    def _extract_salary(text: str, allow_bare: bool = True) -> str | None:
        """Best-effort salary extraction from one segment of text.

        ``allow_bare`` gates the ambiguous single-value pattern. Callers pass
        False for body prose that has no pay context.
        """
        for pattern in EXPLICIT_SALARY_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(0).strip()
        if allow_bare:
            m = re.search(BARE_SALARY_PATTERN, text, re.IGNORECASE)
            if m:
                return m.group(0).strip()
        return None

    @classmethod
    def _extract_salary_from_description(cls, text: str) -> str | None:
        """Extract a salary without swallowing non-pay amounts.

        The header is trusted when it looks like the pipe-delimited job line
        (or names a payroll term). In the body, explicit ranges and
        period-bound amounts are trusted anywhere, while a bare amount is
        accepted only on a line that uses payroll vocabulary. This keeps
        "raised $2.7M" and "saves $1.2M in losses" out of ``salary_raw``.
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return None

        header = lines[0]
        header_like = "|" in header or bool(SALARY_CUE_RE.search(header))
        match = cls._extract_salary(header, allow_bare=header_like)
        if match:
            return match

        for line in lines[1:]:
            if SALARY_CUE_RE.search(line):
                match = cls._extract_salary(line)
            else:
                match = cls._extract_salary(line, allow_bare=False)
            if match:
                return match
        return None

    def fetch(self, last_watermark: str | None = None) -> RawJobBatch:
        threads = self._fetch_threads()
        jobs: list[RawJob] = []
        max_posted = last_watermark

        # Process the most recent thread only
        if not threads:
            return RawJobBatch(source=JobSource.HACKERNEWS, jobs=[], new_watermark=max_posted)

        thread = threads[0]
        thread_id = thread.get("objectID")
        thread_date = thread.get("created_at") or thread.get("created_at_i")

        # Convert date to ISO
        thread_posted = self._safe_datetime(thread_date)

        # Skip if thread is older than watermark
        if last_watermark and thread_posted <= last_watermark:
            logger.info("HN thread %s already processed", thread_id)
            return RawJobBatch(source=JobSource.HACKERNEWS, jobs=[], new_watermark=max_posted)

        comment_ids = self._fetch_comments(int(thread_id))
        logger.info("HN: processing %d comments from thread %s", len(comment_ids), thread_id)

        # Process comments with a cap to keep runtime reasonable
        for comment_id in comment_ids[:500]:
            comment = self._fetch_comment(comment_id)
            if not comment or comment.get("text") is None:
                continue

            parsed = self._parse_job_comment(comment["text"])
            if not parsed:
                continue

            # Create external_id from comment id
            external_id = f"hn_{thread_id}_{comment_id}"
            salary_raw = parsed["salary_raw"] or self._extract_salary_from_description(
                parsed["description"]
            )
            if salary_raw:
                salary_raw = _truncate(salary_raw, MAX_SALARY_RAW_LEN)
            tags = []

            # Detect location country
            location = parsed["location"]
            country = None
            if location:
                loc_lower = location.lower()
                country_hints = {
                    "remote": None, "worldwide": None,
                    "usa": "US", "us": "US", "united states": "US", "sf": "US", "nyc": "US",
                    "uk": "GB", "london": "GB", "united kingdom": "GB",
                    "canada": "CA", "germany": "DE", "berlin": "DE",
                    "france": "FR", "spain": "ES", "netherlands": "NL",
                    "europe": "EU", "india": "IN", "australia": "AU", "brazil": "BR",
                }
                for hint, code in country_hints.items():
                    if hint in loc_lower:
                        country = code
                        break

            jobs.append(
                RawJob(
                    external_id=external_id,
                    source=JobSource.HACKERNEWS,
                    title=parsed["title"] or "Unknown Position",
                    description=parsed["description"],
                    location=location or "Remote",
                    country=country,
                    salary_raw=salary_raw,
                    # Salary is parsed from free text and may be USD, EUR, or
                    # GBP; leave the currency unset so the validator detects
                    # the symbol instead of forcing USD.
                    salary_currency=None,
                    # Free-text salary; leave the period unknown so the
                    # validator can detect hourly/annual from the text.
                    salary_type=SalaryType.UNKNOWN,
                    posted_at=self._safe_datetime(comment.get("time")),
                    url=f"https://news.ycombinator.com/item?id={comment_id}",
                    company=parsed["company"],
                    tags=tags,
                )
            )

        max_posted = thread_posted if not max_posted or thread_posted > max_posted else max_posted
        logger.info("HackerNews: fetched %d jobs", len(jobs))
        return RawJobBatch(source=JobSource.HACKERNEWS, jobs=jobs, new_watermark=max_posted)
