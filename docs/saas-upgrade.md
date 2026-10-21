# Persistent accounts release

## 1. Authentication architecture

Supabase Auth is the single managed identity provider. It owns password hashing,
email verification, recovery tokens and provider abuse controls. Neon continues to
store all retail records. Clerk was evaluated but production requires an owned
domain; the existing pages.dev address does not meet that prerequisite.

The browser communicates with a same-origin `/api/v1` proxy on Cloudflare Pages.
FastAPI stores encrypted provider session material in Neon and issues only an
opaque, HttpOnly, SameSite=Lax cookie. Persistent account tokens are never placed
in browser storage. Mutating cookie requests require an exact allowed Origin and
an explicit CSRF header. The existing demo bearer flow remains separate.

Accounts and memberships are additive: `users.id` remains the business actor key
for existing approvals. Each persistent membership has a dedicated actor, and
every business request checks its current active database membership and role.
Changing the selected organization is a validated server session operation.

Migration `c8d3_persistent_accounts` creates six new tables; it does not rewrite
or delete any existing retail table, organization identifier or demo user.
It is forward-only. Before production migration, create and verify a managed
Neon checkpoint or an isolated restorable backup. Keep the old application
revision available: because this migration is additive, application rollback can
leave the new tables intact. A destructive database downgrade is prohibited.

Registration and real uploads default OFF. No paid resources, public account
launch, transactional mail delivery or successful provider configuration is
implied by the presence of account pages. Unconfigured services fail closed.

Provider references:
- https://supabase.com/docs/guides/auth/auth-email-templates
- https://supabase.com/docs/guides/auth/sessions
- https://supabase.com/docs/guides/auth/auth-smtp
- https://clerk.com/docs/guides/development/deployment/production

## 2. Provider configuration

The free Supabase project `retailpilot-ai-auth` (`pbenydajktfdbtuzfowq`, Oregon)
uses confirmed email, default email templates and official SDK PKCE exchange.
An encrypted server-side verifier and expiring HttpOnly challenge cookie bind
email links to the requesting browser. Callback query/fragment data is cleared.
Recovery sessions cannot access retail APIs. The Data API, anonymous sign-ins,
manual linking and Google are disabled. Global signup remains closed.

Site URL: `https://retailpilot-ai.pages.dev`. Allowed redirects on that origin:
`/auth/callback`, `/auth/verify`, `/auth/recovery`, `/auth/reset-password`.
The enabled Before User Created hook additionally enforces an operator-maintained
email allowlist and ten-user ceiling. Reproducible SQL:
[supabase-pilot-hook.sql](../deployment/supabase-pilot-hook.sql).
No service-role key is used. Default mail is restricted to project-team recipients
and low delivery limits; custom SMTP is absent. Default-template editing required
custom SMTP or a paid upgrade, so supported PKCE email links are used instead.

## 3. Implemented account features

Verified signup/login, logout, recovery/reset, persistent profile, initials avatar,
timezone, verified email changes, current-password reauthentication, session
listing/revocation, workspace restoration, invitations and deletion requests.
Deletion requests immediately revoke access; physical erasure needs operator
review. Final owners must transfer ownership or close the organization first.
Personal deletion does not delete a business organization.

## 4. Pages and components

Signup, login, verification, callback, forgot password, recovery, reset password,
expired session, invitation response, resumable onboarding, profile, account
settings, workspaces, organization settings and team management. The workspace
shell adds an account menu, profile avatar, organization selector and signout.
Business settings include stores and planning; authorized supplier settings remain.
Screenshots: [account captures](screenshots/accounts/).

## 5. Migration and recovery

The additive migration creates accounts, account_sessions,
authentication_audit_events, identity_challenges, organization_memberships and
organization_invitations. Each membership has a dedicated legacy user actor.
The original business keys and historical approval references remain intact.

A data-and-schema Neon recovery branch was created and queried before production
migration: [checkpoint evidence](neon-account-checkpoint.json). Local PostgreSQL
17.11 independently tested pg_dump/restore, compared all 21 legacy-table
fingerprints and checked Alembic drift: [migration evidence](saas-migration-verification.json).
This is not a claim that a production restoration occurred. Roll back application
code while retaining additive tables, or restore into a separate database and
verify before switching. Destructive downgrade is prohibited.

## 6. Server-enforced role matrix

| Capability | Owner | Admin | Manager | Analyst | Viewer |
|---|---|---|---|---|---|
| Scoped retail reads / analyst tools | Yes | Yes | Yes | Yes | Yes |
| Create MIS reports | Yes | Yes | Yes | Yes | No |
| Import permitted sample files | Yes | Yes | Yes | Organization option | No |
| Approve purchasing recommendations | Yes | Yes | Yes | No | No |
| Planning / suppliers / stock workflows | Yes | Yes | Yes | No | No |
| Business settings / stores | Yes | Yes | No | No | No |
| Manage manager / analyst / viewer members | Yes | Yes | No | No | No |
| Grant owner/admin or manage owners/admins | Yes | No | No | No | No |
| Close organization | Yes | No | No | No | No |

Invitations cannot grant owner; admins cannot invite admins. Final-owner safeguards
apply. Role changes/removal are checked on subsequent requests, not cached tokens.
All members manage their own profile/session and may leave where ownership permits.
Public private-workspace ERP writes and arbitrary uploads remain disabled.

## 7. Verified onboarding walkthrough

Isolated browser tests use real React/FastAPI, a fresh migrated SQLite database
and a provider mock loaded only by the test entrypoint. They verify signup,
confirmation, resumable personal/business/workspace steps, synthetic data,
profile persistence after login, a second organization, switching, invitations,
viewer rejection, analyst approval rejection, member removal and logout.
Separate tests exercise recovery/reset, expiry and default-template PKCE callbacks.
These do not establish a live owner's delivered email lifecycle.

## 8. Security test results

Backend account tests cover exact-origin CSRF, opaque cookies, encrypted provider
tokens, identity/verification rejection, admission caps, refresh persistence,
session expiry/revocation, forged organization access, roles, invitation
expiry/replay/issuer demotion, final owners, closure/deletion and demo isolation.
The actual official SDK exchange is exercised with HTTP MockTransport.
The proxy check verifies its fixed upstream, both permitted cookies, excluded
private cookies/forged headers, no-store, HttpOnly forwarding and outage handling.
Production app.main has no mock identity route or test bypass.

## 9. Regression and responsive verification

The original backend suite remains included. Original browser journeys exercise
upload, validation, commit, reorder, manager approval, MIS, analyst, forecasting,
audit and mobile navigation. Account/auth screens are tested at1440,768 and390px.
Evidence: [workspace accessibility](saas-browser-accessibility.json),
[PKCE responsiveness](saas-pkce-browser-verification.json), screenshots and CI.
All fixtures are fictional. Provider mocks never imply live mail delivery.
Build, TypeScript and lint checks are required. Upstream warnings are not hidden.

## 10. Deployment status and configuration

Status on21 October2026: implementation tested locally; release validation in
progress. Registration remains closed. Public links:
[frontend](https://retailpilot-ai.pages.dev/),
[API health](https://retailpilot-ai-api.onrender.com/api/v1/health),
[GitHub](https://github.com/saifmodan2006/retailpilot-ai).

Pages: root `frontend`, build `npm run build`, output `dist`, Node24,
`VITE_API_URL=https://retailpilot-ai-api.onrender.com`. Pages deploys `functions`;
`_routes.json` limits Functions to `/api/v1/*`; auth/onboarding paths use SPA
redirects. No provider secret is a Vite variable.
Render Free: Python3.12, install `backend/requirements.runtime.txt`, health
`/api/v1/health`, startup/memory limits in [render.yaml](../render.yaml).
Alembic runs before serving. Neon uses TLS and bounded SQLAlchemy pooling.
All business records persist in Neon; ephemeral filesystem is not authoritative.
Actual secrets are managed Render variables; blueprint defaults remain closed.

## 11. Environment variables and reproducible checks

See [.env.example](../.env.example). Existing database URL, JWT secret, exact CORS
and public-demo limits remain required. Account variables:

| Variable | Requirement |
|---|---|
| ACCOUNTS_ENABLED | true only with configured provider and encryption |
| REGISTRATION_ENABLED | false until a restricted pilot is explicitly opened |
| REGISTRATION_ALLOWLIST | Admitted emails; never commit real addresses |
| SUPABASE_URL | Exact HTTPS project URL |
| SUPABASE_PUBLISHABLE_KEY | Managed server configuration; never service-role |
| SESSION_ENCRYPTION_KEY | Stable Fernet secret; rotation requires a migration plan |
| APP_ORIGIN | Exact frontend origin |
| ACCOUNT_COOKIE_SECURE | true on public HTTPS |
| ACCOUNT_MAX_USERS / ACCOUNT_MAX_ORGANIZATIONS | 10 / 4 pilot ceilings |
| REAL_UPLOADS_ENABLED | false for this public portfolio |

Run pytest, Ruff, frontend lint/build and `node scripts/check-api-proxy.mjs`.
The CI workflow documents the isolated test harness: `RETAILPILOT_SAAS_TEST=1`
runs `backend/tests/serve_accounts.py` on loopback8002; Vite5174 uses
`RETAILPILOT_DEV_API=http://127.0.0.1:8002`; Playwright uses `SAAS_E2E=1` and
`E2E_BASE_URL=http://127.0.0.1:5174`. It uses fresh temporary data and test-only
provider responses. Ordinary Compose keeps accounts off. Real local Auth needs
matching localhost redirects/origin/CORS, same-origin proxy and local-only
insecure cookies. Never reuse production secrets for local testing.

## 12. Free-tier and retention limitations

No paid plan, billing method, worker or AI provider was added. Render sleeps and
can cold-start slowly. Bounded in-process tasks keep durable workflow state in
PostgreSQL. One worker, BLAS/OMP limits and row/upload/report/admission caps bound
resources. Earlier MVP measurements peaked around248MiB inside512MiB; this is not
an account load benchmark or reliability guarantee. The checkpoint logical size
was about97MiB, below the1GiB Neon free allowance; ongoing growth needs monitoring.
Supabase default mail is unsuitable for open registration; free projects can
pause. Pages Functions has a daily free allowance.

Sessions expire after8h, maximum5/account. PKCE challenges expire after30min,
invitations after24h, demos after2h. Raw previews expire after7days, generated
exports after30days; cleanup runs on workspace access, not a paid scheduler.
Core retail records remain, with growth caps. Audit/auth logs are bounded.
Physical erasure and business retention require operator review.

## 13. Remaining work and recruiter checklist

- Validate live owner signup, delivered email link, recovery and new login using
  a password entered by the owner. Mocks do not prove email delivery.
- Keep unrestricted signup closed. Additional pilot recipients need admission in
  both allowlists plus suitable email delivery. Invitation emails are not sent;
  the issuer manually shares the single-use link with its named recipient.
- Google OAuth is absent. UI language is English; avatar uses initials.
- Arbitrary/private business uploads stay disabled; synthetic portfolio data only.
- Account deletion is an access-revoking request with operator-reviewed erasure.
- No third-party ERP integration or autonomous purchasing/AI write is claimed.
- Before submission: check public health/current CI, complete the guided demo,
  remove credentials from screenshots and disclose cold starts and these limits.

Portfolio description: RetailPilot AI connects spreadsheet validation, inventory
planning, approval controls and management reporting in a React/FastAPI app. Its
persistent-account pilot adds managed identity, organizations, invitations and
database membership checks while retaining an isolated fictional demonstration.
