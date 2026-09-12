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
import logging
import re

import httpx

from src.ingestion.sources.base import BaseSource, SourceError
from src.schemas import JobSource, RawJob, RawJobBatch, SalaryType

logger = logging.getLogger(__name__)

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"
ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

SALARY_PATTERNS = [
    # $100k - $150k, $100K, $100k/year, etc.
    r"\$([\d,]+)\s*(?:k|K)?\s*(?:-|to|–)\s*\$?([\d,]+)\s*(?:k|K)?",
    r"\$([\d,]+)\s*(?:k|K)?\s*(?:/|per)?\s*(?:yr|year|annum)",
    # € numbers
    r"€([\d,]+)\s*(?:k|K)?\s*(?:-|to|–)\s*€?([\d,]+)\s*(?:k|K)?",
    # £ numbers
    r"£([\d,]+)\s*(?:k|K)?\s*(?:-|to|–)\s*£?([\d,]+)\s*(?:k|K)?",
]


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
        except Exception:
            return None

    @staticmethod
    def _parse_job_comment(text: str) -> dict | None:
        """Extract structured job info from an HN comment."""
        # First line typically: "CompanyName | Job Title | Location | $Salary" or
        # "[Company] | [Title] ([Location]) - $Salary"
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return None

        first_line = lines[0]

        # Try pipe-delimited format: Company | Title | Location | $Salary
        parts = [p.strip() for p in first_line.split("|")]
        if len(parts) >= 2:
            company = parts[0].strip("[] ")
            title = parts[1].strip("[] ")
            location = parts[2].strip() if len(parts) > 2 else None
            salary_raw = parts[3].strip() if len(parts) > 3 else None
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
                "title": m.group(1).strip(),
                "location": m.group(2).strip(),
                "company": m.group(3).strip(),
                "salary_raw": None,
                "description": text,
            }

        # Fallback: title is everything
        return {
            "title": first_line,
            "company": None,
            "location": None,
            "salary_raw": None,
            "description": text,
        }

    @staticmethod
    def _extract_salary(text: str) -> str | None:
        """Best-effort salary extraction from description."""
        for pattern in SALARY_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(0)
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
            salary_raw = parsed["salary_raw"] or self._extract_salary(parsed["description"])
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
                    salary_currency="USD",
                    salary_type=SalaryType.ANNUAL if salary_raw else SalaryType.UNKNOWN,
                    posted_at=self._safe_datetime(comment.get("time")),
                    url=f"https://news.ycombinator.com/item?id={comment_id}",
                    company=parsed["company"],
                    tags=tags,
                )
            )

        max_posted = thread_posted if not max_posted or thread_posted > max_posted else max_posted
        logger.info("HackerNews: fetched %d jobs", len(jobs))
        return RawJobBatch(source=JobSource.HACKERNEWS, jobs=jobs, new_watermark=max_posted)