# Release audit — 19 October 2026

Scope: preserve the working React/FastAPI/PostgreSQL application, redesign all existing routes, verify release controls, publish to the authenticated owner's existing repository, and deploy only to an authorized compatible host.

## Initial inspection

The local repository has no commits and no remote configured initially. The supplied public GitHub repository exists and contains a single introductory README. GitHub CLI identity matches `saifmodan2006`; the separate connector identity does not, so publication will use the matching CLI session. The running Docker stack is healthy. Existing screenshots and 37 backend / two browser test evidence exist and will be rerun rather than treated as current proof.

The interface is React 19 with strict TypeScript, Vite, Tailwind 4, Lucide, Recharts, TanStack Query, React Router and React Hook Form/Zod. Shared panels/tables/forms live in App.tsx. Main usability issues: undersized 8–11px text, weak contrast, inconsistent visual priority, no sortable table headers, generic landing preview rather than an actual product screenshot, and repeated flat page presentation. Some static status language implies connectivity without a health query.

The redesign follows the attached brief: slate navigation, light neutral surfaces, restrained teal, readable tabular typography, semantic tokens, consistent keyboard focus, operationally distinct page structures and retained API contracts. UI UX Pro Max's verified minimal enterprise style guidance is applicable; its initial automatic dark-OLED recommendation did not fit the requested light enterprise workspace and was discarded.

## Verified release gaps to repair

- Demo role switching is gated only by a global flag; organizations lack an explicit demo marker, so public-demo isolation needs an additional server-side boundary.
- Anonymous sessions can accumulate full seeded datasets without an active-tenant cap, expiration cleanup or per-tenant write quotas.
- Rate-limit buckets are process-local, unbounded and shared by nginx's proxy address. Public configuration needs explicit single-worker constraints, bounded buckets and trusted proxy handling.
- Upload byte bounds are checked after multipart parsing; the ASGI ingress needs a streamed request-body cap. Workbook row bounds are checked after parsing; parsing needs an earlier row cap and macro/formula/header checks.
- Independently valid price/quantity values can overflow NUMERIC(14,2) when multiplied; monetary products and integer quantities need domain bounds. ISO dates currently silently truncate arbitrary suffixes.
- Cancelling a purchase-approval workflow can diverge from its linked approval state; cancellation must use the governed approval path.
- Forecast GET calls persist a new version on every refresh; persistence should occur only when the request's version/filters/result actually change.
- Public release should disable optional outbound LLMs, real ERP targets and arbitrary uploads; supplied fictional samples still support the complete upload journey.
- The repository needs a deterministic tracked-file secret scanner, release checklist, pinned CI action revisions, deployment manifest and explicit public-versus-local evidence.

## Validation plan

Capture every page before editing. Add regression tests for each repaired security boundary, rerun numerical and workflow tests, lint, TypeScript/build, and browser journeys. Capture 13 routes at 1440×900, 1280×800, 768×1024 and 390×844; record overflow/error evidence. Verify public routes separately only if a compatible deployment actually succeeds. Never treat a static frontend or local tunnel as a durable deployed Python/PostgreSQL application.

## Resolution evidence

The listed security gaps now have implemented controls and regression coverage (53 backend tests passed). The 52-capture visual matrix passed after responsive fixes. Public compute is single-process and serialized; SQL filtering/typed tuples reduced memory allocation. A complete browser journey passed with a 512 MB hard limit at ~232 MiB peak. Secrets and sample archives were scanned before publication. The user's final architecture is Cloudflare Pages Free + Render Free native Python + isolated Neon Free PostgreSQL; no paid Containers, billing methods or overages are authorized. Public URLs require separate live verification.
