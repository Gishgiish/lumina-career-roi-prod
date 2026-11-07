# src/ingestion/sources/adzuna.py
"""
Adzuna source adapter.

Adzuna is a global job search engine with a free API tier (~500 req/month).
API: https://api.adzuna.com/v1/api/jobs/{country}/search/{page}
Requires an App ID and App Key (free registration).
"""
import logging

import httpx

from src.ingestion.sources.base import BaseSource
from src.schemas import JobSource, RawJob, RawJobBatch, SalaryType

logger = logging.getLogger(__name__)

# Adzuna country codes supported by the API
SUPPORTED_COUNTRIES = ["gb", "us", "de", "ca", "au", "in", "nl", "fr", "ie", "pl", "br", "at"]

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


class AdzunaSource(BaseSource):
    """Adapter for Adzuna's job search API."""

    name = "adzuna"
    trust_rank = 5

# Validate connection cofiguration and return an error if it's not set
    def _validate_config(self):
        if not self.config.get("app_id") or not self.config.get("app_key"):
            raise ValueError("Adzuna requires 'app_id' and 'app_key' config values")


# Fetch data from Adzuna, checking the watermark to reduce compute for unnecesary reloads of old data allready ingested
    def fetch(self, last_watermark: str | None = None) -> RawJobBatch:
        jobs: list[RawJob] = []
        max_posted = last_watermark

        for country in SUPPORTED_COUNTRIES:
            page = 1
            while page <= 5:  # Cap at 5 pages per country per run to stay within free tier @audit during production
                try:
                    response = httpx.get(
                        BASE_URL.format(country=country, page=page),
                        params={
                            "app_id": self.config["app_id"],
                            "app_key": self.config["app_key"],
                            "results_per_page": 50,
                            "content-type": "application/json",
                        },
                        timeout=30,
                    )
                    response.raise_for_status()
                    data = response.json()
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning("Adzuna: failed to fetch %s page %d: %s", country, page, exc)
                    break

                items = data.get("results", [])
                if not items:
                    break

                for item in items:
                    if not isinstance(item, dict):
                        continue

                    external_id = f"{country}_{item.get('id', '')}"
                    if not item.get("id"):
                        continue

                    # Adzuna returns created as "2025-06-01T10:00:00Z"
                    posted_at = self._safe_datetime(item.get("created"))

                    # Incremental filter
                    if last_watermark and posted_at <= last_watermark:
                        continue

                    if max_posted is None or posted_at > max_posted:
                        max_posted = posted_at

                    # Adzuna salary. Emit plain numeric ranges; the currency is
                    # supplied separately as an ISO code below. Do not prefix
                    # "$" here — it would make the parser guess USD for GBP,
                    # EUR, INR, and every other non-USD country.
                    salary_min = item.get("salary_min")
                    salary_max = item.get("salary_max")
                    salary_raw = None
                    if salary_min or salary_max:
                        if salary_min and salary_max:
                            salary_raw = f"{int(salary_min)} - {int(salary_max)}"
                        elif salary_min:
                            salary_raw = f"{int(salary_min)}"
                        elif salary_max:
                            salary_raw = f"{int(salary_max)}"

                    location = item.get("location", {}).get("display_name") or ""
                    # Extract country from the Adzuna location object
                    location_area = item.get("location", {}).get("area")
                    area_map = {
                        "United Kingdom": "GB",
                        "USA": "US",
                        "Germany": "DE",
                        "Canada": "CA",
                        "Australia": "AU",
                        "India": "IN",
                        "Netherlands": "NL",
                        "France": "FR",
                        "Ireland": "IE",
                        "Poland": "PL",
                        "Brazil": "BR",
                        "Austria": "AT",
                    }
                    country_code = area_map.get(location_area, country.upper())

                    url = item.get("redirect_url") or item.get("url")
                    tags = []
                    if item.get("category", {}).get("label"):
                        tags.append(item["category"]["label"])
                    if item.get("salary_is_predicted"):
                        tags.append("salary_predicted")

                    jobs.append(
                        RawJob(
                            external_id=external_id,
                            source=JobSource.ADZUNA,
                            title=self._clean_text(item.get("title", "")),
                            description=self._clean_text(item.get("description", "")),
                            location=location,
                            country=country_code,
                            salary_raw=salary_raw,
                            salary_currency=self._currency_for_country(country_code),
                            salary_type=SalaryType.ANNUAL if salary_raw else SalaryType.UNKNOWN,
                            posted_at=posted_at,
                            url=url,
                            company=self._clean_text(item.get("company", {}).get("display_name")),
                            tags=tags,
                        )
                    )

                count = data.get("count", 0)
                if len(items) < 50 or len(jobs) >= count:
                    break
                page += 1

        logger.info("Adzuna: fetched %d jobs", len(jobs))
        return RawJobBatch(source=JobSource.ADZUNA, jobs=jobs, new_watermark=max_posted)

    @staticmethod
    def _currency_for_country(country_code: str) -> str:
        """Map ISO country code to ISO 4217 currency."""
        currency_map = {
            "GB": "GBP", "US": "USD", "DE": "EUR", "CA": "CAD",
            "AU": "AUD", "IN": "INR", "NL": "EUR", "FR": "EUR",
            "IE": "EUR", "PL": "PLN", "BR": "BRL", "AT": "EUR",
        }
        return currency_map.get(country_code, "USD")
