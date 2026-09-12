# src/schemas.py
"""
Canonical data schemas for Lumina Career ROI.

These schemas define the unified "RawJob" record that all source adapters
must produce, regardless of the source API's native format. This is the
single source of truth for the Bronze layer.
"""
from enum import Enum

from pydantic import BaseModel, Field


class JobSource(str, Enum):
    """All supported job board sources."""

    ADZUNA = "adzuna"
    REMOTEOK = "remoteok"
    REMOTIVE = "remotive"
    ARBEITNOW = "arbeitnow"
    USAJOBS = "usajobs"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    HACKERNEWS = "hackernews"


class SalaryType(str, Enum):
    """How the salary is expressed in the source."""

    ANNUAL = "annual"
    HOURLY = "hourly"
    MONTHLY = "monthly"
    UNKNOWN = "unknown"


class RawJob(BaseModel):
    """
    Canonical raw job record after source adapter normalization.

    Every source adapter MUST return a list of these objects. Field-level
    details:

    - `external_id`: The job's ID in the source system (dedup key component)
    - `source`: Which job board API this came from
    - `title`: Normalized/cleaned job title
    - `description`: Full job description text (used for skills extraction)
    - `location`: Best-effort location string (city, state, remote, etc.)
    - `country`: ISO 3166-1 alpha-2 code when known, else None
    - `salary_raw`: Unparsed salary string exactly as the source provided
    - `salary_currency`: ISO 4217 currency code (e.g., USD, EUR, GBP)
    - `salary_type`: hourly vs annual vs monthly
    - `posted_at`: ISO timestamp the job was posted (used for watermarks)
    - `url`: Link to the original job posting
    - `company`: Employer/company name
    - `tags`: Source-provided skill tags/labels (if any)
    """

    external_id: str = Field(..., description="Job ID in the source system")
    source: JobSource = Field(..., description="Source job board API")
    title: str = Field(..., description="Job title")
    description: str = Field(..., description="Full job description text")
    location: str | None = Field(None, description="Location string")
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code")
    salary_raw: str | None = Field(None, description="Raw salary string from source")
    salary_currency: str | None = Field(None, description="ISO 4217 currency code")
    salary_type: SalaryType = Field(
        SalaryType.UNKNOWN, description="Annual, hourly, or monthly"
    )
    posted_at: str = Field(..., description="ISO timestamp the job was posted")
    url: str | None = Field(None, description="Link to original job posting")
    company: str | None = Field(None, description="Employer name")
    tags: list[str] = Field(default_factory=list, description="Source-provided tags")

    @property
    def dedup_key(self) -> str:
        """A best-effort key for initial exact-match deduplication."""
        norm_title = self.title.lower().strip()
        norm_company = (self.company or "").lower().strip()
        norm_location = (self.location or "").lower().strip()
        return f"{norm_title}|{norm_company}|{norm_location}"


class RawJobBatch(BaseModel):
    """A batch of raw jobs fetched from a single source in one run."""

    source: JobSource
    jobs: list[RawJob]
    new_watermark: str | None = Field(
        None, description="New high-watermark timestamp for incremental fetching"
    )