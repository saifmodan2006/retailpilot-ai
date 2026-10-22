# Private workspace files

Updated 22 October 2026. **Hosted imports are enabled after owner approval**; the live
capability endpoint and private catalog/store UI were verified. The complete hosted
file journey is still pending Chrome file-access permission. See live provider evidence
for the precise status and separate browser evidence for the isolated local test.

## Use your own authorized records

1. Create an account with verified email or Google. Create an **empty** private workspace;
   choose “Set up my stores and catalog” during onboarding when private imports are enabled.
2. In Organization settings, add store codes/names. A workspace supports up to 20 stores.
3. Add SKU records individually or download the catalog template, replace its example
   values, upload CSV/XLSX and save only after every row validates. New SKUs include product,
   brand, category, supplier, purchase cost, selling price, optional size/color and supplier
   planning rules. Existing supplier names require matching rules. Existing SKU records
   are preserved; duplicate codes fail atomically. Catalog-file imports support 500 rows,
   1 MB, and 1,000 SKUs per workspace.
4. Download the sales/inventory templates in Data import center. Replace all example
   records and dates. Match your saved store and SKU codes. You can map custom column
   headings, review errors, and import accepted rows. Missing master records are never guessed.
5. Review the overview and inventory; private default dates follow the latest imported
   business date. Select another range when needed. Recommendations and import-triggered
   reports use the workspace dates. Currency is the configured workspace currency;
   relabeling it after business data exists is rejected, and no conversion is implemented.
6. Request/approve simulated purchase drafts, export MIS and ask one of the six supported
   analyst questions. Forecasting needs at least 42 daily observations for rolling validation;
   a small new dataset can legitimately be insufficient.

The shared demo stays sample-only even when private imports are enabled. A workspace
loaded with fictional samples also stays sample-only: create an empty organization for
your real records. There is no paid ERP or outbound LLM integration in this deployment.

## Security and capacity

- Only authenticated owner/admin memberships can create catalog records. Business requests
  check current organization membership and role; viewer writes and unauthorized analyst
  imports remain blocked. Client-supplied organization IDs cannot choose a different tenant.
- Private sales/stock files: **1 MB, 2,000 rows, 50 columns**, values up to 120 characters.
  XLSX expansion is capped at 10 MB. Formula cells, macros, encrypted files and unsupported
  formats are rejected. Existing safe export escaping remains in place.
- At most 12 import batches per workspace, 100,000 sales rows and 10,000 inventory rows.
  Catalogs and shared rows have separate deployment-wide limits. The shared admission
  checks serialize PostgreSQL capacity decisions and stop writes at 400,000 sales rows,
  40,000 inventory rows, 40 MB preview/export JSON, or 450 MB database size. They do not
  enable billing or overages. Free capacity is finite, with no availability SLA.
- Hosted PDFs show up to 500 rows, with an explicit notice and full-selection KPI totals.
  XLSX contains all report rows. The single API worker serializes expensive operations;
  no paid worker service is required. Private parsing checks row/expansion limits before
  materializing XLSX in Pandas.

## Privacy and retention

Upload only business records you are authorized to process. Omit customer names,
contact details, payment information, employee records and credentials, including
unrelated columns. Previews can include all uploaded columns. Private workspaces
are shared with their authorized members; hosting providers and the operator have
administrative access for service operations. This is not end-to-end encryption.

Cloudflare forwards account requests, Render parses files in memory and Neon persists
rows. No imported business data is sent to an AI provider. The temporary Render filesystem
is not used as a database or durable file store. Raw previews expire after seven days,
export row payloads after thirty days, with cleanup on workspace access. Business facts
and catalog records have no automatic expiry or self-service physical erasure. An account
deletion request revokes access and requires operator review; recovery branches/backups
can retain copies. Keep original files. Use this portfolio app only for non-sensitive,
non-critical data. Read the live `/privacy/` page before uploading.

## Evidence

- [Isolated browser journey](private-data-browser-verification.json): store/catalog setup,
  sales and inventory imports, date defaults, refresh persistence, XLSX export and analyst
  value; identity was mocked only in the loopback harness. Three catalog viewport audits
  reported no WCAG A/AA violations or horizontal overflow.
- Three new backend scenarios cover private/demo separation, master-data atomicity,
  role restrictions, formula/row limits, shared capacity, and correct currency/date labels.
- A hosted private-file journey must still be executed after Chrome permits file selection. Only fictional
  QA records may be used for release verification; no real Saffron records are test fixtures.

`REAL_UPLOADS_ENABLED` defaults false and now applies only to authenticated own-data
workspaces. It requires configured managed accounts. Rollback this flag to stop new
private uploads without deleting stored records or disabling existing verified accounts.
