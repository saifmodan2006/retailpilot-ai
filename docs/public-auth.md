# Public registration and Google sign-in

Release verification, 22 October 2026. The existing retail application is preserved.
This report distinguishes implemented behavior from live provider configuration.

## Implemented and tested

- Open registration mode removes the email allowlist, with verified identity and current organization membership still required. Restricted mode remains the default.
- Continue with Google uses the official Supabase Python SDK, PKCE S256 and a single-use, ten-minute, browser-bound challenge. The callback exchanges the code on the API. Google API tokens are discarded; application sessions remain encrypted in PostgreSQL behind an HttpOnly cookie.
- Google requests only `openid email profile`. It does not connect Gmail, Drive, Calendar or an ERP.
- Cloudflare Turnstile tokens pass to Supabase Auth on email signup, login, recovery, resend and password reauthentication. Public email signup refuses to start without configured CAPTCHA and custom SMTP flags. These flags describe operator verification, not automatic proof of email delivery.
- An operator-owned Supabase hook supports closed, restricted and open registration. Google-only opening is possible while SMTP is unavailable. The hook and API each retain bounded account capacity; open access does not promise unlimited free hosting.
- Privacy information is available at `/privacy/`. Provider secrets never belong in frontend build variables.

Latest release CI: **90 backend tests**, **seven Playwright scenarios**, frontend lint, TypeScript and production build. The isolated Google browser scenario mocks the external identity exchange; real provider checks are recorded separately below. Playwright also covers the original upload, validation, import, recommendation, approval, MIS export and analyst journey.

PostgreSQL migration and backup/restore checks passed:

- [Retail schema preservation](public-auth-migration-verification.json)
- [Existing account/session preservation](oauth-account-preservation.json): all 27 existing tables retained matching fingerprints; only `oauth_challenges` was added, with no Alembic drift.
- [Registration hook checks](registration-policy-verification.json): the actual policy SQL passed restricted/open/Google-only/closed, capacity and anonymous-denial checks under the Auth service role in disposable PostgreSQL. Run with `python scripts/check-registration-policy.py` against the local Compose DB; fixtures and roles roll back.
- [Managed Neon checkpoint](neon-public-auth-checkpoint.json) was queried before the production OAuth migration. No production restore was performed.

## Live configuration status

Public registration is active. Both admission checks accept any verified email/Google
identity, subject to 100 accounts and 100 private workspaces. Google is published to
external users. Google sign-in and custom email delivery passed real provider checks.

API source `7305e7e` deployed on Render as `dep-dbcu286q1p3s73dai17g`,
with Google and custom-SMTP capability flags enabled. The additive `c8d3` to `d9e4`
migration remains intact. [Release CI](https://github.com/saifmodan2006/retailpilot-ai/actions/runs/39671130190)
passed all 90 backend and seven browser scenarios, lint, builds, proxy checks and dependency audits.
The new registration hook was installed in restricted mode and its live grants
were checked: Auth service SELECT/EXECUTE allowed, anonymous access denied,
non-admitted identity rejected with 403, and the existing single identity retained.
The managed SQL role does not permit `SET ROLE supabase_auth_admin`; no permissions
were expanded to bypass that restriction. Service-role execution was tested locally.

Cloudflare Pages now serves source `7305e7e`, deployment
`5e99f30b-3b80-472e-81ae-9356ee949e82`; the delayed GitHub delivery was resolved
by retrying the exact source deployment. The live signup, login, callback and privacy
pages passed accessibility/overflow checks at 1440, 768 and 390 pixels, and anonymous
onboarding redirects to login. See [live browser evidence](saas-public-browser-verification.json).
The current `7305e7e` deployment passed both live demo Playwright scenarios in
3.3 minutes: Excel validation/import, exact revenue increment, recommendations,
manager approval, XLSX MIS export, deterministic analyst, forecasting, audit log
and mobile navigation. Historical checks remain separately dated in
[the earlier deployment evidence](public-oauth-release-verification.json).

- The dedicated free Turnstile widget is enabled in both the API and Supabase Auth. Automated Chrome initially received error `300030`; the owner completed the normal browser check, producing a real token. The protected recovery request was accepted and its email arrived. No challenge bypass, test key or pre-clearance was used.
- Gmail custom SMTP is saved in Supabase only. The exposed older app password was revoked, and the owner created its replacement. Actual verification delivery, signup OTP verification and recovery delivery passed. The replacement credential is absent from source and evidence. Final password reset was not performed because it requires the owner to choose a password.
- Confirmation and recovery templates use the provider's one-time `{{ .Token }}` code, supported by the existing verification pages. Versioned templates: [confirmation](../deployment/email-confirmation.html), [recovery](../deployment/email-recovery.html). This also supports resends after an earlier browser PKCE challenge expires.
- Google granted the requested non-paid project quota. Dedicated project `retailpilot-ai-512319` and its web client were created; the owner performed the credential-creation click. The client secret was transferred directly to Supabase. Its only scopes are OpenID, email and profile, with no sensitive/restricted scopes. Real owner Google consent, browser-bound callback and access to the existing private workspace passed; the identity count stayed at one.
- The user-approved Flask-Project shutdown completed, with scheduled deletion on 20 November 2026. Its OAuth client was not reused. No billing or paid service was added.
- Owner onboarding, fictional seeding and page refresh passed. Production SQL measured **88,973,312 database bytes**, one account, one membership, two organizations including the legacy demo, 97,608 fictional sales and 4,320 inventory snapshots. Dashboard project storage was 99.42 MB; that metric can lag and includes a different scope. This fits even a conservative 500 MB storage budget. Global sample seeding remains bounded to 400,000 sales rows.

[Measured live provider evidence](live-provider-verification.json) distinguishes the real
checks above from mocked tests. A QA address outside the former allowlist completed
public signup, received its verification email and reached onboarding after OTP verification.
Its hosted private retail journey remains pending activation and a renewed login;
the read-only live browser audit verified open admission,
the Google button, SMTP/CAPTCHA capability flags and all twelve responsive page checks.
Personal Gmail SMTP has
limited sending capacity and no delivery SLA; it is appropriate only for a small portfolio demo.

## Activation sequence

1. Verify the Neon recovery branch, deploy the additive migration/backend and frontend with existing restricted flags, and confirm health and existing demo behavior.
2. Set Render `CAPTCHA_ENABLED=true` and `CAPTCHA_SITE_KEY` to the dedicated public site key. Deploy, check that the widget renders, then enable Turnstile in Supabase Auth using its matching secret. No CAPTCHA secret is needed in frontend or Render.
3. Configure Supabase custom SMTP: sender `RetailPilot AI`, operator-owned sender address, `smtp.gmail.com`, TLS port `465`, the same Gmail username and an app password held only in Supabase's SMTP secret field. Keep confirmation enabled. Test actual receipt and same-browser verification/recovery before `EMAIL_DELIVERY_CONFIGURED=true`.
4. After Google grants project capacity, create a dedicated RetailPilot OAuth project and Web client. Set the authorized JavaScript origin to `https://retailpilot-ai.pages.dev` and redirect URI to `https://pbenydajktfdbtuzfowq.supabase.co/auth/v1/callback`. Request only basic identity scopes. Save the client ID and secret only in Supabase's Google provider, then set Render `GOOGLE_AUTH_ENABLED=true`. Do not add billing or paid APIs.
5. Install [the registration policy](../deployment/supabase-registration-policy.sql) in the dedicated Supabase Auth database, initially restricted. It assumes the existing `auth_hooks.pilot_allowlist` and schema grants. Test the hook with the Auth service role and retain public/anonymous denial.
6. Once a usable verified method is tested, set the hook to open and Render `REGISTRATION_MODE=open`, `REGISTRATION_ENABLED=true`. For email signup use `EMAIL_SIGNUP_ENABLED=true` only after SMTP/CAPTCHA verification; for Google-only opening use false. Raise the bounded API/hook user cap together as storage permits, and review the global organization capacity. Real uploads stay disabled.
7. Test an eligible address outside the former allowlist, duplicate-account behavior, Google callback replay, cold start, refresh, tenant denial, account recovery and existing retail exports. Record actual URLs and deployed source revisions.

Do not enable public email signup using Supabase's default team-only SMTP. Free Gmail delivery is quota-limited and suitable only for a small portfolio demonstration; no delivery SLA or unlimited account capacity is promised. Manual team invitation links remain manually shared; custom Auth SMTP does not implement transactional invitation sending.

## Rollback

Return the hook to `restricted` or `closed` and the API to restricted registration to stop new accounts while preserving existing sessions and data. Disable the Google feature flag to hide its button. Keep the stable encryption key and database URL. Do not reverse the forward-only OAuth migration or erase business tables.

References: [Supabase SMTP](https://supabase.com/docs/guides/auth/auth-smtp), [Google through Supabase](https://supabase.com/docs/guides/auth/social-login/auth-google), [Google project deletion and quotas](https://docs.cloud.google.com/resource-manager/docs/delete-restore-projects).
