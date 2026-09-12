# main.py
"""
Lumina Career ROI API — expanded with market intelligence endpoints.

Powers:
  - Skill ROI dashboard
  - Skill detail pages
  - Skill comparison tool
  - Career path/overlap analysis
  - Market overview for B2B personas
"""
import logging
import time

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.api.schemas import (
    CompareResponse,
    MarketOverviewResponse,
    RelatedSkillsResponse,
    SalaryDistributionResponse,
    SkillOverlapListResponse,
    SkillsListResponse,
)
from src.utils import api_data_loader as loader

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("lumina_api")

# --- Rate limiting ---
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# Initialize the FastAPI app
app = FastAPI(
    title="Lumina Career ROI API",
    description=(
        "Advanced labor market intelligence platform API. "
        "Provides ROI metrics, skill comparisons, market overviews, "
        "and salary distributions for technical skills."
    ),
    version="2.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_start_time = time.time()


# ============================================================
# SYSTEM ENDPOINTS
# ============================================================

@app.get("/api/v1/health", tags=["System"])
def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "message": "Lumina Career ROI API is operational",
        "version": "2.0.0",
    }


@app.get("/metrics", tags=["System"], include_in_schema=False)
@limiter.limit("10/minute")
def metrics(request: Request):
    """Basic metrics for monitoring."""
    return {"uptime_seconds": int(time.time() - _start_time)}


# ============================================================
# SKILLS ENDPOINTS (specific sub-routes BEFORE {skill_name} catch-all)
# ============================================================

@app.get("/api/v1/skills/roi", response_model=SkillsListResponse, tags=["Skills"])
@limiter.limit("100/minute")
def get_all_skills_roi(request: Request):
    """
    Returns the ROI metrics for all tracked skills, sorted by salary premium.
    Powers the 'Top Skills' dashboard view.
    """
    try:
        data = loader.get_single_skill_roi_data()
        return {"total_skills": len(data), "data": data}
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/skills", tags=["Skills"])
@limiter.limit("100/minute")
def get_skills_list(request: Request):
    """Returns the list of all available skill names (for autocomplete)."""
    try:
        return {"skills": loader.get_skills_list()}
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/skills/overlap", response_model=SkillOverlapListResponse, tags=["Skills"])
@limiter.limit("100/minute")
def get_skill_overlap(request: Request, limit: int = Query(20, ge=1, le=100)):
    """
    Returns the highest-ROI skill combinations.
    Powers the 'Career Paths & Combinations' view.
    """
    try:
        data = loader.get_skill_overlap_data(limit=limit)
        return {"total_combos": len(data), "data": data}
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/skills/compare", response_model=CompareResponse, tags=["Skills"])
@limiter.limit("100/minute")
def compare_skills(
    request: Request,
    skills: str = Query(..., description="Comma-separated skill names, e.g., python,aws,docker"),
):
    """
    Compares multiple skills side-by-side.
    Powers the 'Compare' view.
    """
    skill_names = [s.strip() for s in skills.split(",") if s.strip()]
    if not skill_names:
        raise HTTPException(status_code=400, detail="No skills provided for comparison.")

    data = loader.compare_skills(skill_names)
    return {"skills": data, "total": len(data)}


@app.get("/api/v1/skills/{skill_name}/related", response_model=RelatedSkillsResponse, tags=["Skills"])
@limiter.limit("100/minute")
def get_related(
    request: Request,
    skill_name: str,
    limit: int = Query(10, ge=1, le=20),
):
    """Returns related skills for a given skill based on co-occurrence."""
    related = loader.get_related_skills(skill_name, limit=limit)
    return {"skill": skill_name, "related": related}


@app.get("/api/v1/skills/{skill_name}/salary-distribution", response_model=SalaryDistributionResponse, tags=["Market"])
@limiter.limit("100/minute")
def get_salary_dist(request: Request, skill_name: str):
    """Returns the salary distribution buckets for a specific skill."""
    dist = loader.get_salary_distribution(skill_name)
    return {"skill": skill_name, "distribution": dist}


@app.get("/api/v1/skills/{skill_name}", response_model=dict, tags=["Skills"])
@limiter.limit("100/minute")
def get_specific_skill_roi(request: Request, skill_name: str):
    """
    Returns the ROI metrics for a specific skill, including related skills
    and salary distribution.
    Powers the 'Skill Detail' view.
    """
    skill_data = loader.get_skill_by_name(skill_name)
    if not skill_data:
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{skill_name}' not found in our labor market database.",
        )
    related = loader.get_related_skills(skill_name)
    salary_dist = loader.get_salary_distribution(skill_name)
    return {
        **skill_data,
        "related_skills": related,
        "salary_distribution": salary_dist,
    }


# ============================================================
# MARKET ENDPOINTS
# ============================================================

@app.get("/api/v1/market/overview", response_model=MarketOverviewResponse, tags=["Market"])
@limiter.limit("100/minute")
def get_market_overview(request: Request):
    """
    Returns broad market statistics: average salary, total jobs tracked,
    top skills by demand.
    Powers the B2B 'Market Intelligence' view.
    """
    try:
        return loader.get_market_overview()
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# TAXONOMY
# ============================================================

@app.get("/api/v1/taxonomy", tags=["System"])
@limiter.limit("100/minute")
def get_taxonomy_stats(request: Request):
    """Returns stats about the skills taxonomy."""
    from src.ingestion.skills_taxonomy import get_taxonomy_stats

    return get_taxonomy_stats()