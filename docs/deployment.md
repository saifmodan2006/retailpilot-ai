# Free-tier deployment

Budget: **INR 0**. No paid plans, billing methods, paid overages, Cloudflare Containers or worker services are required.

Cloudflare Pages Free serves React/Vite. Browser requests go directly to Render Free native Python FastAPI over HTTPS. Neon Free stores business records, imports, reports, workflow state and audit events. Render's ephemeral filesystem is not a business datastore. The ERP simulator remains available locally in Docker Compose and is disconnected publicly; external LLMs are disabled publicly.

## Cloudflare Pages

Source: `saifmodan2006/retailpilot-ai`, branch `main`. Root directory **frontend**, build command **npm run build**, output **dist**, `NODE_VERSION=24`. Set production `VITE_API_URL` to the actual Render origin, without `/api/v1` or a trailing slash. This is a public URL, never a secret. `_redirects` supports workspace refreshes; `_headers` provides CSP and frame restrictions. Update its explicit `connect-src` hostname if the API origin changes. Preview deployment is disabled to keep preview code away from the shared demo database.

## Render Free

Create a Web Service, GitHub source, branch main, language **Python 3**, region **Oregon**, compute **Free ($0/month, 512 MB)**. Leave Root Directory empty: the backend needs repository `sample_data`. Build:

```sh
pip install -r backend/requirements.runtime.txt
```

Start:

```sh
cd backend && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --limit-concurrency 12 --timeout-keep-alive 5 --no-proxy-headers
```

Health check **/api/v1/health**. Startup runs migrations; no paid pre-deploy command is needed. Keep automatic deploy off while validating. `render.yaml` records these native Python settings. `Dockerfile.release` is an optional same-origin image for existing Docker hosts and local resource tests, not the selected public architecture.

Set through Render's environment editor, never Git:

| Variable | Value |
|---|---|
| PYTHON_VERSION | 3.12.15 |
| DATABASE_URL | Dedicated Neon pooled TLS connection URL |
| JWT_SECRET | Render-generated stable high-entropy secret |
| PUBLIC_DEMO / DEMO_ENABLED | true / true |
| DEMO_TTL_HOURS / DEMO_MAX_TENANTS | 2 / 4 |
| CORS_ORIGINS | Exact production Pages origin |
| ERP_URL | Empty |
| LLM_ENABLED | false |
| OPENBLAS_NUM_THREADS / OMP_NUM_THREADS | 1 / 1 |
| MALLOC_ARENA_MAX | 2 |

## Neon Free

Create a dedicated PostgreSQL-only project on **Free** in AWS Oregon. Leave additional services off. Use the pooled connection string with **sslmode=require**. Standard postgres/postgresql URLs are normalized to SQLAlchemy's psycopg driver. Public-demo Neon connections without required TLS are rejected. The pool uses two connections, zero overflow, pre-ping, 15-second connection timeout and five-minute recycle. Prepared statements are disabled for transaction-pool compatibility. Alembic applies transactional migrations at startup. Never use a private project's database.

The console displayed **1 GB storage per project** on 20 October 2026. Check current console allowances before future launches. Measure actual storage in Neon SQL Editor after seeding:

```sql
SELECT pg_size_pretty(pg_database_size(current_database())) AS database_size;
SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;
```

The isolated local PostgreSQL check used **38,303,411 bytes** after one full tenant, imported rows, saved reports and an empty tenant. Four tenants leave headroom; WAL/history, indexes and traffic still require monitoring. Expired marked demo tenants are deleted on later session admission. This is bounded demo lifecycle management, not backups or unattended maintenance.

## Memory and background work

Public API computations are serialized in one process. Uvicorn concurrency, uploads, expanded XLSX size and row counts are bounded. Runtime dependencies exclude unused scikit-learn and development tools. Analytics reads typed tuples and pushes store/SKU filters into SQL, avoiding large row dictionaries and Decimal allocations. Reports and background workflows run inside the web service; no separate free-tier worker or hosted cron is claimed. PostgreSQL retains execution state; interrupted jobs become explicitly retryable on restart.

The complete local browser journey passed with a **512 MB hard cgroup limit**, peak **242,954,240 bytes (~232 MiB)**, no OOM and zero restarts. Render CPU/network/cold starts need separate live verification. Public uploads accept only supplied fictional samples, which are much smaller than the private local parser's maximum.

## Operational limits and validation

Render Free sleeps after inactivity and shares monthly runtime limits across the account's free web services. Existing services may consume that allowance; do not delete or upgrade them. Neon also scales to zero. Do not use keep-alive traffic to imply an always-on service. The API health endpoint checks its database.

Verify HTTPS, exact CORS, direct workspace refresh, all pages, import ? validation ? import ? reorder ? approval ? XLSX/PDF ? analyst, tenant isolation, denied arbitrary uploads, persistence and an explicit service restart. Configuration is not deployment proof; actual results belong in [verification.md](verification.md).

Official references: [Cloudflare React Pages](https://developers.cloudflare.com/pages/framework-guides/deploy-a-react-site/), [Render Free](https://render.com/docs/free), [Render Python](https://render.com/docs/python-version), [Neon Free storage announcement](https://neon.com/blog/neon-free-plan-1-gb-per-project).
