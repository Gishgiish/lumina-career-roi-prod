# src/ingestion/sources/remotive.py
"""
Remotive source adapter.

Remotive provides a free, keyless API for remote jobs.
API: https://remotive.com/api/remote-jobs
"""
import logging

import httpx

from src.ingestion.sources.base import BaseSource, SourceError
from src.schemas import JobSource, RawJob, RawJobBatch, SalaryType

logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"

# Map Remotive category slugs to job categories
CATEGORY_MAP = {
    "software-dev": "Software Development",
    "data": "Data",
    "product": "Product",
    "design": "Design",
    "devops": "DevOps",
    "marketing": "Marketing",
    "sales": "Sales",
    "customer-support": "Customer Support",
    "finance": "Finance",
    "hr": "Human Resources",
}


class RemotiveSource(BaseSource):
    """Adapter for Remotive's remote jobs API."""

    name = "remotive"
    trust_rank = 4

    def _validate_config(self):
        return

    def fetch(self, last_watermark: str | None = None) -> RawJobBatch:
        jobs: list[RawJob] = []
        max_posted = last_watermark
        page = 1

        while True:
            try:
                response = httpx.get(
                    API_URL,
                    params={"limit": 100, "page": page},
                    timeout=30,
                    headers={"User-Agent": "LuminaCareerROI/1.0"},
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                raise SourceError(f"Remotive fetch failed: {exc}") from exc

            items = data.get("jobs", [])
            if not items:
                break

            for item in items:
                if not isinstance(item, dict):
                    continue

                external_id = str(item.get("id", ""))
                if not external_id:
                    continue

                # Remotive uses a unix timestamp (epoch seconds)
                raw_time = item.get("publication_date")
                posted_at = self._safe_datetime(raw_time) if raw_time else None
                if posted_at and last_watermark and posted_at <= last_watermark:
                    continue

                # Track max watermark
                if posted_at and (max_posted is None or posted_at > max_posted):
                    max_posted = posted_at

                # Remotive salary comes as a single string like "$100k - $130k"
                salary_raw = item.get("salary") or None
                salary_type = SalaryType.ANNUAL if salary_raw else SalaryType.UNKNOWN

                category = item.get("category", "")
                tags_raw = [category] if category else []
                skills = item.get("tags", []) if isinstance(item.get("tags"), list) else []
                tags = tags_raw + [s for s in skills if isinstance(s, str)]

                location = item.get("candidate_required_location") or "Remote"
                country = None
                if location and location.lower() != "worldwide":
                    # Best-effort country extraction (simple heuristic)
                    loc = location.lower()
                    country_hints = {
                        "usa": "US", "united states": "US", "america": "US",
                        "uk": "GB", "united kingdom": "GB", "london": "GB",
                        "canada": "CA", "europe": "EU", "germany": "DE",
                        "france": "FR", "spain": "ES", "netherlands": "NL",
                        "australia": "AU", "india": "IN", "brazil": "BR",
                    }
                    for hint, code in country_hints.items():
                        if hint in loc:
                            country = code
                            break

                jobs.append(
                    RawJob(
                        external_id=external_id,
                        source=JobSource.REMOTIVE,
                        title=self._clean_text(item.get("title", "")),
                        description=self._clean_text(item.get("description", "")),
                        location=location,
                        country=country,
                        salary_raw=salary_raw,
                        salary_currency="USD",
                        salary_type=salary_type,
                        posted_at=posted_at or self._safe_datetime(None),
                        url=item.get("url"),
                        company=self._clean_text(item.get("company_name", "")),
                        tags=tags,
                    )
                )

            # Pagination: Remotive returns total_pages or just "page" count
            total = data.get("total", 0)
            if not items or len(jobs) >= total or page >= 10:
                break
            page += 1

        logger.info("Remotive: fetched %d jobs", len(jobs))
        return RawJobBatch(source=JobSource.REMOTIVE, jobs=jobs, new_watermark=max_posted)