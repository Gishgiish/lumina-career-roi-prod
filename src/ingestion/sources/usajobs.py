# src/ingestion/sources/usajobs.py
"""
USAJobs source adapter.

USAJobs is the US federal government's job board, offering a free API.
API: https://data.usajobs.gov/api/search
Requires an API key (free) and an email/User-Agent header.
"""
import logging

import httpx

from src.ingestion.sources.base import BaseSource
from src.schemas import JobSource, RawJob, RawJobBatch, SalaryType

logger = logging.getLogger(__name__)

API_URL = "https://data.usajobs.gov/api/search"


class USAJobsSource(BaseSource):
    """Adapter for the USAJobs.gov public API."""

    name = "usajobs"
    trust_rank = 5

    def _validate_config(self):
        if not self.config.get("api_key"):
            raise ValueError("USAJobs requires 'api_key' config value")

    def fetch(self, last_watermark: str | None = None) -> RawJobBatch:
        jobs: list[RawJob] = []
        max_posted = last_watermark
        page = 1

        while page <= 10:  # Cap at 10 pages (500 results) per run
            try:
                response = httpx.get(
                    API_URL,
                    params={
                        "ResultsPerPage": 50,
                        "Page": page,
                        "SortField": "PositionEndDate",
                    },
                    headers={
                        "Host": "data.usajobs.gov",
                        "User-Agent": "gishnora@gmail.com",
                        "Authorization-Key": self.config["api_key"],
                    },
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logger.warning("USAJobs: failed to fetch page %d: %s", page, exc)
                break

            result_items = data.get("SearchResult", {}).get("SearchResultItems", [])
            if not result_items:
                break

            for item in result_items:
                match = item.get("MatchedObjectDescriptor", {})
                if not match:
                    continue

                external_id = str(item.get("MatchedObjectId", ""))
                if not external_id:
                    continue

                # USAJobs gives "PositionEndDate" and "PositionStartDate"
                posted_at = self._safe_datetime(match.get("PositionStartDate"))

                # Incremental filter
                if last_watermark and posted_at <= last_watermark:
                    continue

                if max_posted is None or posted_at > max_posted:
                    max_posted = posted_at

                # Salary from PositionRemuneration
                positions = match.get("PositionRemuneration", [])
                salary_raw = None
                salary_currency = "USD"
                if positions:
                    salaries = []
                    for pos in positions:
                        if pos.get("MinimumRange") and pos.get("MaximumRange"):
                            salaries.append(
                                f"${int(float(pos['MinimumRange']))} - ${int(float(pos['MaximumRange']))}"
                            )
                        elif pos.get("MinimumRange"):
                            salaries.append(f"${int(float(pos['MinimumRange']))}")
                    if salaries:
                        salary_raw = "; ".join(salaries)

                # Location
                locations = match.get("PositionLocation", [])
                location_str = ", ".join(
                    loc.get("LocationName", "") for loc in locations
                ) or "USA"
                country = "US"

                # Keywords
                qual = match.get("QualificationSummary", {})
                tags = []
                for kw in match.get("JobCategory", []):
                    tags.append(kw.get("Name", ""))

                description = " ".join([
                    match.get("JobSummary", "") or "",
                    qual.get("QualificationSummary", "") or "",
                    qual.get("SubstitutionStatement", "") or "",
                ])

                jobs.append(
                    RawJob(
                        external_id=external_id,
                        source=JobSource.USAJOBS,
                        title=self._clean_text(match.get("PositionTitle", "")),
                        description=self._clean_text(description),
                        location=location_str,
                        country=country,
                        salary_raw=salary_raw,
                        salary_currency=salary_currency,
                        salary_type=SalaryType.ANNUAL if salary_raw else SalaryType.UNKNOWN,
                        posted_at=posted_at,
                        url=match.get("PositionURI"),
                        company="US Federal Government",
                        tags=tags,
                    )
                )

            total = data.get("SearchResult", {}).get("SearchResultCountAll", 0)
            if len(result_items) < 50 or len(jobs) >= total:
                break
            page += 1

        logger.info("USAJobs: fetched %d jobs", len(jobs))
        return RawJobBatch(source=JobSource.USAJOBS, jobs=jobs, new_watermark=max_posted)