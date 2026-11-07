# src/api/schemas.py
from pydantic import BaseModel, Field


class SkillROIResponse(BaseModel):
    """ROI metrics for a single skill."""

    skill: str = Field(..., description="The name of the technical skill")
    avg_salary: float = Field(..., description="Average expected salary for this skill (USD)")
    job_demand_count: int = Field(..., description="Number of job postings requiring this skill")
    salary_premium: float = Field(..., description="Salary premium vs market average (USD)")


class SkillOverlapResponse(BaseModel):
    """ROI metrics for a skill combination."""

    skill_combo: str = Field(..., description="Comma-separated skill combination")
    combo_avg_salary: float = Field(..., description="Average salary for this combo (USD)")
    combo_demand_count: int = Field(..., description="Number of jobs requiring this combo")
    combo_premium: float = Field(..., description="Salary premium for this combo (USD)")


class SkillDemandResponse(BaseModel):
    """Demand for a skill across all jobs, including salary-less postings."""

    skill: str = Field(..., description="The name of the technical skill")
    job_demand_count: int = Field(..., description="Number of jobs mentioning this skill")
    job_share: float = Field(..., description="Fraction of jobs-with-skills mentioning it")


class RelatedSkillResponse(BaseModel):
    """A related skill with co-occurrence count."""

    skill: str
    co_occurrence_count: int


class SalaryBucketResponse(BaseModel):
    """Salary distribution bucket."""

    skill: str
    salary_bucket: str
    job_count: int


class MarketOverviewResponse(BaseModel):
    """Market-level statistics."""

    metrics: dict[str, float | int | str]
    top_skills: list[SkillROIResponse]


class SkillsListResponse(BaseModel):
    """List of all skills with ROI data."""

    total_skills: int
    data: list[SkillROIResponse]


class SkillOverlapListResponse(BaseModel):
    """List of skill overlap combinations."""

    total_combos: int
    data: list[SkillOverlapResponse]


class SkillDemandListResponse(BaseModel):
    """List of skills ranked by demand across all jobs."""

    total_skills: int
    data: list[SkillDemandResponse]


class CompareResponse(BaseModel):
    """Comparison of multiple skills."""

    skills: list[SkillROIResponse]
    total: int


class RelatedSkillsResponse(BaseModel):
    """Related skills for a specific skill."""

    skill: str
    related: list[RelatedSkillResponse]


class SalaryDistributionResponse(BaseModel):
    """Salary distribution for a skill or globally."""

    skill: str | None = None
    distribution: list[SalaryBucketResponse]
