# Release verification - 20 October 2026

These are executed checks against the actual application, not a production certification.

## Verified public endpoints

- Frontend: https://retailpilot-ai.pages.dev/
- FastAPI health: https://retailpilot-ai-api.onrender.com/api/v1/health
- Public source: https://github.com/saifmodan2006/retailpilot-ai
- CI: https://github.com/saifmodan2006/retailpilot-ai/actions

Cloudflare Pages serves React/Vite; Render Free runs native FastAPI; isolated Neon Free PostgreSQL holds the data. Render's service page and Neon's console both show Free. No paid plan, billing method, paid overage, Cloudflare Container, hosted worker or private business resource was created or connected.

## Executed checks

| Check | Actual outcome |
|---|---|
| Backend numerical, ingestion, authorization, tenant, workflow, forecast and export fixtures | **54 passed**, one upstream Starlette/httpx deprecation warning |
| Ruff / ESLint | Passed |
| Strict TypeScript and Vite production build | Passed locally, in Docker and in GitHub CI |
| Latest local Docker Playwright journey | **2 passed in 1.8 minutes** |
| Final public Playwright journey, including cleanup of disposable sessions | **2 passed in 3.5 minutes** |
| Expanded public acceptance | **25 checks and all 12 workspace routes passed**, including a deliberate service redeployment |
| Responsive visual matrix | **52 captures**: 13 routes including landing, at 1440x900, 1280x800, 768x1024 and 390x844; no document overflow or role alerts |
| Targeted automated accessibility | **13 routes, zero violations** for checked WCAG 2/2.1 A/AA rules; four incomplete checks remain manual |
| Local HTTP/ERP smoke | **16 checks passed**, including real authenticated paginated HTTP to the separate fictional simulator |
| Local persistence after backend restart | Passed: saved metrics, sales records and report download remained available |
| Public persistence after redeployment | Passed: original signed session, metrics, records, report exports, idempotent import and analyst still worked |
| Full 4,320-row inventory XLSX/PDF in a hard 512 MB container | Passed; memory peak **259,801,088 bytes (~248 MiB)** |
| Large export timing | XLSX **3.69 seconds / 241,350 bytes**; PDF **20.89 seconds / 402,328 bytes** |
| Live bounded seed | **63.719 seconds**, exact manifest counts, unchanged baseline revenue and inventory value |
| Live Neon storage checkpoint | **123,133,952 bytes (117 MB per console)** at four demo tenants / 195,246 sales rows; displayed Free allowance **1 GB** |
| Python runtime dependency advisory audit | No known vulnerabilities after patching three packages |
| npm audit | Zero findings |
| Tracked-file secret scan | Passed, including ZIP/XLSX members and comparison with ignored local secrets |
| Genuine idle wake-up | After **960 seconds** without test-generated requests: **43.093 seconds**, HTTP 200; warm probe **0.516 seconds**. Render shutdown observed before wake. |

The full workflow verifies 15 accepted and four rejected workbook rows, an exact INR 55,532.25 revenue increment, explained recommendations, analyst approval denial, manager approval, simulated drafts, formatted XLSX/PDF, all six deterministic analyst tools, forecasting and the audit trail. No actual supplier order or external notification is sent.

The public acceptance also verifies another real demo tenant's report returns 404, arbitrary uploads return 403, unauthenticated analytics returns 401, exact CORS origin enforcement, disabled public OpenAPI pages, direct route navigation, browser refresh and session revocation. Starting a replacement public workspace ends its prior demo session. Ended/expired fictional data is reclaimed on later admission.

## Evidence artifacts

- [Public HTTP/browser/persistence checks](public-runtime-verification.json)
- [Public route screenshots](screenshots/public)
- [Visual matrix results](screenshots/after/evidence.json) and [before captures](screenshots/before)
- [Neon SQL storage result](neon-storage-verification.json)
- [512 MB export profile](export-resource-verification.json)
- [Live seed measurement](seed-performance-verification.json)
- [Idle wake-up measurement](cold-start-verification.json)
- [Dependency audit](dependency-audit.json)
- [Targeted accessibility results](accessibility-verification.json)
- [Local simulator/runtime evidence](runtime-verification.json)
- [Targeted release audit](release-audit.md)

A first matrix exposed responsive overflow; table positioning and KPI sizing were repaired and the entire matrix rerun. A local parallel-seeding check exposed an overly small connection budget outside public mode; the strict pool is now public-only, local capacity is bounded separately, and the local journey was rerun sequentially. Seeding now uses bounded SQLAlchemy insertmanyvalues batches rather than per-row driver execution. Local seed observations fell from roughly 85-88 seconds to 55 seconds; these are individual run timings, not a controlled performance study.

The initial dependency scan reported 29 advisory records, including duplicate entries, across pydantic-settings, PyJWT and python-multipart. Exact pins were upgraded to **2.16.0**, **2.15.1** and **0.0.32**. The full tests and advisory audit were repeated successfully. CI now enforces the advisory check. Interpreter configuration is pinned to Python **3.12.15**, the security patch used by CI and the current Docker base.

## Reproduce

```powershell
.\.venv\Scripts\python -m pytest backend/tests -q
.\.venv\Scripts\ruff check backend
.\.venv\Scripts\python scripts/security-scan.py
cd frontend
npm run lint
npm run build
npm run test:e2e
node scripts/visual-audit.mjs after
cd ..
.\.venv\Scripts\python scripts/run-accessibility.py
```

The browser tests target localhost by default. For public verification, set `E2E_BASE_URL` to the Pages origin and `E2E_API_URL` to the Render origin. `scripts/public-verify.mjs` uses a disposable fictional session, pauses for an operator-authorized Render restart, then checks persistence and ends that session. Tokens remain in process memory. The current free-capacity limit may require waiting for a prior session to end or expire; do not create more resources or raise quotas to bypass it.

## Honest boundaries

The public exhibit uses isolated demo identity, not organizational SSO. Its limiter and task runner support one process. Backend fixtures use temporary SQLite; PostgreSQL is exercised by real migrations, local HTTP journeys, public tenant checks and restart/persistence checks. No distributed load guarantee, independent penetration test or full screen-reader/WCAG certification is claimed. The ERP simulator is verified locally and intentionally disconnected publicly. Commercial ERP, paid-LLM execution, real messaging, FIFO cost lots, document RAG and autonomous purchasing are not shipped or claimed.

Dependency audits are point-in-time known-advisory checks, not proof against unknown vulnerabilities. The build retains harmless upstream Zod comment-annotation notices. Vendor splitting keeps each emitted JavaScript chunk below 500 kB. PDF inventory exports select six key columns for legibility while retaining all rows; XLSX keeps the full report columns. Free hosting can sleep, shares account allowances and needs monitored storage/compute usage. Named volumes and managed persistence are not backup/restore certification. No real company, employee or customer data was used.
