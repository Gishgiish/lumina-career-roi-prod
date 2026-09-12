# src/ingestion/sources/arbeitnow.py
"""
Arbeitnow source adapter.

Arbeitnow provides a free, keyless API for German tech jobs.
API: https://www.arbeitnow.com/api/job-board-api
"""
import logging

import httpx

from src.ingestion.sources.base import BaseSource, SourceError
from src.schemas import JobSource, RawJob, RawJobBatch, SalaryType

logger = logging.getLogger(__name__)

API_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowSource(BaseSource):
    """Adapter for Arbeitnow's German job board API."""

    name = "arbeitnow"
    trust_rank = 3

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
                    params={"page": page},
                    timeout=30,
                    headers={"User-Agent": "LuminaCareerROI/1.0"},
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                raise SourceError(f"Arbeitnow fetch failed: {exc}") from exc

            items = data.get("data", [])
            if not items:
                break

            for item in items:
                if not isinstance(item, dict):
                    continue

                external_id = str(item.get("slug", ""))
                if not external_id:
                    continue

                # Arbeitnow provides created_at as a unix timestamp
                posted_at = self._safe_datetime(item.get("created_at"))

                if posted_at and last_watermark and posted_at <= last_watermark:
                    continue

                if posted_at and (max_posted is None or posted_at > max_posted):
                    max_posted = posted_at

                # Arbeitnow has no salary data
                location = item.get("location", "") or item.get("city", "") or "Germany"
                tags = [t for t in item.get("tags", []) if isinstance(t, str)]

                jobs.append(
                    RawJob(
                        external_id=external_id,
                        source=JobSource.ARBEITNOW,
                        title=self._clean_text(item.get("title", "")),
                        description=self._clean_text(item.get("description", "")),
                        location=location,
                        country="DE",
                        salary_raw=None,
                        salary_currency="EUR",
                        salary_type=SalaryType.UNKNOWN,
                        posted_at=posted_at or self._safe_datetime(None),
                        url=item.get("url"),
                        company=self._clean_text(item.get("company_name", "")),
                        tags=tags,
                    )
                )

            # Pagination via "links" / "meta"
            meta = data.get("meta", {})
            next_page = meta.get("next")
            if not next_page or page >= 10:
                break
            page += 1

        logger.info("Arbeitnow: fetched %d jobs", len(jobs))
        return RawJobBatch(source=JobSource.ARBEITNOW, jobs=jobs, new_watermark=max_posted)