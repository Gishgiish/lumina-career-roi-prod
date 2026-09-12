# Lumina Career ROI

**Labor market intelligence platform** that quantifies the financial return on investment (ROI) of technical skills. Built for career optimizers, L&D directors, and educators.

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- Docker (optional, for full stack)
- `uv` package manager

### 1. Install dependencies
```bash
uv sync
cd frontend && npm install
```

### 2. Generate seed data (so the product works out-of-the-box)
```bash
make seed
```

### 3. Start the backend API
```bash
make api
# or: PYTHONPATH=. uv run uvicorn main:app --reload --port 8000
```

### 4. Start the frontend
```bash
make frontend
# or: cd frontend && npm run dev
```

Open http://localhost:3000

### 5. Run tests
```bash
make test
```

## 🏗️ Architecture

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Adzuna API  │ │  RemoteOK    │ │  Remotive    │ │  Arbeitnow   │
│  (free tier) │ │  (keyless)   │ │  (keyless)   │ │  (keyless)   │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │                │
┌──────▼───────┐ ┌──────▼───────┐ ┌──────▼───────┐ ┌──────▼───────┐
│ AdzunaSource │ │ RemoteOKSrc  │ │ RemotiveSrc  │ │ ArbeitnowSrc │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       └────────────┬───┴────────────────┴───┬────────────┘
                    ▼                        ▼
           ┌───────────────┐         ┌───────────────┐
           │  BRONZE       │         │   QUARANTINE  │
           │  raw NDJSON   │         │   rejects     │
           └───────┬───────┘         └───────────────┘
                   ▼
           ┌───────────────┐
           │  SILVER       │  ← dedup (fuzzy), salary/currency
           │  clean parquet│    normalization, skills extraction
           └───────┬───────┘
                   ▼
           ┌───────────────┐         ┌───────────────────────┐
           │  GOLD         │         │  PostgreSQL           │
           │  ROI marts    │         │  users, saved skills, │
           │  (parquet)    │         │  career paths (new)   │
           └───────┬───────┘         └───────────┬───────────┘
                   ▼                            │
           ┌───────────────┐                    │
           │  FastAPI      │◄───────────────────┘
           │  (expanded)   │
           └───────┬───────┘
                   ▼
           ┌───────────────┐
           │  Next.js 16   │
           │  (multi-page) │
           └───────────────┘
```

## 📊 Data Sources

| Source | Auth | Coverage | Salary? |
|---|---|---|---|
| **Adzuna** | API key (free) | US/UK/DE/CA/AU/IN/NL etc. | ✅ |
| **RemoteOK** | None | Global remote | ✅ |
| **Remotive** | None | Global remote | ⚠️ |
| **Arbeitnow** | None | Germany tech | ❌ |
| **USAJobs** | API key (free) | US federal | ✅ |
| **Greenhouse** | None | Global ATS | ⚠️ |
| **Lever** | None | Global ATS | ⚠️ |
| **HackerNews** | None | Global | ✅ |

### Setting up API keys (optional)
Copy `.env.sample` to `.env` and add:
- `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` — https://developer.adzuna.com/
- `USAJOBS_API_KEY` — https://developer.usajobs.gov/

Without keys, the keyless sources (RemoteOK, Remotive, Arbeitnow, Greenhouse, Lever, HackerNews) still work.

## 🔌 API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/v1/health` | Health check |
| `GET /api/v1/skills/roi` | All skills with ROI metrics |
| `GET /api/v1/skills` | List of all skill names |
| `GET /api/v1/skills/{skill}` | Skill detail + related + salary dist |
| `GET /api/v1/skills/overlap` | Skill combinations with ROI |
| `GET /api/v1/skills/compare?skills=a,b,c` | Side-by-side comparison |
| `GET /api/v1/skills/{skill}/related` | Related skills |
| `GET /api/v1/skills/{skill}/salary-distribution` | Salary buckets |
| `GET /api/v1/market/overview` | Market statistics |
| `GET /api/v1/taxonomy` | Skills taxonomy stats |

## 🧪 Testing

```bash
make test
# or: PYTHONPATH=. uv run pytest tests/ -v
```

## 🛠️ Development Commands

```bash
make up        # Start all services (Docker Compose)
make down      # Stop all services
make seed      # Generate seed data
make test      # Run backend tests
make lint      # Run ruff lint
make ingest    # Run multi-source ingestion pipeline
make api       # Start backend locally
make frontend  # Start frontend locally
```

## 📁 Project Structure

```
├── main.py                    # FastAPI application
├── src/
│   ├── schemas.py             # Canonical data schemas
│   ├── api/                   # API schemas
│   ├── ingestion/
│   │   ├── sources/           # 8 source adapters
│   │   ├── skills_taxonomy.py # ~300 skill taxonomy
│   │   └── validator.py       # Data quality enforcement
│   ├── transformation/
│   │   ├── dedup.py           # Fuzzy deduplication
│   │   ├── silver.py          # Bronze → Silver
│   │   └── gold.py            # Silver → Gold marts
│   └── utils/                 # Paths, data loaders
├── scripts/
│   ├── orchestrator.py        # Prefect pipeline
│   ├── seed_data.py           # Seed data generator
│   └── sync_to_r2.py          # Cloudflare R2 sync
├── frontend/                  # Next.js 16 app
│   └── src/app/
│       ├── page.tsx           # Dashboard
│       ├── skills/[skill]/    # Skill detail
│       ├── compare/           # Skill comparison
│       ├── career-paths/      # Skill combos
│       ├── business/          # B2B L&D page
│       └── education/         # B2B educator page
└── tests/                     # Backend test suite
```

## 🎯 Personas

1. **Career Optimizer (B2C)** — Junior/mid-level developers maximizing earning potential
2. **L&D Director (B2B)** — Corporate training leaders justifying budgets
3. **Bootcamp/Educator (B2B)** — Institutions designing data-driven curricula