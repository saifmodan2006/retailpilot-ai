# Public registration and Google sign-in

Release preparation, 21 October 2026. The existing retail application is preserved.
This report distinguishes implemented behavior from live provider configuration.

## Implemented and tested

- Open registration mode removes the email allowlist, with verified identity and current organization membership still required. Restricted mode remains the default.
- Continue with Google uses the official Supabase Python SDK, PKCE S256 and a single-use, ten-minute, browser-bound challenge. The callback exchanges the code on the API. Google API tokens are discarded; application sessions remain encrypted in PostgreSQL behind an HttpOnly cookie.
- Google requests only `openid email profile`. It does not connect Gmail, Drive, Calendar or an ERP.
- Cloudflare Turnstile tokens pass to Supabase Auth on email signup, login, recovery, resend and password reauthentication. Public email signup refuses to start without configured CAPTCHA and custom SMTP flags. These flags describe operator verification, not automatic proof of email delivery.
- An operator-owned Supabase hook supports closed, restricted and open registration. Google-only opening is possible while SMTP is unavailable. The hook and API each retain bounded account capacity; open access does not promise unlimited free hosting.
- Privacy information is available at `/privacy/`. Provider secrets never belong in frontend build variables.

Executed locally: **86 backend tests**, **six Playwright scenarios**, frontend lint, TypeScript and production build. The Google browser scenario mocks the external identity exchange; it does not establish live Google consent or SMTP delivery. Playwright also completed the original upload, validation, import, recommendation, approval, MIS export and analyst journey.

PostgreSQL migration and backup/restore checks passed:

- [Retail schema preservation](public-auth-migration-verification.json)
- [Existing account/session preservation](oauth-account-preservation.json): all 27 existing tables retained matching fingerprints; only `oauth_challenges` was added, with no Alembic drift.
- [Registration hook checks](registration-policy-verification.json): the actual policy SQL passed restricted/open/Google-only/closed, capacity and anonymous-denial checks under the Auth service role in disposable PostgreSQL. Run with `python scripts/check-registration-policy.py` against the local Compose DB; fixtures and roles roll back.
- [Managed Neon checkpoint](neon-public-auth-checkpoint.json) was queried before the production OAuth migration. No production restore was performed.

## Live configuration status

The existing owner-only pilot remains active. General signup and Google sign-in are not claimed as live.

The new API source `b4c56bb` deployed successfully on Render as
`dep-dbcdciifngtc739rh7b0`; startup logs confirmed the `c8d3` to `d9e4` migration,
and real HTTPS health returned 200. [Release CI](https://github.com/saifmodan2006/retailpilot-ai/actions/runs/39623445007)
passed all 86 backend and six browser scenarios, lint, builds, proxy checks and dependency audits.
The new registration hook was installed in restricted mode and its live grants
were checked: Auth service SELECT/EXECUTE allowed, anonymous access denied,
non-admitted identity rejected with 403, and the existing single identity retained.
The managed SQL role does not permit `SET ROLE supabase_auth_admin`; no permissions
were expanded to bypass that restriction. Service-role execution was tested locally.

At the release check, Cloudflare Pages still served frontend source `ce39869`.
Its dashboard reported degraded GitHub push delivery, confirmed by the
[21 October GitHub incident](https://www.githubstatus.com/). No new frontend
deployment or live CAPTCHA activation is claimed while the source is delayed.
Two real public browser scenarios then passed against the new API in 3.5 minutes,
including the entire Excel-to-MIS/analyst flow and mobile navigation. See
[the measured deployment state](public-oauth-release-verification.json) and
[CI metadata](public-auth-ci.json). These public checks used the existing frontend
and do not establish live Google login, SMTP delivery or the new privacy route.

- A dedicated, free Turnstile widget was created for `retailpilot-ai.pages.dev`, with pre-clearance disabled. Its secret is not in this repository. Activation must follow deployment of the CAPTCHA-capable code.
- Gmail SMTP fields were prepared in the dedicated Supabase Auth project, but not saved without the app password. The account owner must complete Google identity verification and app-password creation. No credential should be pasted into chat or committed.
- Google Cloud refused a new project because of account quota. The user requested a new RetailPilot project rather than reuse of Flask-Project. No existing OAuth client was modified. A free-project quota request and the exact Flask shutdown dialog were prepared, awaiting their required confirmations. Project deletion still counts against quota for 30 days, so it does not immediately resolve this blocker.
- SMTP delivery, real Google consent/callback, verified owner onboarding and public-account retail journeys remain pending. Existing demo evidence is separate from these unverified account flows.

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
