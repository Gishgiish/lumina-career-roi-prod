# src/ingestion/sources/greenhouse.py
"""
Greenhouse ATS source adapter.

Greenhouse exposes public job board APIs for companies using their ATS.
Each company has its own board: https://boards-api.greenhouse.io/v1/boards/{company}/jobs

We query a curated list of well-known tech companies that use Greenhouse.
"""
import logging

import httpx

from src.ingestion.sources.base import BaseSource
from src.schemas import JobSource, RawJob, RawJobBatch, SalaryType

logger = logging.getLogger(__name__)

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"

# Known companies using Greenhouse (can be extended)
GREENHOUSE_COMPANIES = [
    "airbnb",
    "spotify",
    "instacart",
    "mercadolibre",
    "stripe",
    "lyft",
    "coinbase",
    "duolingo",
    "datadog",
    "mongodb",
    "dropbox",
    "doordash",
    "chime",
    "gusto",
    "reddit",
    "pinterest",
    "etsy",
    "shopify",
    "wise",
    "confluent",
]


class GreenhouseSource(BaseSource):
    """Adapter for Greenhouse ATS public job boards."""

    name = "greenhouse"
    trust_rank = 4

    def __init__(self, config: dict | None = None):
        config = config or {}
        # Allow custom company list via config
        self.companies = config.get("companies", GREENHOUSE_COMPANIES)
        super().__init__(config)

    def _validate_config(self):
        return

    def fetch(self, last_watermark: str | None = None) -> RawJobBatch:
        jobs: list[RawJob] = []
        max_posted = last_watermark

        for company in self.companies:
            try:
                response = httpx.get(
                    BASE_URL.format(company=company),
                    params={"content": "true", "per_page": 100},
                    timeout=30,
                    headers={"User-Agent": "LuminaCareerROI/1.0"},
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.warning("Greenhouse: failed to fetch %s: %s", company, exc)
                continue

            for item in data.get("jobs", []):
                if not isinstance(item, dict):
                    continue

                external_id = f"{company}_{item.get('id', '')}"
                if not item.get("id"):
                    continue

                posted_at = self._safe_datetime(item.get("updated_at"))
                # Incremental filter
                if last_watermark and posted_at <= last_watermark:
                    continue

                if max_posted is None or posted_at > max_posted:
                    max_posted = posted_at

                location_obj = item.get("location", {}) or {}
                location_name = location_obj.get("name") or "Remote"
                location_data = []
                if location_name:
                    # Location is often "City, State, Country" or "Remote (US)"
                    loc_lower = location_name.lower()
                    country = None
                    country_hints = {
                        "uk": "GB", "united kingdom": "GB", "london": "GB",
                        "usa": "US", "us": "US", "united states": "US",
                        "remote": None, "germany": "DE", "berlin": "DE",
                        "france": "FR", "spain": "ES", "canada": "CA",
                        "netherlands": "NL", "india": "IN", "australia": "AU",
                    }
                    for hint, code in country_hints.items():
                        if hint in loc_lower:
                            country = code
                            break
                    location_data = [location_name, country]

                # Greenhouse doesn't provide salary ranges in the public API
                salary_raw = None
                if item.get("salary_min") or item.get("salary_max"):
                    salary_raw = f"${item.get('salary_min')} - ${item.get('salary_max')}"

                jobs.append(
                    RawJob(
                        external_id=external_id,
                        source=JobSource.GREENHOUSE,
                        title=self._clean_text(item.get("title", "")),
                        description=self._clean_text(item.get("content", "")),
                        location=location_data[0],
                        country=location_data[1] if len(location_data) > 1 else None,
                        salary_raw=salary_raw,
                        salary_currency="USD",
                        salary_type=SalaryType.ANNUAL if salary_raw else SalaryType.UNKNOWN,
                        posted_at=posted_at,
                        url=item.get("absolute_url"),
                        company=company,
                        tags=[],
                    )
                )

        logger.info("Greenhouse: fetched %d jobs", len(jobs))
        return RawJobBatch(source=JobSource.GREENHOUSE, jobs=jobs, new_watermark=max_posted)