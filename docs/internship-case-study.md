# Internship case study

## Problem

Multi-store apparel teams often reconcile Excel extracts by hand. Inconsistent dates, unknown SKU codes and duplicates create conflicting sales totals. Slow stock ties up capital while high-demand positions run low. Reorder decisions can become difficult to explain or trace.

## Solution and implementation

RetailPilot AI is a React/FastAPI modular application with PostgreSQL persistence. It ingests XLSX/CSV, validates physical spreadsheet rows, supports column mapping and persists accepted transactions only after review. Shared Python services compute sales and stock KPIs, export nine management reports, classify inventory and calculate supplier-aware reorders. Manager permissions and a state machine govern simulated purchasing drafts. A read-only deterministic analyst resolves common retail questions without requiring an LLM subscription. Optional provider routing is limited to an allowlist. Four demand baselines use chronological backtests. A separate local ERP simulator demonstrates real authenticated HTTP mapping and pagination.

## Technical skills demonstrated

| Internship area | Concrete evidence |
|---|---|
| Excel and MIS | Multi-sheet import, column review, row errors, reusable XLSX/PDF reporting |
| Data/reporting automation | Import-triggered reports, stock checks, weekly comparisons, persisted execution states |
| Python | FastAPI transport, Pandas transformations, SQLAlchemy models, NumPy forecasts, OpenPyXL exports |
| API integrations | Bearer-authenticated, paginated local ERP with timeouts, mapping and review-first synchronization |
| Practical AI | Validated analytical tool routing, deterministic fallback, baseline comparison and transparent evidence |
| Quality/security | Known numerical fixtures, role/tenant checks, duplicate prevention, export injection protection and browser journeys |

## Evidence

See [verification.md](verification.md) for actual executed commands, test counts and verified runtime. Screenshots in [screenshots](screenshots) come from the running application, not design mockups. The supplied incremental workbook has 15 accepted records, four deliberate rejections and a precisely calculated revenue increment of INR 55,532.25. The dataset uses seed 271828, with 12 fictional stores, 180 products, 360 variants and 12 months of historical sales. It contains no real customer/employee records.

No unsupported productivity percentage, stockout reduction, financial return or production-readiness claim is made. Business value is demonstrated through a reproducible workflow and traceable calculations; actual organizational impact would require a controlled pilot.

## Honest limitations and next work

The shipped identity flow is isolated demo identity, not organizational SSO. The task runner and limiter are single-process; large installations need a durable queue, shared quotas and SQL aggregation. Full accounting reconciliation, FIFO lots, commercial ERP credentials, real notification consent, RAG and committed stock transfers are outside the current demonstrator. Baselines are evaluated, but trained-model superiority is not claimed. Public deployment and GitHub publication are only complete when verified URLs exist.

Next priorities: production OIDC and tenant retention; distributed workflow/outbox handling; stress and security review; reconciliation against a consenting organization's staging extracts; then separately evaluated advanced models or retrieval only if they solve a measured problem.

## Portfolio description (under 150 words)

RetailPilot AI is a retail operations and business automation platform built with React, TypeScript, FastAPI and PostgreSQL. It transforms Excel/CSV extracts into validated business records, calculates sales and inventory KPIs, and generates formatted Excel and PDF MIS reports. Its explainable stock engine accounts for demand, supplier lead times, reservations, inbound orders and pack sizes. Managers review recommendations through an audited approval workflow that creates simulated purchase drafts. Four forecasting baselines use chronological backtests, while a read-only analytical assistant answers supported questions without paid APIs. A separate authenticated HTTP ERP simulator demonstrates mapping and paginated synchronization. Reproducible fictional data, numerical fixtures and browser journeys show the complete spreadsheet-to-decision process. The project demonstrates Excel/MIS automation, Python engineering, API integration and practical, controlled AI workflows.
