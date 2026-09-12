# 📋 Lumina Career ROI — Codebase Audit Plan

> **Status:** DRAFT — awaiting approval
> **Prepared by:** Cline (acting Senior SWE / Product Lead)
> **Repo:** `lumina-career-roi-prod` @ `70aafbe` (`main`)
> **Date:** 2026-09-10
> **Estimated duration:** 7–9 engineering days of focused audit work

---

## 1. Purpose & Objectives

Audit the `lumina-career-roi-prod` codebase end-to-end and produce:

1. An **honest baseline** of the current state: what works, what's broken, what's aspirational.
2. A **severity-ranked findings report** (Impact × Likelihood × Effort) that a product manager and an engineer can both act on.
3. A **staged remediation roadmap** (now / next 30 days / next quarter) tied to the three product personas.
4. This **living playbook** so every step I take is visible, repeatable, and verifiable by you.

### Personas driving the audit lens
| Persona | Product need | What the audit must protect |
|---|---|---|
| Career Optimizer (B2C) | Trustworthy salary/ROI data | Data correctness, API speed/reliability |
| L&D Director (B2B) | Budget justification via market intel | Market marts, business pages, data freshness |
| Bootcamp/Educator (B2B) | Data-driven curriculum design | Taxonomy, skill detail, comparison flows |

---

## 2. Recon Summary (already performed — verified facts)

> Everything below was confirmed by reading the code and running read-only commands. No files were modified.

| Item | Verified fact | Evidence |
|---|---|---|
| Stack | Python 3.12, FastAPI, Polars, Prefect, duckdb, rapidfuzz, slowapi, uv; Next.js 16.2 / React 19.2 / Tailwind 4 / TanStack Query | `pyproject.toml`, `frontend/package.json` |
| Git history | **Exactly 1 commit** (`70aafbe chore: initialize production-grade environment and medallion structure`); essentially **the entire app is untracked** (`git status` shows `??` on `src/`, `scripts/`, `frontend/`, `main.py`, Dockerfiles, CI) | `git log`, `git status` |
| Data freshness | Gold marts last generated **2026-07-31** (≈6 weeks stale today); pipeline has no scheduler in-repo | `data/gold/*.parquet` timestamps, grep for cron |
| Data layers | Bronze NDJSON + quarantine, Silver parquet, Gold = 6 marts (single_skill_roi, skill_overlap, market_overview, top_skills, skill_related, salary_distribution) | `data/*/`, `src/transformation/gold.py` |
| Sources | 8 adapters exist; 6 keyless (remoteok, remotive, arbeitnow, hackernews, greenhouse, lever), 2 key-gated (adzuna, usajobs) | `src/ingestion/sources/registry.py` |
| API | 10 endpoints, all in `main.py` (222 lines), all sync defs, no caching, parquet read per request | `main.py` |
| Postgres | Provisioned in `docker-compose.yml` but **zero SQL/DB code anywhere** | grep for `CREATE TABLE`/`postgres` in code |
| Testing | 4 backend test files (~280 test lines) vs ~2,500 prod Python lines; **no frontend tests at all** | `tests/`, `frontend/` |
| CI | GitHub Actions: pytest + ruff (backend), eslint + next build (frontend). No type check, no coverage gate, no Docker smoke test | `.github/workflows/ci.yml` |

### Critical risk surfaced in recon
---

## 3. Scope

### In scope
- Backend: FastAPI layer, API schemas, data loader
- Pipeline: 8 source adapters, validator, dedup, silver/gold transforms, orchestrator, R2 sync, seed script
- Data: bronze/silver/gold/quarantine contents (read-only inspection + reproduction in disposable copies or a scratch dir)
- Frontend: all pages, components, API client, types, build config
- Infra: docker-compose, Dockerfiles, CI workflow, env/template hygiene
- Process/security: secrets hygiene, dependency posture, observability

### Out of scope (unless you say otherwise)
- Debt warehousing / full rewrite
- Production deployment/cloud account configuration
- Legal/compliance review (though data privacy notes will be flagged)

---

## 4. Audit Playbook — Phases

> Each phase lists **goal**, **files**, **commands**, **questions**, and **deliverable**. I will mark each phase as ⬜ Not started / 🔄 In progress / ✅ Done as I work through it.

---

### Phase 0 — Orientation & Baseline  ⬜  (½ day)

**Goal:** Establish stable reference points before any analysis; verify docs vs. reality.

**Actions**
1. Create a baseline snapshot so the audit never modifies the true state:
   - Commit current working tree to `audit-baseline` branch or a tag (requires your approval to write to git).
   - Confirm `git status` is clean afterward.
2. Read `README.md` side by side with the code and annotate a **docs-vs-code discrepancy table**:
   | README claim | Check against |
   |---|---|
   | Architecture diagram (8 sources → gold+Postgres → API → Next.js) | `registry.py`, `orchestrator.py`, `docker-compose.yml` |
   | 10 API endpoints table | `main.py` route list |
   | "Phase 3: Auth & Personalization" via Postgres | grep for SQL usage |
   | Personas section | Actual shipped pages in `frontend/src/app/` |
3. Run the full validation suite (this is the "green baseline" — record everything):
   ```bash
   cd /home/evilmorty/Desktop/Projects-peronal/lumina-career-roi-prod
   make test
   make lint
   cd frontend && npm run lint && npm run build
   ```
4. Collect environment facts: `python --version`, `uv --version`, `node --version`, `npm --version` (if available).

**Deliverable:** Baseline record (commit hash/tag, test/lint/build output logs, environment versions, docs-vs-code discrepancy table).

---

### Phase 1 — Repository Hygiene & Git History  ⬜  (½ day)

**Files:** `.gitignore`, `.env`, `.env.sample`, `test_r2.py`, `configs/ingestion_state.json`, git log, untracked file list, `pyproject.toml` version vs `main.py` version.

**Commands**
```bash
git log --oneline --decorate --all
git status --short
git ls-files | grep -E '\.(env|json|pyc|cache)'
find . -name '*.pyc' -o -name '__pycache__' | head -50
grep -rn "ADZUNA_APP_KEY\|R2_SECRET\|USAJOBS_API_KEY" --exclude-dir=.venv --exclude-dir=node_modules .
```

**Questions to answer**
1. Is `.env` truly excluded and was it ever committed? (check `git log --all -p` for credential-looking values)
2. Should `test_r2.py` live at repo root? It builds an R2 boto3 client at import time — `pytest` collects `test_*.py` and would attempt a live connection.
3. Is `configs/ingestion_state.json` (pipeline watermarks) meant to be versioned or is it runtime state?
4. Why are `__pycache__/` and `.pytest_cache/` present in the working tree while also listed in `.gitignore`?
5. Version drift: `pyproject.toml=0.2.0` vs API `version="2.0.0"` vs README "v2" — define a single source of truth.

**Red flags already identified**
- [x] Single commit; whole app untracked → **no history, no blame, no bisect**
- [x] `test_r2.py` at repo root with import-time side effects
- [x] `.env` present in tree (gitignored ✅) but `R2_TOKEN_VALUE` appears in it but NOT in `.env.sample` — sample drift
- [x] Version strings inconsistent across three files

**Deliverable:** Hygiene findings list + recommended `.gitignore`/repo-layout changes (as a proposal, not yet applied).
---

### Phase 2 — Architecture & Data Flow Audit  ⬜  (1 day)

**Files:** `docker-compose.yml`, both `Dockerfile`(s), `scripts/orchestrator.py`, `scripts/run_bronze_ingestion.py`, `scripts/run_silver_transformation.py`, `scripts/run_gold_transformation.py`, `src/utils/paths.py`, `configs/ingestion_state.json`.

**Goal:** Draw the **actual** architecture from code (not README), then diff against the documented one.

**Questions to answer**
1. **End-to-end trace** — for a single job posting, can I follow it: adapter → `RawJob` → enforcement → NDJSON bronze → concat → dedup → silver → gold mart → API response → UI card? Where are the seams/leaks?
2. **Idempotency:** Bronze files accumulate forever; every Silver run re-reads *all* bronze files and re-dedups → runtime grows each run and old data can't be retracted. Is a full rebuild the intent? Is there a manifest/version stamp?
3. **Scheduling:** Nothing in-repo schedules `make ingest` (no cron, no CI cron, no Prefect server config). How is "production" getting new data?
4. **Service coupling in compose:** backend `depends_on: etl-pipeline` + `restart: unless-stopped`. If ETL completes once and exits, and long-running bronze history accumulates — what's the compose-level behavior on `docker compose up`?
5. **Container layering:** both Dockerfiles — check `uv sync` dev vs prod (`--no-dev`), non-root user, pinned base images, `uv.lock` usage, `.dockerignore` coverage (does it exclude `.venv`, `data/`, `__pycache__`?).
6. **State:** where is watermark state kept; what happens on concurrent runs (file-lock/atomicity)?

**Commands**
```bash
cat docker-compose.yml Dockerfile Dockerfile.backend .dockerignore
cat configs/ingestion_state.json
sed -n '1,120p' scripts/run_bronze_ingestion.py   # thin wrappers vs duplication
```

**Deliverable:** Architecture-as-built diagram (Mermaid/ASCII) + documented-vs-actual diff table + service lifecycle notes.

---

### Phase 3 — Data Pipeline & Correctness Deep-Dive  ⬜  (2 days) — **go first: highest business risk**

**Files:** all of `src/ingestion/sources/*.py`, `src/ingestion/validator.py` (242 lines), `src/ingestion/skills_taxonomy.py` (423 lines), `src/transformation/dedup.py`, `src/transformation/silver.py`, `src/transformation/gold.py`, `src/schemas.py` (RawJob contract), plus `data/bronze`, `data/silver`, `data/gold`, `data/quarantine`.

**3a. Salary & currency handling (`validator.py`) — P0 area**
| # | Suspected defect | Evidence | Impact |
|---|---|---|---|
| C1 | `_detect_currency` iterates dict; `"$"` matches before `"C$"`/`"A$"` → CAD/AUD salaries parsed as USD | lines ~102–110 | WRONG NUMBERS in every mart |
| C2 | `"₩"` mapped to `KRW` (should be RUB); RUB not in FX table | `CURRENCY_SYMBOLS` | Russian salaries misclassified |
| C3 | Single-char `"R"` → ZAR will false-positive on any description word containing "R" | `CURRENCY_SYMBOLS` | Random ZAR misclassification |
| C4 | FX rates hardcoded FY2025/26 (comment admits live API needed) | `FX_RATES_TO_USD` | Silently stale conversions |
| C5 | "Strict data contract" only checks title non-empty; unparseable salaries pass validation and die later | `enforce_constraints` valid_mask | Silence masks real data loss |

**Verification approach for 3a:** Write a **golden-file parameterized test** for `_parse_salary` covering: `"$130,000 - $160,000"`, `"100k"`, `"Competitive"`, `"€80k - €95k"`, `"C$120,000"`, `"A$95k"`, `"90k - 110k"`, `"$25/hr"`, empty string. These become regression tests in the final report.

**3b. Deduplication (`dedup.py`)**
- Complexity: nested `fuzz.ratio` over all accepted rows → O(n²) in Python. At current seed scale fine; ask at what N it breaks (can micro-benchmark in a scratch script).
- Trust model keeps the highest-trust row but **never merges fields** (e.g., better salary from a lower-trust row is lost).
- No deterministic tie-break when two rows have equal trust.
- `_normalize_title` regex strips noise words — verify it doesn't destroy title meaning (e.g., "Remote Data Engineer").

**3c. Skills extraction (`skills_taxonomy.py`)**
- Spot-check precision/recall: extract skills from 5 real descriptions from bronze, hand-verify each extraction.
- How are alternative spellings/aliases handled (e.g., `postgres` → `PostgreSQL`)? Is extraction case/word-boundary safe?

**3d. Bronze → Silver → Gold correctness (`silver.py`, `gold.py`)**
- Title case standardization: `to_titlecase()` after lowercasing — verify no weird casing for acronyms ("AWS" → "Aws"?).
- `expected_salary_usd` = midpoint; then rows with null salary are **dropped** (line ~91) — quantify the drop rate; this contradicts "Arbeitnow has no salary" claim in README (those jobs can never reach gold!).
- Related-skills mart: self-join produces both (a,b) and (b,a) rows → double count in co-occurrence (verify).
- `overall_avg_salary` computed from full silver; marts use that single global baseline — confirm intended semantics.
- **No mart versioning**: fixed filenames overwritten per run; no as-of timestamp → API consumers can't tell data age.

**3e. Reproduce the pipeline end-to-end (read-only on originals; outputs to scratch dir)**
```bash
cd /home/evilmorty/Desktop/Projects-peronal/lumina-career-roi-prod
PYTHONPATH=. uv run python scripts/run_bronze_ingestion.py
PYTHONPATH=. uv run python scripts/run_silver_transformation.py
PYTHONPATH=. uv run python scripts/run_gold_transformation.py
```
Then inspect with polars/duckdb:
```python
# scratch inspect (not committed)
import polars as pl
df = pl.read_parquet("/tmp/lumina_audit/data/silver/jobs_silver.parquet")
print(df.shape, df.null_count().sum(), df.head(5))
```
Trace 3–5 real jobs through every stage and record what changes at each hop.

**Deliverable:** **Data-quality scorecard** — rows in/out per stage, dedup rate, salary parse coverage %, quarantine rate, null-salary drop rate, extraction spot-check results. Plus a bug list with repro snippets (C1–C5 and anything new).
---

### Phase 4 — API & Data-Serving Layer  ⬜  (1 day)

**Files:** `main.py` (222 lines), `src/api/schemas.py`, `src/utils/api_data_loader.py`, `tests/test_api.py`, `frontend/src/lib/api.ts` (contract consumer).

**Focus areas & questions**
1. **Caching.** Every request re-reads parquet from disk (up to 3 reads on skill detail). No in-process TTL cache, no CDN strategy. Measure:
   ```bash
   PYTHONPATH=. uv run uvicorn main:app --port 8000 &   # background
   for i in $(seq 1 20); do curl -s -o /dev/null -w "%{time_total}\n" http://localhost:8000/api/v1/skills/roi; done
   ```
   Record p50/p95; repeat with cache proposal (not implemented) in mind.
2. **Route ordering fragility.** `/skills/{skill_name}` catch-all must stay last; `response_model=dict` on detail endpoint skips schema validation. What breaks if a new static route is added after it?
3. **Contract consistency.**
   - `/skills/{skill}/salary-distribution` → 200 with `[]` for unknown skill
   - `/skills/{skill}` → 404 for unknown skill
   - FileNotFoundError → 500 raw text on several endpoints
   Recommend one unified error contract (RFC 7807 problem+json) for all endpoints.
4. **Sync handlers on async framework.** All endpoint fns are `def` (thread pool) — fine, but no `run_in_executor`/`asyncio.to_thread` and no request ID / timing logs. Slow downstream fights the `slowapi` 429s.
5. **Rate limiter behavior.** Test that a 429 returns a clean JSON body, not an HTML error; confirm state is in-memory (resets on restart) and per-IP (`get_remote_address`) — proxies/behind-reverse-proxy caveat.
6. **CORS** hardcoded to two localhost origins — parameterize via env for any future staging/prod.
7. **Health endpoint** reports only `"healthy"` + version; no dependency status (parquet presence, data age).

**Deliverable:** Endpoint inventory table (route, method, response_model, caching, error handling, data freshness risk), benchmark numbers, and a cache/error-contract proposal.

---

### Phase 5 — Frontend & UX  ⬜  (1 day)

**Files:** `frontend/src/app/page.tsx` (dashboard), `compare/page.tsx`, `skills/[skill]/page.tsx`, `career-paths/page.tsx`, `business/page.tsx`, `education/page.tsx`, `frontend/src/components/Navbar.tsx`, `frontend/src/lib/api.ts`, `frontend/src/app/providers.tsx`, `frontend/package.json`, `frontend/next.config.ts`.

**Focus areas**
1. **Test gap:** zero test tooling (no vitest/jest/playwright/cypress). Flag as P1 gap.
2. **Metric-key coupling:** dashboard reads `m.total_unique_skills`, `m.average_salary_usd`, `m.median_salary_usd`, `m.total_jobs` directly from market mart → changing a mart column silently breaks the UI with no typing protection (`Record<string, number>`). Recommend shared generated types or a versioned API contract.
3. **TanStack Query usage:** no `staleTime`, no `retry`, no backoff, no `refetchOnWindowFocus` handling → 429s from the API surface as UX errors. Evaluate error UX on all pages (dashboards show a single "Failed to connect" banner).
4. **Persona coverage vs shipped pages:** For each of the 3 personas, walk the actual user journey:
   - Career Optimizer: dashboard → search → skill detail → compare → career-paths. Is the loop complete?
   - L&D: `business/page.tsx` — is it a real value-prop flow or a marketing stub? Does it use any market data?
   - Educator: `education/page.tsx` — same question.
   Record: page loads data from API or static copy?
5. **Bug-scan targets (manual):**
   - `decodeURIComponent(params.skill)` double-decoding edge cases (skill names with `%`, `+`, spaces).
   - Skill-detail chart when `salary_distribution` is `[]`.
   - Compare page with 3+ skills (API allows unlimited; check UI).
   - `career-paths` overlap list limit (API caps at 100; does UI paginate?).
6. **Build/runtime config:** `NEXT_PUBLIC_API_URL` default hardcoded to localhost; docker-compose passes `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` — only valid for local browser. Note for non-local deploys. Check `next.config.ts` for image domains/security headers (CSP, X-Frame).

**Deliverable:** UX/test findings per persona, a requirements-level gap list for B2B pages, and frontend test-strategy proposal (vitest unit + playwright smoke).
---

### Phase 6 — Security  ⬜  (1 day)

**Tooling first (automated scan):**
```bash
uv run bandit -r src/ scripts/ main.py            # if adding bandit to dev deps is OK with you
gitleaks detect --source . --no-git --redact      # if gitleaks is installed
uv audit                                            # uv's pyproject audit (treated as advisory)
npm audit --audit-level=high                        # frontend advisories
```

**Manual review checklist**
1. **Secrets:** `.env` is gitignored ✅ — confirm no values leaked into tracked files, `configs/`, Docker artifacts, or the lockfile. Check `test_r2.py`, `sync_to_r2.py` read from env only.
2. **Compose hardening:** hardcoded `lumina_dev_password` Postgres creds; no secrets injection (env_file only); no healthchecks; `restart: unless-stopped` on everything. Note as config debt, not a production cluster.
3. **Dependency posture:** `slowapi` (v0.1.9) is a small/early library powering rate limits — check maintenance/star count and failure mode. `uv.lock` locks everything but flag any direct pins to old majors.
4. **API surface:** all endpoints are public GETs of aggregate data — confirm that's intended (no PII). No auth anywhere; flag for future `saved skills`/personalization work.
5. **SSRF/redirects:** review `httpx` usage in source adapters — timeouts set? redirect policy? any user-controlled URL being fetched?
6. **Container security:** Dockerfiles — root user? base image tags pinned? `.dockerignore` excluding `.env`/`.venv`/`.git` (verify actual file: only 36 bytes, confirm coverage).
7. **Info leakage:** FastAPI 500 tracebacks in production? `include_in_schema` set on `/metrics` only. Error responses should not echo stack traces.

**Deliverable:** Security findings table (severity, evidence, CWE-ish mapping where obvious), secret-scan outputs, dependency advisory summary.

---

### Phase 7 — Testing & CI/CD Quality Gates  ⬜  (½ day)

**Files:** `tests/test_api.py` (77 lines), `test_validator.py` (85), `test_dedup.py` (49), `test_taxonomy.py` (65); `.github/workflows/ci.yml`.

**Coverage map (production lines vs test lines)**
| Module | Prod LOC (approx.) | Tested? |
|---|---|---|
| `main.py` | 222 | Partial (7 endpoint tests, mocked loaders) |
| `validator.py` | 242 | Partial |
| `dedup.py` | 138 | Partial |
| `silver.py` | 102 | ❌ none |
| `gold.py` | 197 | ❌ none |
| `orchestrator.py` | 181 | ❌ none |
| `sources/*.py` (8 adapters) | ~1,100 | ❌ none (no HTTP mocking) |
| `skills_taxonomy.py` | 423 | Partial |

**Gaps & proposed tests (to be written during audit with your OK)**
1. Golden-file table for salary parsing (Phase 3a).
2. Per-adapter fixture tests using `httpx.MockTransport`/`respx`.
3. Silver/Gold transform tests on fixture data (incl. null-salary drop behavior).
4. Orchestrator test with mocked registry (skipped-ingest branch coverage).
5. API contract tests for 404/empty/429/500 paths.
6. Frontend: 1 baseline vitest config + 2–3 component tests + an API-contract fixture check.

**CI gaps to flag**
- No coverage threshold (e.g., `--cov-fail-under`).
- No backend type checking (mypy/pyright/pyrightconfig absent).
- No Docker image build in CI (compose files can drift).
- No API smoke test (boot + hit `/api/v1/health` + `/api/v1/skills/roi` with seeded data).
- No frontend tests, no E2E.
- No scheduled run to detect stale data.

**Deliverable:** Test-strategy proposal, coverage report, CI enhancement list (ready to implement on approval).

---

### Phase 8 — Product, Performance & Roadmap Alignment  ⬜  (1 day)

**Questions to resolve (with you)**
1. **Data freshness SLA** — gold is 6 weeks stale. Propose: daily ETL, staleness alert, `Ingested-At` headers on API, README badge.
2. **Performance budget** — define p95 targets for dashboard (list, detail, compare, overlap). Propose in-process TTL cache (e.g., 5–15 min) as minimal viable fix, then DuckDB/Postgres if volume grows.
3. **Observability** — currently zero aggregation. Propose: structured logging (JSON), request-id middleware, `/metrics` expansion (parquet age, mart counts), optional Sentry.
4. **Roadmap honesty** — README implies auth/personalization ("Phase 3"), but Postgres is unused. Recommend finishing data/marts core before personalization.
5. **B2B pages** — decide: invest in real market-intel-driven business/education pages (they're the monetizable persona flow) vs. ship as-is.

**Deliverable:** Product gap analysis + prioritized roadmap (P0/P1/P2 with effort estimates).

---

### Phase 9 — Synthesis: Severity Matrix & Final Report  ⬜  (½ day)

**Severity rubric**
| Severity | Definition | Example |
|---|---|---|
| **P0 — Critical** | Data corruption, security exposure, total workflow breakage | Currency misclassification (C1–C3), repo loss risk |
| **P1 — High** | Major feature/persona impact, silent wrongness, scale blocker | No caching, unscheduled pipeline, Postgres unused |
| **P2 — Medium** | Debt with workarounds, quality gates missing | No frontend tests, hardcoded creds/CORS, no type check |
| **P3 — Low** | Polish, docs, ergonomics | Version drift in strings, pycache clutter |

**Final report structure**
1. Executive summary (3–5 bullets)
2. Severity matrix (all findings: ID, area, description, evidence w/ file:line, impact, likelihood, effort, recommended fix)
3. Data-quality scorecard & benchmark results
4. Architecture-as-built vs documented
5. Staged remediation roadmap (Now → 30 days → Next quarter), each item tied to a persona or risk
6. Appendix: commands run, logs, golden tests, reproduction scripts
---

## 5. Confirmed Red Flags (from recon, to be verified during audit)

| # | Finding | Source | Severity (est.) |
|---|---|---|---|
| 1 | Entire app untracked; 1-commit history | `git status`, `git log` | **P0** |
| 2 | Currency symbol/FX bugs (`$` swallow of `C$`/`A$`, `₩→KRW`, hardcoded rates) | `validator.py` lines 53–57, 102–110 | **P0** |
| 3 | No cache; parquet read per request; no error contract | `api_data_loader.py`, `main.py` | **P1** |
| 4 | No scheduler; 6-week-stale gold data | repo search, `data/gold` | **P1** |
| 5 | Postgres provisioned, zero code uses it | `docker-compose.yml`, grep | **P1** |
| 6 | Zero frontend tests; tight mart-key coupling | `frontend/` | **P1** |
| 7 | `test_r2.py` import-time boto3 client; repo-root clutter | repo root | **P2** |
| 8 | Hardcoded DB creds / CORS / version drift (0.2.0 vs 2.0.0) | `docker-compose.yml`, `main.py`, `pyproject.toml` | **P2** |
| 9 | O(n²) dedup, no merging, no mart versioning, null-salary rows dropped silently | `dedup.py`, `gold.py`, `silver.py` | **P2** |
| 10 | No observability / error tracking | global search | **P2** |
| 11 | Validator's "strict data contract" effectively only requires a title | `validator.py` lines 223–229 | **P2** |
| 12 | Related-skills mart double-count (a,b)/(b,a) | `gold.py` lines 137–152 | **P2** |
| 13 | `.env` has `R2_TOKEN_VALUE` missing from `.env.sample` | `.env`, `.env.sample` | **P3** |

---

## 6. Execution Order (bookended for safety)

| Order | Phase | Why this order |
|---|---|---|
| 1 | **Freeze baseline** (Phase 1 git step) | Never audit a moving target |
| 2 | **Phase 3** data correctness | The product IS the data; everything inherits it |
| 3 | Phases **4 (API)** + **5 (Frontend)** + **6 (Security)** | Can run as parallel tracks |
| 4 | Phases **0, 1, 2, 7** | Fill in around the above |
| 5 | Phase **8 (Product)** | Needs findings from 3–7 to be concrete |
| 6 | Phase **9 (Synthesis)** | Final matrix + roadmap |

---

## 7. Definition of Done (for the whole audit)

- [ ] Baseline frozen (git tag/branch, clean status)
- [ ] All 6 marts + full pipeline reproduced in scratch dir
- [ ] Salary parser golden tests written and passing (as proposed additions)
- [ ] Endpoint inventory + latency benchmarks recorded
- [ ] Frontend persona walk-through documented
- [ ] Security scans run and outputs captured
- [ ] Severity matrix (P0–P3) with evidence for every finding
- [ ] Staged remediation roadmap delivered
- [ ] Final report committed to `docs/audit/` (or location you prefer)

---

## 8. Guardrails & Working Agreements

1. **Read-only during audit unless you approve the write:** reproduction runs write only to `/tmp` scratch dirs; no modifications to `src/`, `frontend/`, configs, or data without explicit sign-off.
2. **Nothing destructive:** I will not run `make down` against a live stack, delete data, force-push, or touch your `.env` secrets.
3. **Golden tests only as proposals** at first — applied to the suite only with your approval.
4. **Every finding includes evidence** (file:line or command output), not vibes.
5. **Incremental check-ins:** each phase ends with a short summary + updated severity matrix before I proceed.
**The repository effectively has no history.** This blocks normal audit tools (git blame, bisect, per-feature diffs) and means the "production-grade" commit message is untested marketing. Mitigation: **freeze the baseline first** (Phase 1) before touching anything.