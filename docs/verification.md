# Release verification ? 20 October 2026

Current release checks, executed locally before public deployment:

| Check | Actual outcome |
|---|---|
| Backend tests | **53 passed**, one upstream Starlette/httpx deprecation warning |
| Ruff / ESLint | Passed |
| Strict TypeScript + production build | Passed; split bundles all below 500 kB |
| Public-demo browser journey, hard 512 MB container | **2 passed in 1.8 minutes** |
| Measured cgroup memory peak | **242,954,240 bytes**, no OOM, zero restarts |
| Isolated PostgreSQL size | **38,303,411 bytes** after full journey + empty tenant |
| Visual route matrix | **52 captures**, 13 routes ? 4 viewports; no document overflow or role alerts |
| Staged source scan | Passed, including ZIP/XLSX members and comparison with ignored local secrets |
| GitHub CI / public URLs | Pending live release verification below |

The browser journey exercises the real API: 15 accepted / 4 rejected rows, INR 55,532.25 revenue increment, recommendation rationale, manager approval, simulated draft, MIS XLSX download, deterministic analyst, forecast and audit. The public-demo configuration accepts only supplied fictional workbooks. The local simulator remains supported separately; it is disabled on the chosen free public architecture. A local memory-constrained container is resource evidence, not a claim of a Render deployment.

Visual evidence: [before](screenshots/before/evidence.json), [after](screenshots/after/evidence.json). All captures are from the running application; the marketing preview uses its actual calculated overview. The first matrix found overflow; table positioning and KPI sizing were repaired and the entire matrix rerun successfully.

Security review repaired explicit demo-tenant boundaries, expiring public sessions, bounded tenant/write quotas, strict JWT claims, pre-parser body limits, workbook expansion/formula/header checks, strict dates/monetary bounds, governed approval cancellation and forecast version deduplication. This is a targeted portfolio release review, not an independent penetration test or production certification.

## Historical MVP checks (19 October)


Verified locally on **19 October 2026**, Asia/Kolkata. This report records executed checks, not a production certification.

| Check | Actual result |
|---|---|
| Python numerical, ingestion, security, forecasting, workflow and export tests | **37 passed, 0 failed** |
| Playwright against production Docker frontend/backend | **2 passed, 0 failed in 58.6 seconds** |
| Ruff | Passed for backend and scripts |
| ESLint | Passed |
| TypeScript strict check and Vite production build | Passed on host and inside frontend Docker build |
| Docker images | Backend, frontend and independent ERP built successfully |
| Docker health | PostgreSQL, backend, frontend and ERP all healthy |
| API runtime smoke | **16 checks passed**, including six analytical tools and real HTTP ERP pagination |
| Persistence | Saved report metrics and sales records remained available after backend container recreation; report download returned HTTP 200 |
| GitHub Actions | Workflow supplied; no remote CI execution claimed |
| Public deployment | Not performed; no public infrastructure/URL configured |
| GitHub publication | Local Git repository initialized; no remote repository published |
| Optional paid LLM | Not configured or live-tested; deterministic analyst verified |

The final container run completed the full Excel-to-MIS/approval/analyst/forecast/audit journey in 56.7 seconds and the isolated mobile navigation journey in 973 milliseconds. Container verification exposed and fixed an immediate-read transaction race: default request-scoped database cleanup could commit after response transmission, allowing a rapid query refresh to read the previous approval state. Database dependencies now use FastAPI **function scope**, committing before response delivery. The passing container result supersedes intermediate failed runs.

## Commands actually executed

```text
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
.venv/Scripts/python scripts/setup-env.py
docker compose up -d db
# From backend:
../.venv/Scripts/python -m alembic upgrade head
# From root:
.venv/Scripts/python -m pytest -q
.venv/Scripts/ruff check backend scripts
.venv/Scripts/python scripts/generate_samples.py
.venv/Scripts/python scripts/export_demo_dataset.py
# From frontend:
npm install
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
# From root:
docker compose up --build -d
.venv/Scripts/python scripts/verify_runtime.py check
docker compose up --build -d backend
.venv/Scripts/python scripts/verify_runtime.py persistence
docker compose ps
```

## What was exercised

Known fixtures prove net revenue INR 5,310, gross profit INR 2,950, 59 net units, inventory at cost INR 5,200 and inactive inventory INR 5,000. A position with 5 on hand, 1 reserved and two daily demand units has two days of cover and a 30-unit reorder under the fixture lead/safety/pack assumptions. Only confirmed inbound reduces that reorder. A stale approval cannot create a purchase order. Duplicate uploads and transaction IDs cannot add sales twice. All nine report types generate actual PDF files, and the daily XLSX summary/table totals match the metric service. Tenant A cannot read or approve tenant B's objects.

Forecast instrumentation verifies holdout origins receive lengths 69, 76 and 83 for a 90-day series, rather than future data. Model/error tests cover constant demand and nullable WAPE semantics. API validation checks reject invalid dates/IDs/numerics and unsupported analyst operations. Workflow tests exercise failure, safe retry, idempotent keys and invalid terminal transitions. Independent HTTP adapter tests cover authentication headers, mapping and pagination; runtime checks fetched 25 products and 25 sales in three actual HTTP pages.

`runtime-verification.json` records the 16 runtime checks, stored report reference and persistence result. It contains fictional business metrics and internal demo references, never bearer tokens or provider secrets.

## Screenshots

All PNGs are captured from the running application by Playwright. Charts disable entry animation so evidence captures the complete data series. Files include landing, overview, multi-sheet validation, recommendation evidence, manager approval, analyst response, forecasts and the mobile landing. Screenshots are not synthetic artwork.

## Verification limits

Backend fixtures run on temporary SQLite; PostgreSQL is exercised through migrations, API smoke, the browser journey and persistence checks. No PostgreSQL concurrency stress/load test, full accessibility certification, external scheduler installation, commercial ERP connection, real notification sending, live paid-LLM evaluation or public-site acceptance test is claimed. No real user/customer data was used.

The Python suite emits one upstream Starlette/httpx TestClient deprecation warning. The production bundle emits a size advisory (about 886 kB uncompressed / 266 kB gzip before HTTP caching) and Zod comment-annotation advisories; these do not fail the build. Route/vendor code splitting is an optimization for a future iteration. The generated npm install audit reported zero vulnerabilities at execution time; this is not a security audit of the application.
