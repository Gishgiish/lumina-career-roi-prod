# Lumina Career ROI — Codebase Status and Audit

**Prepared:** 2026-11-04\
**Last updated:** 2026-11-07 — Steps 1–3 committed; Step 4 live scratch run executed three times, its P0 salary defects fixed and re-verified; see §10.\
**Baseline:** commit `42c3218` (`Add data-correctness remediation (Steps 1-3) and review fixes`) plus the Step 4 salary fixes in the current HEAD commit; working tree clean
**Method:** full read of backend, pipeline, frontend, infra, tests, and CI; inspection of the generated data; execution of
the test, lint, and build suites; direct reproduction of the defects listed here.

> **Document control:** this file replaces `AUDIT_PLAN.md` and `lumina_audit_report.md`, both removed on 2026-11-04
> because they contained stale or factually incorrect claims. The corrections are recorded in §8.

---

## 1. Executive Summary

Lumina Career ROI is a **well-structured prototype with a working synthetic demo**. The architecture is sensible:
canonical `RawJob` schema, eight source adapters, Bronze/Silver/Gold layering, quarantine, FastAPI, and a Next.js UI.
The demo loop works end to end when seeded with synthetic data.

The **live data path is still not production-ready**, but the P0 data defects are fixed. Currency conversion (Step 2.1),
deduplication (Step 2.2), and the Gold hygiene/salary-less work (Step 3) are complete: null and empty skills no longer
contaminate the marts, related pairs are canonicalized, salary buckets are ordered numerically, title casing preserves
acronyms, and salary-less jobs are retained for demand statistics while salary-based marts exclude them and report
coverage. Remaining gaps are operational and accuracy-related: no scheduler or data-freshness signal, static FX rates,
heuristic skill extraction, and one unscheduled scratch live run (not committed as data).

**Bottom line:** do not treat the current output as production labor-market intelligence. The synthetic demo is now
internally consistent; real ingestion, freshness, and serving hardening remain.

**Step status (2026-11-07): Steps 1, 2, 3, and 4 are complete.** Backend lint and tests are green (155 tests),
scratch data/state isolation exists, the seed and pipeline share one Gold builder, currency and dedup regressions are
fixed, and Gold hygiene plus the salary-less policy are implemented and covered by tests. Step 4 ran three times into
scratch: run 1 exposed corrupt live salaries; after the HN parsing, salary-period, and plausibility fixes run 2 looked
plausible, but review found that description-wide bare-amount matching still treated funding, savings, and revenue
figures as salaries. Bare amounts are now trusted only in a pipe header or on payroll-vocabulary lines, and run 3
re-verified the result. Remaining gaps are skill extraction, source health, coverage, and freshness.

---

## 2. Verified Baseline

| Area | Verified fact |
|---|---|
| Git | `main`, 6 commits, no branches. HEAD is the Step 4 salary-fix commit; the previous baseline was `42c3218`, and the 2026-11-04 review baseline was `e1848d3` plus uncommitted work |
| Uncommitted changes | None after the Step 4 salary-fix commit (2026-11-07) |
| Documentation cleanup | On 2026-11-04 this status file was added, `README.md` was rewritten to match the code, and `AUDIT_PLAN.md`, `lumina_audit_report.md`, and `frontend/README.md` were deleted. `42c3218` also records those two audit-file deletions |
| Backend tests | `155 passed` (was `144` after the first Step 4 review, `135` after Step 3, `109` after Step 2.2, `102` after 2.1, `85` after Step 1, `59` before Step 1) |
| Backend lint | **Passes.** `uv run ruff check src/ scripts/ tests/` is clean. `I001` fixed 2026-11-07; `BLE001` was already fixed in the working tree |
| Frontend lint | `npm run lint` passes |
| Frontend build | `npm run build` passes; Next.js performs TypeScript checking during the build |
| API | All 11 public endpoints respond against seed data and against the scratch live run (1.8–17.5 ms per request in-process) |
| Data | 800 synthetic rows, 6 sources, 82 skills represented, 700 salaried jobs (87.5% coverage), 7 Gold marts, files regenerated 2026-11-07 |
| Live pipeline evidence | **Scratch run only** (2026-11-07, keyless 6, run 3): 5 sources produced data, 3,517 Bronze → 3,269 Silver, 96 salaried (2.9%), 7 Gold marts. Kept under `/tmp/opencode/lumina-step4`; default demo data and watermark untouched. Lever yielded zero jobs (all boards 404) |
| PostgreSQL | Provisioned in compose; zero application code uses it |
| Scheduling | No cron, CI schedule, or Prefect deployment in the repository |
| Frontend tests | None |
| R2 | Reachable; `tests/test_r2.py` performs a live `head_bucket` call during pytest collection |

Path isolation added in Step 1: `LUMINA_DATA_DIR` relocates `bronze/`, `silver/`, `gold/`, and `quarantine/`;
`LUMINA_STATE_FILE` relocates the ingestion watermark. Both default to the previous locations and are read at import
time.

### What the data actually is

The on-disk Gold marts are **seed data**, not output from the multi-source orchestrator:

- Silver contains 800 rows with `external_id` values such as `seed_0`.
- Only six sources are represented (no Adzuna or USAJobs).
- The marts were rebuilt on 2026-11-07 through the shared production builder, so they now carry production Gold
  semantics: seven market metrics (including `jobs_with_salary` and `salary_coverage_rate`), related pairs filtered
  at `>= 2`, and a demand mart that includes salary-less postings.
- They are still synthetic and must not be presented as live labor-market data.

No repository artifact demonstrates a successful run of the current `scripts/orchestrator.py` flow.

---

## 3. Architecture as Built

### Demo path

```
scripts/seed_data.py
  -> synthetic Silver parquet
  -> src/transformation/gold.py::build_gold_marts (shared with the pipeline)
  -> FastAPI
  -> Next.js
```

This path bypasses Bronze, validation, currency parsing, deduplication, and skills extraction. It is why the demo
looks clean despite the pipeline defects below. Since Step 1 it uses the same Gold implementation as the pipeline,
so mart semantics no longer diverge.

### Live path

```
8 adapters
  -> validator.enforce_constraints()
       - parses salaries and currencies
       - validity gate currently checks only that title is non-empty
  -> Bronze NDJSON + quarantine
  -> transform_bronze_to_silver()
       - reads ALL Bronze history
       - fuzzy deduplication
       - skills extraction
       - keeps salary-less rows (`has_salary = false`) for demand
  -> transform_silver_to_gold()
       - 7 parquet marts
  -> FastAPI
  -> Next.js
```

### Strengths worth preserving

- Canonical `RawJob` contract and adapter registry.
- Quarantine concept with rejection metadata.
- Curated taxonomy with aliases.
- Medallion separation and small, readable transform modules.
- Seed script that lets the UI run offline.
- CI covering both backend and frontend.
- Reproducible Python environment via `uv` and the lockfile.

---

## 4. Findings

Severity definitions:

- **P0:** corrupts core numbers or breaks the live API once real data is ingested.
- **P1:** user-visible defect, blocks scale/freshness, or misleads the business.
- **P2:** operational/technical debt with a workaround.
- **P3:** polish.

### P0 — Data correctness and live-launch blockers

#### D-01 — Non-USD salary conversion is wrong in the live path

**Fixed in Step 2.1 (2026-11-07).** Recorded here for history.

Original evidence:

- Adzuna built every salary string with a literal `$`, including for GBP, EUR, INR, CAD, AUD, and other countries:
  `src/ingestion/sources/adzuna.py:86-93`. The correct country currency was supplied separately at `:130`, but it lost.
- `_parse_salary` gave the detected symbol precedence over the adapter-supplied currency:
  `src/ingestion/validator.py:196-198`.
- The uncommitted WIP made this worse for ISO-code-prefixed strings. Its single-letter `R` rule matched the `R`
  in `EUR` or `INR` followed by a digit:
  `src/ingestion/validator.py:121-150` (pre-fix working-tree version).
- FX rates are hardcoded FY2025/26 values:
  `src/ingestion/validator.py:21-46`.

Original reproduction:

```python
_parse_salary("$70000 - $90000", "GBP", "annual")   # -> USD, 70k-90k
_parse_salary("EUR 80,000", "EUR", "annual")         # -> ZAR, 4,320
_parse_salary("INR 500000", "INR", "annual")         # -> ZAR, 27,000
_detect_currency("EUR 80,000")                       # -> "ZAR"
```

Re-verified on 2026-11-07 with the working-tree WIP left untouched:

```python
_detect_currency("EUR 80k")          # -> "ZAR"
_detect_currency("INR 1,200,000")    # -> "ZAR"
_detect_currency("80 000 EUR")       # -> None
_parse_salary("EUR 80k")             # -> (4320.0, 4320.0, "ZAR", "unknown")
_parse_salary("INR 1,200,000")       # -> (64800.0, 64800.0, "ZAR", "unknown")
```

Impact: every non-USD Adzuna salary was mis-converted, and any source that emitted ISO-code-prefixed salaries was at
risk. This corrupted every downstream ROI number.

Resolution (Step 2.1):

- `_detect_currency` now checks ISO 4217 codes as whole tokens **before** any symbol, so the `R` in `EUR`/`INR` can no
  longer win. `EUR 80k` → EUR, `INR 1,200,000` → INR, `80 000 EUR` → EUR.
- The `R` (ZAR) rule now requires a standalone/number-adjacent token that is not preceded by a letter. `R 500 000` and
  `500 000 R` still map to ZAR; `R$` still maps to BRL.
- `_parse_salary` prefers a valid adapter-supplied ISO currency over symbol sniffing.
  `_parse_salary("$70,000 - $90,000", "GBP")` → GBP, 70k–90k (converted at 1.27).
- Adzuna emits plain numeric ranges (`"70000 - 90000"`) and passes the country ISO code, so GBP/EUR/INR/CAD/AUD
  salaries are no longer read as USD.
- The useful WIP behavior is preserved: space-grouped thousands (`"120 000 kr"`) and `kr` → SEK.
- Coverage: new ISO/`R`/explicit-currency tests in `tests/test_validator.py` and a fetch regression test in
  `tests/test_adzuna.py`.

Verified after the fix:

```python
_detect_currency("EUR 80k")          # -> "EUR"
_detect_currency("INR 1,200,000")    # -> "INR"
_detect_currency("80 000 EUR")       # -> "EUR"
_detect_currency("R 500 000")        # -> "ZAR"
_parse_salary("EUR 80k")             # -> (86400.0, 86400.0, "EUR", "unknown")
_parse_salary("INR 1,200,000")       # -> (14400.0, 14400.0, "INR", "unknown")
_parse_salary("$70000 - $90000", "GBP")  # -> (88900.0, 114300.0, "GBP", "unknown")
```

Remaining limitations:

- FX rates are still the hardcoded FY2025/26 `FX_RATES_TO_USD` table. **Decision:** keep them for the prototype
  because they are deterministic, offline, and need no API key; move them to configuration or a live FX source before
  any production launch. Converted USD values are directional, not financially precise. The decision is documented in
  `src/ingestion/validator.py`.
- `_parse_salary_numbers` handles comma-grouped (`80,000`) and space-grouped (`80 000`) thousands but not dot-grouped
  thousands (`80.000 EUR`). It reads `80.000` as the decimal number `80`, which falls below the annual threshold, so
  the salary is dropped entirely; for hourly rates the same misread produces `$80/hour`. Add dot-grouped parsing
  before relying on DE/NL/ID-style postings. Documented in `src/ingestion/validator.py`.
- `_detect_currency` disambiguates `¥` with a loose `"cn" in low` substring test as well as `cny`/`china`. Any `¥`
  string containing the letters `cn` anywhere (for example a company or city name) is classified as CNY instead of
  JPY. Tighten to whole-token/context matching when CNY volume matters. Documented in `src/ingestion/validator.py`.

Status: **fixed for the currency-detection and conversion path; FX-rate precision remains an open prototype
limitation.**

#### D-02 — Deduplication merges distinct jobs

**Fixed in Step 2.2 (2026-11-07).** Recorded here for history.

Original evidence: `src/transformation/dedup.py:109-123` accepted a fuzzy match when either the company **or** the
location matched. The exact key was title + company + location, but the fuzzy OR path was the damaging one.

Reproduced with three distinct rows:

```
("Software Engineer", "Acme",     "Remote")   -> kept
("Software Engineer", "Other Co", "Remote")   -> dropped (same location)
("Software Engineer", "Acme",     "Berlin")   -> dropped (same company)
```

Result: three distinct jobs collapsed to one. At live scale, common titles such as “Software Engineer” in “Remote”
would be heavily undercounted, and demand statistics would be wrong.

Resolution (Step 2.2):

- Fuzzy acceptance now requires **both** company and location to match (and both to be non-empty). A shared company or
  a shared location alone is no longer sufficient.
- Exact keys normalize whitespace and prefer the specific `location` over the broader `country`, so "Berlin" and
  "Munich" in Germany no longer collide on the same key.
- The surviving record is chosen deterministically: trust rank, then source, then `external_id`, then input order.
- Missing fields on the kept row are filled from lower-trust duplicates (for example `min_salary_usd`,
  `max_salary_usd`, `salary_raw`). Existing values are never overwritten, and source/trust identity is never merged.
- Coverage: `tests/test_dedup.py` now includes the three-distinct-jobs fixture plus fuzzy-match, salary-merge,
  no-overwrite, tie-break, and location-vs-country regressions.

Status: **fixed.**

#### D-03 — Jobs without salaries were silently dropped at Silver

Evidence: `src/transformation/silver.py:90-91` filters out every row with a null `expected_salary_usd`.

Consequences:

- All Arbeitnow jobs are dropped (the adapter has no salary).
- Most Greenhouse jobs are dropped (the public API does not provide salary).
- Many Lever, Remotive, and HackerNews jobs are dropped.
- Demand counts are biased toward sources that publish salaries.

The audit trail does not report this loss; the rows simply disappear between Bronze and Silver.

Status: **fixed (Step 3).** Policy: keep salary-less jobs for demand statistics with a separate demand mart.

Resolution: Silver retains every deduplicated row, sets `expected_salary_usd = null` when no salary is parseable, and
adds `has_salary`. The transform logs total salaried/total jobs and the coverage rate on every run. Salary-based marts
(`single_skill_roi_mart`, `skill_overlap_mart`, `salary_distribution_mart`, `top_skills_mart`) filter on salary;
`skill_demand_mart` counts all jobs; `market_overview_mart` exposes `jobs_with_salary` and `salary_coverage_rate`.
Coverage: `tests/test_silver.py`, `tests/test_gold.py`, `tests/test_seed.py`, `tests/test_api.py`.

#### D-04 — Jobs without extracted skills create a `null` skill that breaks the API

Evidence:

- Gold explodes `skills_list` with `empty_as_null=True` and then groups by it, so an empty skill list becomes a null
  skill row: `src/transformation/gold.py::build_single_skill_roi` (the explode is at line 66).
- The API loader calls `item["skill"].lower()` while looking up a skill:
  `src/utils/api_data_loader.py:34-40`.
- The same null skill can reach the dashboard and break `.toLowerCase()` filtering in the UI.

Reproduced:

```python
# One job with ["Python"], one job with []
# explode -> ["Python", null]
# group_by -> a null skill group
```

Status: **fixed (Step 3).**

Resolution: `_clean_skills` strips empty entries and drops jobs with no usable skills before every explode in
`build_single_skill_roi`, `build_skill_overlap`, `build_salary_distribution`, `build_skill_demand`, and
`build_skill_related`. `skills_list` is cast to `List(Utf8)` so all-null columns are handled. Coverage:
`tests/test_gold.py::TestSkillHygiene`.

#### D-10 — Live HackerNews salaries were arbitrary description text

**Found and fixed in Step 4 (2026-11-07).** Recorded here because the seed demo cannot exercise this path.

Evidence from the first scratch run (keyless 6, 3,511 Bronze rows):

- Algolia returns HN comment bodies as HTML with `<p>` tags, not newlines. `_parse_job_comment` split `lines[0]`,
  which was the entire comment, then used `parts[3]` as `salary_raw`.
- 168 HN rows had `salary_raw` averaging 278 characters (max 2,066): `"Full-time"`, `"UK time zone"`,
  `"Remote (North America & Europe)"`, and whole HTML paragraphs.
- `HOURLY_HINTS` contained `"hr"` and used substring matching, so `href`/`https` made 35 HN rows hourly; the
  validator then multiplied arbitrary numbers by 2,080.
- Result: 14 titles longer than 120 characters (max 1,268) containing HTML, `average_salary_usd = 1.83e16`, one row
  at `2.93e18`, 49-skill overlap combos, and `"Hiring"` as the #2 skill.

Resolution:

- HN comment bodies are converted from HTML to line-delimited plain text, and salary is reduced to an explicit
  salary token (max 80 chars). Titles are capped at 200 chars.
- `_detect_salary_type` uses word-boundary regex patterns, so `hr` no longer matches `href`/`https`.
- `_parse_salary` annualizes and converts each candidate, keeps only values within `$1,000`–`$10,000,000`, and takes
  the range from the first two plausible values.
- `enforce_constraints` now honors an adapter-declared `salary_type` and logs per-source parse coverage.
- HN leaves the salary period unknown for free text so detection can run.

Verified in the third scratch run: average `$153,903.27`, median `$157,500`, 96/3,269 salaried (2.9%), zero HN
hourly misclassifications, `salary_raw` mean 10.4 chars (max 19), zero titles containing HTML, 11/11 API endpoints
200, default data and R2 untouched. Coverage: `tests/test_hackernews.py`,
`tests/test_validator.py::TestSalaryPeriodAndPlausibility`.

Review finding fixed before run 3: run 2 matched bare currency amounts anywhere in the comment body, so `$2.7M`
(raised), `$1.2M` (saved), and `$10k` (revenue) entered `salary_raw` and inflated the average by 22%. Bare amounts are
now accepted only in a pipe-delimited header or on a line with payroll vocabulary; explicit ranges and period-bound
amounts remain trusted anywhere.

Remaining after the fix: HN hourly/monthly rates whose period suffix is stripped (`$55 - $75`, `$70-150`, `€5,000`)
are extracted but stay unparsed; comma-decimal values such as `"$35,3k"` are read as `353k`; skill extraction still
yields `"Hiring"`/standalone `"Go"` false positives; and full-set combos still reach 49 skills. These are P1.

### P1 — User-visible defects, freshness, and business accuracy

#### D-05 — Salary histogram buckets are in the wrong order

Evidence: `src/transformation/gold.py:193` sorts buckets lexicographically inside
`build_salary_distribution`. There is no longer a second copy in `scripts/seed_data.py` (removed in Step 1).

Reproduced in the stored mart:

```
Apache Kafka: ["$100k - $125k", "$125k - $150k", "$150k - $200k", "$75k - $100k"]
```

The API returns them in that order and the skill-detail chart renders them left to right in that order.

Status: **fixed (Step 3).**

Resolution: `build_salary_distribution` adds an integer `bucket_order` column and sorts by `skill, bucket_order`.
Salary-less rows are filtered before bucketing so a null salary cannot fall through into `$200k+`. The API keeps the
mart's order, so the skill-detail chart renders buckets numerically without a frontend change. Coverage:
`tests/test_gold.py::TestSalaryDistribution`.

#### D-06 — Related-skill responses contained mirrored duplicates

Evidence:

- Gold emits both `(skill_a, skill_b)` and `(skill_b, skill_a)` without canonical ordering:
  `src/transformation/gold.py::build_skill_related` (mirror join at line 149).
- The loader filters either direction and appends the other skill, so both mirrored rows produce an entry:
  `src/utils/api_data_loader.py:61-78`.

Reproduced after Step 1 regeneration:

```
/skills/Python/related?limit=10
-> 10 entries, but only 7 unique skills
```

The pre-Step 1 demo returned 6 unique skills from 10 entries; the shared `>= 2` filter changed which pairs survive but
did not remove the mirroring. The mirrored rows do not double the count; the counts are correct per direction. The
defect is duplicate entries, which pushes real related skills out of the top-N list.

Status: **fixed (Step 3).**

Resolution: `build_skill_related` canonicalizes each unordered pair so `skill_a < skill_b` and counts distinct jobs
containing the pair, so mirrored join rows are neither emitted twice nor double-counted. `get_related_skills` sorts by
count then skill name for deterministic top-N output. Coverage: `tests/test_gold.py::TestSkillRelated`.

#### D-07 — Title casing destroys acronyms

Evidence: `src/transformation/silver.py:70-74` lowercases then title-cases every title.

Reproduced:

```
"AWS Solutions Architect" -> "Aws Solutions Architect"
"DevOps (CI/CD) Lead"     -> "Devops (Ci/Cd) Lead"
```

Seed data bypasses this transform, so the demo hides the issue.

Status: **fixed (Step 3).**

Resolution: `_standardize_title` applies title case and then restores known acronyms/product names from
`TITLE_ACRONYMS` (`AWS`, `ML`, `API`, `SQL`, `ETL`, `QA`, `DevOps`, `iOS`, `JavaScript`, and others). The map is
explicit and extensible; it is not a general NLU title normalizer. **Residual warning:** any acronym, product name, or
proper noun not listed in `TITLE_ACRONYMS` is still title-cased (`GCP` → `Gcp`, `Kubernetes` → `Kubernetes` but
`K8s` → `K8s` only if listed). Extend the map as new titles are observed; do not treat it as complete. Coverage:
`tests/test_silver.py`.

#### D-08 — Skill extraction has false positives and misses

Evidence:

- Every standalone English word “go” matches the Go language:
  `src/ingestion/skills_taxonomy.py:28`, extractor at `:362-411`.
- The tokenizer `[a-z0-9.#+]+` excludes `/`, so aliases such as `CI/CD`, `UI/UX Design`, and `A/B Testing` cannot
  match from their slash forms: `src/ingestion/skills_taxonomy.py:389`.
- `extra_terms` are appended without lowercasing while the tokenizer only matches lowercase, so capitalized tags can
  be ignored: `src/ingestion/skills_taxonomy.py:382-384`.

Reproduced:

```python
extract_skills("We go to market with our product")  # -> ["Go"]
extract_skills("Senior C developer")                # -> ["C"]
```

Step 4 confirmed this at live scale: "Hiring" is the #2 demand skill (43.3% of jobs with skills) and standalone "Go"
is #5 (27.1%). Full-description extraction also produces combos of up to 49 skills.

Status: **open.**

#### D-09 — Seed and production Gold are separate implementations that have diverged

**Fixed in Step 1 (2026-11-07).** Recorded here for history.

Original evidence:

- `scripts/seed_data.py:129-217` duplicated the Gold mart logic.
- Seed wrote four market metrics; `gold.py` wrote five (`top_source_count` was missing from the demo).
- Seed did not apply the related-pair `>= 2` filter that `gold.py` applied.
- Seed bypasses deduplication, currency parsing, title casing, and skills extraction.

Resolution:

- `scripts/seed_data.py` no longer contains mart-building code; it writes Silver and calls
  `src/transformation/gold.py::build_gold_marts`.
- Both paths now produce identical marts; verified by running seed and `transform_silver_to_gold()` against the same
  Silver and comparing all marts.
- Demo data regenerated with production semantics (related pairs filtered at `>= 2`; the market metric set expanded
  in Step 3).
- A pre-existing `market_overview` mixed-int/float crash in the production builder was found and fixed with explicit
  `float(...)` casts during this work.
- Coverage: `tests/test_gold.py` and `tests/test_seed.py`.

Still out of scope for this fix (unchanged): seed bypasses deduplication, currency parsing, title casing, and skills
extraction by design.

Status: **fixed.**

#### O-01 — Nothing schedules ingestion and there is no data-freshness signal

Evidence:

- No cron, CI schedule, or Prefect deployment anywhere in the repository.
- Gold marts have fixed filenames, no version, and no “as of” timestamp.
- `/api/v1/health` reports only `"healthy"` and a version, with no data age.
- Current Gold data was regenerated on 2026-11-07 but is still synthetic.

Status: **open.**

#### T-01 — Test and CI coverage does not protect the risky code

Updated after Step 4 (2026-11-07):

- 155 backend tests pass (20 new Step 4 regressions: HN HTML parsing, bounded salary tokens, `href` not hourly,
  adapter-declared salary type, implausible-salary rejection, funding/savings/revenue amounts not becoming salary,
  body salary behind a pay cue, body salary ranges, range-suffix propagation).
- Gold builders (`tests/test_gold.py`), Silver normalization (`tests/test_silver.py`), path/state resolution
  (`tests/test_paths.py`), the seed script (`tests/test_seed.py`, subprocess smoke), currency detection/parsing plus
  the Adzuna and HackerNews currency contracts (`tests/test_validator.py`, `tests/test_adzuna.py`,
  `tests/test_hackernews.py`), and deduplication (`tests/test_dedup.py`) now have coverage.
- Still untested: `orchestrator.py` and six of the eight source adapters (`remoteok`, `remotive`, `arbeitnow`,
  `greenhouse`, `lever`, `usajobs`). Adzuna and HackerNews now have targeted tests.
- API tests still mock the data loader (plus one loader-level precision test).
- No frontend test tooling or test files.
- CI still has no coverage gate, no backend type check, no Docker smoke test, and no scheduled freshness check.
- Backend lint is clean (`I001` fixed).

Status: **open; partially improved.**

#### P-01 — Postgres, B2B pages, and “ROI” overstate the product

Evidence:

- PostgreSQL is provisioned in `docker-compose.yml:47-59`, but no application code uses it.
- `/business` and `/education` are static pages with hardcoded statistics such as “+$30K”, “100+”, “10k+”, “+35%”,
  and “92%”.
- “Book a Demo” on `/business` links back to `/business`; “Get Curriculum Insights” on `/education` links back to
  `/education`.
- The product computes salary premium versus the overall average; there is no training-cost input or ROI calculation.

Status: **open; product decision required.**

### P2 — Operational and technical debt

| ID | Finding | Evidence |
|---|---|---|
| A-01 | Inconsistent API error contract: unknown skill returns 404, unknown skill salary-distribution returns 200 `[]`, missing mart can return a raw 500, and skill detail uses `response_model=dict` | `main.py:105-106`, `:163-191` |
| O-02 | Docker/ops debt: root `.dockerignore` does not exclude `.git` or `frontend/node_modules`; there is no `frontend/.dockerignore`; ETL/backend containers run as root; no healthchecks; hardcoded Postgres password; CORS hardcoded to localhost; `NEXT_PUBLIC_API_URL` is build-time, not runtime | `Dockerfile`, `Dockerfile.backend`, `.dockerignore`, `docker-compose.yml:45-59`, `main.py:56-65` |
| O-03 | Legacy/dead code: `scripts/run_bronze_ingestion.py` pipes a fake schema (`job_title`, `job_id`) into `enforce_constraints`, which expects `title` and raises `ColumnNotFoundError`; `src/ingestion/source.py` is a leftover fake-data stub | reproduced |
| O-04 | `configs/ingestion_state.json` is committed runtime state in the legacy `last_watermark` shape; the orchestrator expects `watermarks` and ignores it | `configs/ingestion_state.json`, `scripts/orchestrator.py:30-56` |
| O-05 | `tests/test_r2.py` performs a live R2 network call **during pytest collection** and has no assertions; it fails or stalls offline, needs credentials to collect, and makes CI depend on R2 | `tests/test_r2.py:10-30` |
| O-06 | No serving cache; every request re-reads parquet. At seed scale this is fine (p95 ~14 ms). The overlap mart can grow much larger at scale, so caching remains useful later, but it is not the immediate problem the earlier report implied | `src/utils/api_data_loader.py:17-22` |
| O-07 | `BaseSource._retry_fetch` exists but is never used; adapters mostly rely on orchestrator-level retries | `src/ingestion/sources/base.py:111-124` |
| P-02 | Version drift: `pyproject.toml` is `0.2.0`, API is `"2.0.0"`, and there is no single source of truth | `pyproject.toml:3`, `main.py:49`, `:80` |
| P-03 | Default create-next-app SVGs and boilerplate remain in `frontend/public/` | repository contents |
| G-01 | `build_skill_overlap` keys combinations with `", ".join(sorted skills)`. A skill name containing `", "` would collide two different skill sets into one combo; also ambiguous to split back into skills. No current taxonomy entry contains `", "`, so this is latent | `src/transformation/gold.py:166` |
| G-02 | Demand and related counts use `pl.col("external_id").count()` / `n_unique()`, which ignore null IDs. Jobs with a null `external_id` are silently excluded from `job_demand_count` and `combo_demand_count`. All current adapters set an ID, but custom or legacy rows may not | `src/transformation/gold.py:135`, `:171`, `:301` |
| S-01 | Every one of Lever's 20 curated boards returned HTTP 404 in Step 4; the adapter catches each error and continues, so a fully dead source is reported as "no new jobs" with no watermark and no warning | `src/ingestion/sources/lever.py`; `ingest_run1.log`–`ingest_run3.log` |
| S-02 | Six Greenhouse boards returned 404 (spotify, mercadolibre, doordash, etsy, shopify, confluent); the rest still produced 2,882 rows | `src/ingestion/sources/greenhouse.py`; Step 4 logs |

---

## 5. Data-Quality Scorecard (Current Artifacts)

| Metric | Current value | Source |
|---|---|---|
| Silver rows | 800 (synthetic) | `data/silver/jobs_silver.parquet` |
| Skills in ROI mart | 82 | `data/gold/single_skill_roi_mart.parquet` |
| Sources represented | 6 (remoteok, hackersnews, lever, remotive, greenhouse, arbeitnow) | Silver `source` column |
| Gold marts | 7 | `data/gold/` |
| Gold creation date | 2026-11-07 (Step 3 regeneration) | file mtimes |
| Market metrics | 7 (includes `jobs_with_salary`, `salary_coverage_rate`, `top_source_count`) | `market_overview_mart.parquet` |
| Live Bronze rows | 3 legacy rows only | `data/bronze/` |
| Live quarantine rows | 3 legacy rows only | `data/quarantine/` |
| Salary coverage | 700/800 jobs (87.5%); 100 salary-less rows retained for demand | Silver `has_salary` |
| Related-skill duplicated rows | 0 mirrored duplicates; 658 canonical pairs | `skill_related_mart.parquet` |
| Overlap combos | 689: 217 two-skill, 215 three-skill, 257 four-skill | `skill_overlap_mart.parquet` |

The “combo” mart groups by the **full skill set**, not by pairs, and now carries `combo_size`. Two-, three-, and
four-skill combinations still share one ranking, so compare premiums within a `combo_size` before comparing across
sizes. The combo identity is a `", "`-joined string (see P2/G-01), and demand counts ignore rows with a null
`external_id` (P2/G-02).

---

## 6. What Works

- `uv sync` and dependency resolution.
- `make seed` followed by the API and frontend demo.
- All 11 public API endpoints return structurally valid responses against seed data.
- Frontend lint and production build.
- Backend unit tests for the validator, deduplication helpers, taxonomy, and mocked API routes.
- Adapter classes, registry, canonical schema, and quarantine structure.
- R2 upload path exists and the configured bucket is reachable.

---

## 7. API and Frontend Notes (Verified)

- All documented endpoints are implemented in `main.py`.
- `/api/v1/skills/{skill}` performs three parquet reads plus a linear scan per request.
- `/api/v1/skills/nope/salary-distribution` returns **200** with an empty list; `/api/v1/skills/nope` returns **404**.
- `DELETE`/write endpoints do not exist; all public endpoints are aggregate GETs.
- CORS allows only `http://localhost:3000` and `http://localhost:3001`.
- Rate limiting is in-memory per client IP and resets on restart; the 429 response body is JSON.
- The dashboard, skill detail, compare, and career-paths pages consume the live API.
- The business and education pages consume no API data.
- TanStack Query is configured with a 60-second `staleTime`; the earlier report's “no staleTime” claim was wrong.
- Skill names containing `/` (for example `UI/UX Design`) cannot be addressed through the current single-segment route.

---

## 8. Corrections to the Removed Audit Documents

These are the specific claims that did not survive verification. They are recorded so the same errors are not
reintroduced.

| Prior claim | Verified reality |
|---|---|
| “Exactly 2 commits” | There are now 4 commits |
| “Related-skill counts are 2× reality” | Counts are correct per direction; the real defect is mirrored duplicate rows in the API response |
| “Combo mart emits C(4,2)=6 pairs per job” | The mart groups by the full sorted skill set; it does not emit pairwise combinations |
| “No TanStack `staleTime`” | `staleTime: 60_000` is configured in `frontend/src/app/providers.tsx` |
| “README says v2” | No `v2` string exists in the README |
| “BaseSource provides retry” | `_retry_fetch` exists but is unused |
| “The only validator problem is `$` before `C$`/`A$`” | Also: Adzuna forces `$` for every country, the WIP `R` rule misreads `EUR`/`INR` as ZAR, and ISO codes generally fall back to USD |
| “₩ should be RUB” (from `AUDIT_PLAN.md`) | ₩ is the Korean won; RUB is ₽ and is absent from the symbol table. The original plan was wrong; the later report corrected it |
| “The whole app is untracked / no baseline” | The tree is committed; the remaining history problem is only that there are 4 commits and no review trail |
| “No caching is a P1 serving emergency” | Current p95 is ~14 ms at seed scale; the more urgent risk is pipeline correctness and freshness |

Previously missed issues now documented above: Adzuna currency override, dedup OR-collapse, null-skill Gold
contamination, ISO-code currency false positives, slash-token taxonomy misses, mixed-size combo semantics, Docker
context bloat, and the CI lint regression.

---

## 9. Decisions Required

These are product decisions, not code decisions:

1. **Salary-less postings:** keep them for demand statistics with a separate demand mart, or exclude them explicitly
   and document the coverage bias? — **Resolved (Step 3):** keep them for demand statistics with a separate
   `skill_demand_mart`; salary-based marts filter on salary and `market_overview_mart` reports coverage.
2. **“ROI”:** rename the metric to salary premium, or add a real cost-of-learning/cost-of-training model?
3. **PostgreSQL:** implement a real first use (for example saved skills) or remove it from compose until needed?
4. **B2B pages:** replace hardcoded statistics with live mart values, label them as illustrative, or remove them?
5. **Near-term goal:** demo/portfolio readiness or trustworthy production data? This determines whether the next step
   is visible polish or pipeline correctness.

---

## 10. Recommended Next Steps

### Recommended: finish the data-correctness pass before adding features

Steps 1–4 are done. Remaining is P1 hardening, not another correctness gate: skill-extraction precision (D-08),
source health (Lever/Greenhouse boards), salary coverage from salary-less sources, comma-decimal parsing, and a
data-as-of manifest/scheduler (O-01). Estimate: **~1–2 focused engineering days**.

#### Step 1 — Green baseline and safe test environment — **COMPLETE (2026-11-07)**

Delivered:

- Fixed `tests/test_r2.py` import ordering; kept the existing `BLE001` fix. `ruff check` is clean.
- Left the uncommitted validator change **untouched**. It is not committed and its `R`/ISO-code regression is now the
  first task of Step 2 (see the entry conditions below).
- Added `LUMINA_DATA_DIR` and `LUMINA_STATE_FILE` resolution in `src/utils/paths.py`; defaults are unchanged.
- Unified Gold construction: `scripts/seed_data.py` writes Silver only and calls
  `src/transformation/gold.py::build_gold_marts`, the same function the pipeline uses.
- Fixed a pre-existing production crash in `market_overview` (mixed int/float `value` column) with explicit `float`
  casts; no numeric values changed.
- Regenerated the default demo marts with production Gold semantics.
- Added `tests/test_paths.py` (12), `tests/test_gold.py` (13), and `tests/test_seed.py` (subprocess smoke).
- Updated `README.md` and `.env.sample`; no commits.

Evidence:

```bash
uv run ruff check src/ scripts/ tests/                    # All checks passed
pytest tests/ -q                                          # 85 passed
LUMINA_DATA_DIR=/tmp/opencode/lumina-scratch make seed    # 7 marts, default data unchanged
cd frontend && npm run lint && npm run build              # both pass
```

Verification details:

- Refactored Gold output is content-identical to the pre-refactor production output for all six marts (marts 1–2 are
  byte-identical even before applying the float fix).
- Seed and `transform_silver_to_gold()` produce identical marts from the same Silver input.
- Scratch seed writes only under `/tmp/opencode/lumina-scratch` and does not advance
  `configs/ingestion_state.json`.
- All API endpoints (10 at the time) return 200 against the regenerated demo; six frontend routes return 200.
- Demo payload changes are limited to `top_source_count`, related-pair filtering, and the resulting `related_skills`
  ordering.

Carried forward from Step 1:

- **Validator WIP:** kept in the tree, uncommitted. The `R`/ISO regression was the entry condition for Step 2 currency;
  it is fixed and covered in 2.1.
- **Live ingestion:** still not run. The scratch overrides now make it safe to attempt in Step 4.

#### Step 2 — Fix currency and deduplication — **COMPLETE (2026-11-07)**

Entry conditions from Step 1:

- The working-tree validator change must be **completed, not reverted**. It already adds useful space-grouped-thousands
  parsing (`"120 000 kr"`) and `kr` handling; keep those and fix detection.
- Before Step 2.1 the WIP produced `EUR 80k` → ZAR, `INR 1,200,000` → ZAR, `80 000 EUR` → `None`, and
  `_parse_salary("EUR 80k")` → `(4320.0, 4320.0, "ZAR", "unknown")`. All of these are fixed; see 2.1.
- Use `LUMINA_DATA_DIR` plus `LUMINA_STATE_FILE` for any scratch run; do not overwrite the demo or advance the real
  watermark.
- Gold semantics now live in one module, so Step 3 changes to related pairs or buckets are made once and reach both
  seed and pipeline output.

##### 2.1 Currency (D-01) — **COMPLETE (2026-11-07)**

Delivered:

1. Added failing tests first: ISO codes `USD`, `GBP`, `EUR`, `INR`, `ZAR`, plus `"EUR 80,000"`, `"INR 500000"`,
   `"80 000 EUR"`, `"1,200,000 INR"`, `"120 000 kr"`, `"R 500 000"`, `"500 000 R"`, `"$70k"` with `GBP`, `C$`, `A$`,
   and `R$`. Twelve cases failed before the fix.
2. Fixed `_detect_currency` precedence: ISO codes are matched as whole tokens before any symbol; multi-character
   symbols are still checked before single characters; the single-letter `R` now requires a standalone/number-adjacent
   token that is not preceded by a letter. `"R 500 000"` and `"500 000 R"` → ZAR.
3. Re-verified `_parse_salary` normalization: `EUR 80k` → USD 86,400; `INR 1,200,000` → USD 14,400; `80 000 EUR` →
   USD 86,400.
4. Adzuna no longer prefixes `$`; it emits numeric ranges (`"70000 - 90000"`) and passes the country ISO currency.
5. `_parse_salary` now prefers a valid adapter-supplied ISO currency over symbol sniffing, so a `$`-prefixed GBP job is
   read as GBP.
6. FX decision: keep the static FY2025/26 `FX_RATES_TO_USD` table for the prototype (deterministic, offline, no API
   key) and document that it must move to configuration or a live source before production.

Evidence:

```bash
PYTHONPATH=. uv run pytest tests/test_validator.py tests/test_adzuna.py -q   # 53 passed
PYTHONPATH=. uv run pytest tests/ -q                                          # 102 passed
uv run ruff check src/ scripts/ tests/                                       # All checks passed
```

```python
_detect_currency("EUR 80k")             # -> "EUR"
_detect_currency("INR 1,200,000")       # -> "INR"
_detect_currency("80 000 EUR")          # -> "EUR"
_detect_currency("R 500 000")           # -> "ZAR"
_parse_salary("$70000 - $90000", "GBP") # -> (88900.0, 114300.0, "GBP", "unknown")
_parse_salary("120 000 kr")             # -> (11400.0, 11400.0, "SEK", "unknown")
```

Where it fits: changes are confined to `src/ingestion/validator.py`, `src/ingestion/sources/adzuna.py`, and the
corresponding tests. The WIP parser was extended in place; no second parser was added. Step 4 depends on this because
currency distribution is one of its recorded metrics.

Remaining: FX-rate precision (documented prototype limitation, not a blocker for Step 2.2).

##### 2.2 Deduplication (D-02) — **COMPLETE (2026-11-07)**

Delivered:

- Fuzzy acceptance now requires **both** company and location to match, with both non-empty. A shared company or shared
  location alone is no longer enough.
- Exact keys normalize whitespace and prefer the specific `location` over the broader `country`, so different cities in
  the same country do not collide.
- The surviving record is deterministic: trust rank, source, `external_id`, then input order.
- Missing fields on the kept row are filled from lower-trust duplicates (salary fields included). Existing values are
  never overwritten; source/trust identity is never merged.
- `tests/test_dedup.py` adds the three-distinct-jobs regression plus fuzzy-match, salary-merge, no-overwrite, tie-break,
  and location-vs-country tests.

Evidence:

```bash
PYTHONPATH=. uv run pytest tests/test_dedup.py -q   # 12 passed
PYTHONPATH=. uv run pytest tests/ -q                # 109 passed
uv run ruff check src/ scripts/ tests/              # All checks passed
```

Where it fits: `src/transformation/dedup.py` and `tests/test_dedup.py` only; no Gold changes required. Step 4's
dedup-rate metric depends on it.

#### Step 3 — Gold hygiene and salary-less policy — **COMPLETE (2026-11-07)**

Delivered:

- `_clean_skills` drops null/empty skill entries and jobs with no usable skills before every Gold explode.
- `build_skill_related` canonicalizes pairs (`skill_a < skill_b`), emits each unordered pair once, and counts distinct
  jobs; `get_related_skills` uses a deterministic count/name sort.
- `build_salary_distribution` adds `bucket_order`, sorts numerically, and filters salary-less rows before bucketing.
- `_standardize_title` preserves known acronyms and product names.
- Salary-less jobs are retained in Silver with `has_salary`; `build_skill_demand` adds the all-jobs demand mart;
  salary marts filter to salaried rows; `market_overview_mart` reports `jobs_with_salary` and
  `salary_coverage_rate`.
- `skill_overlap_mart` keeps complete skill sets, labels them with `combo_size`, and documents the full-set semantics.
- `GET /api/v1/skills/demand` exposes the demand mart; the seed script generates ~1 in 8 salary-less postings so the
  demand-only path is exercised by the demo.

Evidence:

```bash
PYTHONPATH=. uv run pytest tests/test_gold.py tests/test_silver.py \
  tests/test_api.py tests/test_seed.py -q      # 44 passed
PYTHONPATH=. uv run pytest tests/ -q           # 135 passed
uv run ruff check src/ scripts/ tests/         # All checks passed
PYTHONPATH=. uv run python scripts/seed_data.py
# 800 jobs, 700 with salary (87.5%), 7 marts, 82 skills
```

Where it fits: shared Gold builders and Silver normalization, plus the API loader/schema/endpoint. Seed, pipeline,
tests, and demo converge through `build_gold_marts`.

Post-review corrections (2026-11-07, same working tree):

- `CNY` now has an FX rate, so `¥`-with-China context no longer converts at 1.0.
- HackerNews leaves free-text salaries' currency unset, so `€`/`£` symbols drive conversion instead of a hardcoded
  USD.
- `total_unique_skills` counts skills from all jobs, including salary-less postings.
- Related-pair counts key on `(source, external_id)` so distinct jobs sharing an external ID are counted separately.
- `GET /api/v1/skills/demand` breaks demand ties by skill name for deterministic output.
- README test counts and the project-status banner were refreshed.

#### Step 4 — Run one real ingestion — **COMPLETE (2026-11-07)**

Delivered:

- Scratch-only keyless-6 run with `LUMINA_DATA_DIR` + `LUMINA_STATE_FILE`; Adzuna/USAJobs credentials blanked in the
  runner, R2 sync never invoked.
- Run 1 exposed D-10: HTML comment text became salary, 35 HN rows were misclassified hourly, and average salary was
  `1.83e16`.
- P0 fixes applied: HN HTML normalization and bounded salary tokens, word-boundary period hints, per-candidate USD
  plausibility bounds, and adapter-declared `salary_type` handling. See D-10.
- Review of run 2 found that bare currency amounts anywhere in a comment body were treated as salary (`$2.7M` raised,
  `$1.2M` saved, `$10k` revenue), inflating the average by 22%. Bare amounts are now trusted only in a pipe header or
  on payroll-vocabulary lines; trailing `k`/`m` range suffixes are propagated to both bounds.
- Run 2: 5 sources, 3,517 Bronze → 3,269 Silver (7.1% collapse), 101 salaried (3.1%), 250 skills, 7 marts;
  average `$189,344.69`, median `$151,200` (superseded by run 3).
- Run 3: same row counts, 96 salaried (2.9%), 250 skills, 7 marts; average `$153,903.27`, median `$157,500`; HN 224
  rows, 67 salary tokens, 62 parsed, 0 hourly; 11/11 API endpoints 200.
- Isolation verified: default `data/` and `configs/ingestion_state.json` checksums unchanged; no R2 upload.

Evidence:

```bash
PYTHONPATH=. uv run pytest tests/ -q          # 155 passed
uv run ruff check src/ scripts/ tests/       # All checks passed
# run 3 (scratch):
LUMINA_DATA_DIR=/tmp/opencode/lumina-step4/data \
LUMINA_STATE_FILE=/tmp/opencode/lumina-step4/state/ingestion_state.json \
PYTHONPATH=. uv run python /tmp/opencode/lumina-step4/run_stages.py
```

Full report: `/tmp/opencode/lumina-step4/results.md`. Granular tracker:
`/tmp/opencode/lumina-step4-plan.md` (both temporary, not committed).

Remaining for a trustworthy path: skill extraction false positives (D-08), dead/zero-yield sources (Lever), low salary
coverage from salary-less sources, comma-decimal salary parsing (`$35,3k`), and no data-as-of manifest. Do not run
`make ingest` for reruns: `scripts/orchestrator.py` ends with `task_sync_to_cloud()` and uploads to R2.

### Exit criteria for “trustworthy data path”

- [x] Backend lint and tests are green.
- [x] Currency tests cover symbol, ISO-code, and adapter-supplied-currency cases.
- [x] A three-distinct-jobs dedup fixture preserves all three rows.
- [x] Gold contains zero null/empty skill entries.
- [x] Salary buckets are in numeric order.
- [x] Related-skill responses contain no duplicates.
- [x] Title casing preserves acronyms.
- [x] One real ingestion produces inspectable, plausible statistics (scratch run 3; salary coverage and skill noise
  remain documented P1 gaps).
- [ ] Gold has a data-as-of timestamp or manifest.
- [x] The seed and production mart builders are the same code or are verified against each other.

### If the goal is a demo next week instead

Do only the visible fixes:

1. Correct salary-bucket ordering.
2. Deduplicate related-skill responses.
3. Preserve acronyms in titles.
4. Label the data as synthetic and remove or clearly mark the fabricated B2B statistics.
5. Fix the self-referential demo links.

Do not present live-ingested numbers as trustworthy until the P0 items are resolved.

---

## 11. Verification Commands and Evidence

Commands used:

```bash
# 2026-11-04 audit baseline
git log --oneline -5
git status --short
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q          # 59 passed
uv run ruff check src/ scripts/ tests/                    # 1 error: I001 in tests/test_r2.py
cd frontend && npm run lint                               # pass
cd frontend && npm run build                              # pass
```

After Step 1 (2026-11-07):

```bash
uv run ruff check src/ scripts/ tests/                    # All checks passed
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q          # 85 passed
LUMINA_DATA_DIR=/tmp/opencode/lumina-scratch make seed     # scratch-only, exit 0
cd frontend && npm run lint && npm run build               # pass
```

After Step 2.1 (2026-11-07):

```bash
uv run ruff check src/ scripts/ tests/                    # All checks passed
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q          # 102 passed
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/test_validator.py tests/test_adzuna.py -q          # 53 passed
```

After Step 2.2 (2026-11-07):

```bash
uv run ruff check src/ scripts/ tests/                    # All checks passed
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q          # 109 passed
PYTHONPATH=. .venv/bin/python -m pytest tests/test_dedup.py -q  # 12 passed
```

After Step 3 (2026-11-07):

```bash
uv run ruff check src/ scripts/ tests/                    # All checks passed
PYTHONPATH=. uv run pytest tests/ -q                       # 135 passed
PYTHONPATH=. uv run pytest \
  tests/test_gold.py tests/test_silver.py \
  tests/test_api.py tests/test_seed.py -q                  # 44 passed
PYTHONPATH=. uv run python scripts/seed_data.py            # 800 jobs, 700 salaried, 7 marts
```

Committed baseline (2026-11-07):

```bash
git rev-list --count HEAD      # 6
git log --oneline -1           # Step 4 live-ingestion salary fixes
git status --short             # clean
```

After Step 4 (2026-11-07, scratch):

```bash
PYTHONPATH=. uv run pytest tests/ -q          # 155 passed
uv run ruff check src/ scripts/ tests/       # All checks passed

# keyless-6 scratch run, no R2:
LUMINA_DATA_DIR=/tmp/opencode/lumina-step4/data \
LUMINA_STATE_FILE=/tmp/opencode/lumina-step4/state/ingestion_state.json \
PYTHONPATH=. uv run python /tmp/opencode/lumina-step4/run_stages.py

# isolation:
diff preflight-checksums.txt postflight_run3-checksums.txt   # identical
grep -E "Cloud Sync|Uploading|R2" ingest_run3.log              # no matches
```

Run 3 Gold check:

```text
market: total_jobs=3269, jobs_with_salary=96, salary_coverage_rate=0.0294,
        total_unique_skills=250, average_salary_usd=153903.27,
        median_salary_usd=157500.00, top_source_count=5
marts:  single_skill_roi=156, skill_demand=250, skill_overlap=74,
        skill_related=8189, salary_distribution=387, top_skills=10
HN:     224 rows, 67 explicit salary tokens, 62 parsed, 0 hourly misclassified
API:    11/11 endpoints returned 200
```

Mart check after regeneration:

```text
market_overview_mart  (7, 2)
skill_demand_mart     (82, 3)   skill, job_demand_count, job_share
skill_overlap_mart    (689, 5)  includes combo_size
salary_distribution_mart (269, 4) includes bucket_order
market: total_jobs=800, jobs_with_salary=700, salary_coverage_rate=0.875,
        total_unique_skills=82, average_salary_usd=129101.54,
        median_salary_usd=128069.10, top_source_count=6
```

Direct reproductions:

```python
# Currency — fixed in Step 2.1
_parse_salary("$70000 - $90000", "GBP", "annual")   # -> GBP, 88,900–114,300 USD equivalent
_detect_currency("EUR 80,000")                       # -> EUR
_parse_salary("INR 500000", "INR", "annual")         # -> INR, 6,000 USD equivalent

# Dedup — fixed in Step 2.2: 3 distinct rows -> 3 (was 1)

# Gold hygiene — fixed in Step 3
"aws solutions architect" -> "AWS Solutions Architect"
# one empty skills_list: no null skill group reaches the marts
# /skills/Python/related?limit=10 -> 10 entries, 10 unique skills
# salary buckets: [< $50k, $50k - $75k, ...] in numeric order
# salary-less jobs: score in skill_demand_mart, excluded from salary marts
```

API observations:

```text
200  /api/v1/skills/nope/salary-distribution   -> {"skill":"nope","distribution":[]}
404  /api/v1/skills/nope
200  /api/v1/skills/roi                        -> 82 skills
200  /api/v1/skills/Python                     -> 10 related skills, no duplicates
200  /api/v1/skills/demand?limit=3             -> AWS/Python/Java with job_share ~0.086
```

---

## 12. Limitations of This Review

- Live ingestion has been run once into scratch (2026-11-07, keyless 6, twice after fixes). It has **not** been run
  against Adzuna/USAJobs or the default demo data, and the scratch run is not scheduled. The live numbers in this
  document come from `/tmp/opencode/lumina-step4/results.md`, not from committed artifacts.
- Related-skill uniqueness was re-measured in Step 1: the pre-Step 1 demo returned 6 unique skills from 10 entries,
  and the regenerated demo returns 7; the earlier “5 unique” figure was incorrect.
- Adapter behavior was verified by reading the code and by targeted unit calls for most adapters; HackerNews was also
  exercised against live comments in Step 4. The other network adapters were not independently validated beyond
  successful fetches.
- API latency was measured in-process with `TestClient`, not over HTTP or through the production container.
- Docker images were not built; Docker findings are based on Dockerfile/compose inspection and local context size.
- The R2 test was executed locally and succeeded, confirming the bucket is reachable; no production data was uploaded.
- The repository has no coverage report; “untested” means no test file references the module.
- Salary parsing is now exercised against live payloads. Dot-grouped thousands (`80.000 EUR`), European decimal
  commas (`$35,3k` read as `353k`), and the loose `¥`→CNY `cn` heuristic remain known gaps. In the Step 4 run, 126
  rows had a raw salary token; 101 parsed (80.2%). Currency mix was USD-dominant, so CNY/JPY behavior was not
  exercised.
- `TITLE_ACRONYMS` is a finite explicit list; unlisted acronyms and product names are still title-cased.
- Demand and related counts exclude rows with a null `external_id` (`G-02`), and combo keys are joined strings (`G-01`).
