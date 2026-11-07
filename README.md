# Lumina Career ROI

Labor-market intelligence **prototype** that estimates salary premiums for technical skills using job-posting data.

> **Project status:** working demo, pre-production data layer.
> The bundled demo runs on **synthetic seed data**. The live ingestion pipeline is implemented and the P0 data-path
> defects (currency conversion, deduplication, Gold hygiene, salary-less handling) are fixed, but there is no
> verified real ingestion run yet and no scheduler or data-freshness signal. See
> [`CODEBASE_STATUS.md`](CODEBASE_STATUS.md) for the verified audit, evidence, and remediation plan.

## What it does

- Maintains a curated taxonomy of **285 skills** with **293 aliases**.
- Ships **8 job-source adapters** (6 keyless, 2 key-gated).
- Implements a medallion pipeline: Bronze NDJSON → Silver Parquet → 7 Gold marts.
- Serves the marts through a FastAPI layer with 11 public endpoints.
- Renders a Next.js 16 dashboard with skill detail, compare, and career-path views.

**Naming note:** the product name says “ROI”, but the current implementation computes **salary premium versus the
overall average salary**. There is no training-cost input or true return-on-investment calculation yet.

## Quick start

### Prerequisites

- Python 3.12+
- `uv`
- Node.js 20+
- Docker (optional, for the full compose stack)

### 1. Install dependencies

```bash
uv sync
cd frontend && npm install
```

### 2. Generate the synthetic demo data

```bash
make seed
```

This writes 800 synthetic jobs to `data/silver/` and builds all seven Gold marts through the **same builders the
pipeline uses** (`src/transformation/gold.py::build_gold_marts`). It **does not** exercise the live ingestion,
deduplication, or skill-extraction code paths.

### 3. Start the API

```bash
make api
# or: PYTHONPATH=. uv run uvicorn main:app --reload --port 8000
```

### 4. Start the frontend

```bash
make frontend
# or: cd frontend && npm run dev
```

Open http://localhost:3000.

### 5. Run the checks

```bash
make test
make lint
cd frontend && npm run lint && npm run build
```

Current status: 135 backend tests pass, `uv run ruff check src/ scripts/ tests/` is clean, and frontend
lint/build pass.

### 6. Run against an isolated data root (optional)

By default the pipeline reads and writes `./data` and advances `./configs/ingestion_state.json`. To keep scratch or
live-ingestion runs away from the demo, export both overrides **before** starting Python (they are read at import
time):

```bash
export LUMINA_DATA_DIR=/tmp/opencode/lumina-scratch
export LUMINA_STATE_FILE=/tmp/opencode/lumina-scratch/ingestion_state.json
make seed     # or: make ingest
```

- `LUMINA_DATA_DIR` relocates `bronze/`, `silver/`, `gold/`, and `quarantine/`.
- `LUMINA_STATE_FILE` relocates the per-source watermark file.
- Absolute paths are used as-is; relative paths resolve against the repository root; `~` is expanded.
- The ETL process and the API process must use the **same** exported values, or the API will keep serving the default
  demo marts.

## Architecture as built

```
8 source adapters
      │
      ▼
validator  ──►  Bronze NDJSON
      │              │
      └──► Quarantine│
                     ▼
              Silver transform
              (dedup + skills extraction;
               keeps salary-less rows for demand)
                     │
                     ▼
              Gold transforms
              (7 parquet marts)
                     │
                     ▼
                 FastAPI
                     │
                     ▼
               Next.js frontend
```

Notes:

- The architecture diagram above is the **implemented** path, not an aspirational one.
- PostgreSQL is present in `docker-compose.yml` but **no application code uses it**.
- No scheduler exists in the repository. Data freshness depends on a human running `make ingest`.
- `make seed` bypasses Bronze, validation, deduplication, and skills extraction entirely.

## Data sources

| Source | Auth | Scope | Salary data | Verified caveat |
|---|---|---|---|---|
| Adzuna | API key | 12 countries | Yes | Currency is supplied as an ISO code from the country; conversion uses static FY2025/26 FX rates |
| RemoteOK | None | Global remote | Sometimes | — |
| Remotive | None | Global remote | Sometimes | — |
| Arbeitnow | None | Germany | No | Rows are kept for demand statistics only; salary marts exclude them |
| USAJobs | API key | US federal | Yes | — |
| Greenhouse | None | 20 curated boards | Usually no | Public API does not provide salary; retained for demand only |
| Lever | None | Curated boards | Best-effort | Salary parsed from description text only |
| HackerNews | None | “Who is hiring?” threads | Best-effort | Comment parsing is heuristic |

Copy `.env.sample` to `.env` to provide API keys and R2 credentials. Without keys, the six keyless sources are still
registered; the two key-gated sources are skipped.

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /api/v1/health` | Health check (no data-freshness information) |
| `GET /api/v1/skills/roi` | All skills with salary/ROI metrics |
| `GET /api/v1/skills` | Skill names for autocomplete |
| `GET /api/v1/skills/{skill}` | Skill detail + related skills + salary distribution |
| `GET /api/v1/skills/overlap` | Skill-set combinations ranked by premium |
| `GET /api/v1/skills/demand` | Skill demand across all jobs, including salary-less postings |
| `GET /api/v1/skills/compare?skills=a,b,c` | Side-by-side comparison |
| `GET /api/v1/skills/{skill}/related` | Related skills by co-occurrence |
| `GET /api/v1/skills/{skill}/salary-distribution` | Salary buckets |
| `GET /api/v1/market/overview` | Market totals and top skills |
| `GET /api/v1/taxonomy` | Taxonomy statistics |

`GET /metrics` also exists but is excluded from the OpenAPI schema.

## Data and demo behavior

- `data/` is gitignored; it is generated locally.
- The bundled Gold marts are regenerated with `make seed` (current on-disk copy: **2026-11-07**).
- Seed and pipeline share one Gold implementation (`build_gold_marts`), so the demo uses production Gold
  semantics: seven market metrics (including `jobs_with_salary` and `salary_coverage_rate`), related pairs
  filtered at `>= 2`, and a separate demand mart that counts salary-less postings.
- Salary-less postings are retained in Silver (`has_salary = False`) for demand statistics. Salary-based marts
  (`single_skill_roi_mart`, `skill_overlap_mart`, `salary_distribution_mart`, `top_skills_mart`) cover only
  salaried jobs; `market_overview_mart` reports the resulting coverage rate.
- No live pipeline artifacts exist in the repository beyond a legacy three-row Bronze file and its quarantine file.
- The live pipeline has no scheduler, no mart versioning, and no “data as of” timestamp.

## Testing

- Backend: 11 test files, 135 tests passing.
- Covered: Gold builders, Silver normalization helpers, path resolution, validation, deduplication, the seed
  script, and the API surface.
- Not covered: `orchestrator.py` and six of the eight source adapters (Adzuna and a HackerNews currency-contract test
  have coverage).
- Gold builders, path resolution, and the seed script have dedicated unit/subprocess tests (`test_gold.py`,
  `test_paths.py`, `test_seed.py`).
- Frontend: no test tooling or test files.
- CI: pytest + ruff for backend; ESLint + production build for frontend. No coverage gate, backend type check,
  Docker smoke test, or scheduled freshness check.
- `tests/test_r2.py` performs a live Cloudflare R2 call during pytest collection and has no assertions.

## Project structure

```
main.py                        FastAPI application
src/
  schemas.py                   Canonical RawJob contract
  api/schemas.py               API response models
  ingestion/
    sources/                   8 adapters + BaseSource + registry
    validator.py               Salary/currency parsing, title-only validity gate
    skills_taxonomy.py         285-skill taxonomy and keyword extractor
  transformation/
    dedup.py                   Exact + fuzzy deduplication
    silver.py                  Bronze → Silver
    gold.py                    Silver → 7 Gold marts
  utils/
    paths.py                   Data/state path resolution (env overrides)
    api_data_loader.py         Per-request parquet loader
scripts/
  orchestrator.py              Prefect flow (no deployment/schedule in repo)
  seed_data.py                 Synthetic demo-data generator
  sync_to_r2.py                Cloudflare R2 upload
  run_*.py                     Thin/legacy wrappers
frontend/src/app/              Dashboard, skill detail, compare, career paths, B2B pages
tests/                         Backend tests
```

## Known limitations

The full, evidence-based list is in [`CODEBASE_STATUS.md`](CODEBASE_STATUS.md). The highest-impact remaining items are:

- The demo is synthetic; no verified real ingestion run exists yet (Step 4).
- Currency conversion uses static FY2025/26 FX rates; there is no live rate refresh.
- Skill extraction is keyword/heuristic, so it has false positives and misses.
- Salary-based marts cover only postings with a parseable salary; the seed demo coverage is 87.5%, and real
  coverage depends on the source mix.
- There is no scheduler or data-freshness signal; `make ingest` is manual.
- The B2B pages are static copy with hardcoded statistics; “Book a Demo” links back to the same page.
- PostgreSQL is unused, and there is no authentication or personalization.
- `tests/test_r2.py` performs a live Cloudflare R2 call with no assertions.

## Documentation

- [`README.md`](README.md) — this file: setup and expected behavior.
- [`CODEBASE_STATUS.md`](CODEBASE_STATUS.md) — verified status, findings, evidence, corrections, and next steps.
