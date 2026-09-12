# src/ingestion/sources/lever.py
"""
Lever ATS source adapter.

Lever exposes public job board APIs for companies using their ATS.
Each company has its own board: https://api.lever.co/v0/postings/{company}

We query a curated list of well-known tech companies that use Lever.
"""
import logging

import httpx

from src.ingestion.sources.base import BaseSource
from src.schemas import JobSource, RawJob, RawJobBatch, SalaryType

logger = logging.getLogger(__name__)

BASE_URL = "https://api.lever.co/v0/postings/{company}?mode=json"

# Known companies using Lever (can be extended)
LEVER_COMPANIES = [
    "netflix",
    "notion",
    "buffer",
    "atlassian",
    "carta",
    "gong",
    "intercom",
    "brex",
    "quora",
    "deel",
    "calendly",
    "lattice",
    "n26",
    "loom",
    "figma",
    "vanta",
    "chime",
    "ironclad",
    "tines",
    "uddle",
]


class LeverSource(BaseSource):
    """Adapter for Lever ATS public job boards."""

    name = "lever"
    trust_rank = 4

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.companies = config.get("companies", LEVER_COMPANIES)
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
                    timeout=30,
                    headers={"User-Agent": "LuminaCareerROI/1.0"},
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.warning("Lever: failed to fetch %s: %s", company, exc)
                continue

            if not isinstance(data, list):
                continue

            for item in data:
                if not isinstance(item, dict):
                    continue

                external_id = f"{company}_{item.get('id', '')}"
                if not item.get("id"):
                    continue

                posted_at = self._safe_datetime(item.get("createdAt"))
                # Incremental filter
                if last_watermark and posted_at <= last_watermark:
                    continue

                if max_posted is None or posted_at > max_posted:
                    max_posted = posted_at

                location = item.get("categories", {}).get("location") or "Remote"
                country = None
                if location and location.lower() not in ("remote", "worldwide"):
                    loc_lower = location.lower()
                    country_hints = {
                        "usa": "US", "us": "US", "united states": "US",
                        "uk": "GB", "united kingdom": "GB", "london": "GB",
                        "canada": "CA", "germany": "DE", "berlin": "DE",
                        "france": "FR", "spain": "ES", "netherlands": "NL",
                        "india": "IN", "australia": "AU", "brazil": "BR",
                        "europe": "EU",
                    }
                    for hint, code in country_hints.items():
                        if hint in loc_lower:
                            country = code
                            break

                # Lever salary is usually embedded in description as unstructured text
                description = self._clean_text(item.get("descriptionPlain", ""))
                salary_raw = None
                if "salary" in description.lower():
                    import re
                    match = re.search(
                        r"\$([\d,]+)\s*(?:k|K)?\s*(?:-|to|–)\s*\$?([\d,]+)\s*(?:k|K)?",
                        description,
                    )
                    if match:
                        salary_raw = match.group(0)

                tags = [
                    t
                    for t in (item.get("tags", []) or [])
                    if isinstance(t, str)
                ]
                if item.get("categories", {}).get("commitment"):
                    tags.append(item["categories"]["commitment"])
                if item.get("categories", {}).get("team"):
                    tags.append(item["categories"]["team"])

                jobs.append(
                    RawJob(
                        external_id=external_id,
                        source=JobSource.LEVER,
                        title=self._clean_text(item.get("text", "")),
                        description=description,
                        location=location,
                        country=country,
                        salary_raw=salary_raw,
                        salary_currency="USD",
                        salary_type=SalaryType.ANNUAL if salary_raw else SalaryType.UNKNOWN,
                        posted_at=posted_at,
                        url=item.get("hostedUrl"),
                        company=company,
                        tags=tags,
                    )
                )

        logger.info("Lever: fetched %d jobs", len(jobs))
        return RawJobBatch(source=JobSource.LEVER, jobs=jobs, new_watermark=max_posted)