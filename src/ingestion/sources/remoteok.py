# src/ingestion/sources/remoteok.py
"""
RemoteOK source adapter.

RemoteOK provides a free, keyless API for global remote tech jobs.
API: https://remoteok.com/api
"""
import logging

import httpx

from src.ingestion.sources.base import BaseSource, SourceError
from src.schemas import JobSource, RawJob, RawJobBatch, SalaryType

logger = logging.getLogger(__name__)

API_URL = "https://remoteok.com/api"


class RemoteOKSource(BaseSource):
    """Adapter for RemoteOK's job board API."""

    name = "remoteok"
    trust_rank = 5

    def _validate_config(self):
        # No credentials required
        return

    def fetch(self, last_watermark: str | None = None) -> RawJobBatch:
        try:
            response = httpx.get(API_URL, timeout=30, headers={"User-Agent": "LuminaCareerROI/1.0"})
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise SourceError(f"RemoteOK fetch failed: {exc}") from exc

        # The first element is metadata; the rest are jobs
        jobs_data = data[1:] if isinstance(data, list) and data else []

        jobs: list[RawJob] = []
        max_posted = last_watermark

        for item in jobs_data:
            if not isinstance(item, dict):
                continue

            external_id = str(item.get("id", ""))
            if not external_id:
                continue

            posted_at = self._safe_datetime(item.get("date"))
            # Incremental filter
            if last_watermark and posted_at <= last_watermark:
                continue

            # Track max watermark
            if max_posted is None or posted_at > max_posted:
                max_posted = posted_at

            salary_raw = None
            salary_min = item.get("salary_min")
            salary_max = item.get("salary_max")
            if salary_min or salary_max:
                if salary_min and salary_max:
                    salary_raw = f"${salary_min} - ${salary_max}"
                elif salary_min:
                    salary_raw = f"${salary_min}"
                elif salary_max:
                    salary_raw = f"${salary_max}"

            tags = [t for t in item.get("tags", []) if isinstance(t, str)]

            jobs.append(
                RawJob(
                    external_id=external_id,
                    source=JobSource.REMOTEOK,
                    title=self._clean_text(item.get("position", "")),
                    description=self._clean_text(item.get("description", "")),
                    location="Remote",
                    country=None,
                    salary_raw=salary_raw,
                    salary_currency="USD",
                    salary_type=SalaryType.ANNUAL,
                    posted_at=posted_at,
                    url=item.get("url"),
                    company=self._clean_text(item.get("company", "")),
                    tags=tags,
                )
            )

        logger.info("RemoteOK: fetched %d jobs", len(jobs))
        return RawJobBatch(source=JobSource.REMOTEOK, jobs=jobs, new_watermark=max_posted)