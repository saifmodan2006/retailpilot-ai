# Fictional demonstration data

No real Saffron, employee, customer, sales, or inventory records are used.

`demo_dataset.zip` contains the complete seeded dataset as CSV: stores, SKU catalog, suppliers, sales and inventory. `manifest.json` records exact generated counts. The application seeds this data directly through `app.seed.seed` into each isolated demo tenant. Fixed random seed: **271828**. Business dates: **19 October 2025–18 October 2026**. 12 stores, 5 brands, 6 categories, 180 products, 360 size/color variants, 4 suppliers, 4,320 inventory positions.

`sales_import.xlsx` is the flagship incremental upload: 15 valid records in Sales and 4 intentionally rejected records on Validation examples (invalid SKU, missing date, duplicate transaction, invalid numeric quantity). Accepted revenue increase: **INR 55,532.25**. All records are dated 18 October 2026. Reuploading this exact file is a no-op; changing the bytes still cannot duplicate an existing transaction ID.

`inventory_import.xlsx` contains ten valid replacements for same-date inventory snapshots at ST01. These replace quantities rather than adding stock. `sales_template.csv` contains two sample rows using canonical headers.

## Import contract

Load the demo catalog before importing; master-data onboarding is outside this demonstration. Use store codes ST01–ST12 and SKU codes from the catalog. Transaction IDs are organization-unique **line IDs**, not invoices containing multiple lines.

Sales: `transaction_id,date,store,sku,quantity,unit_price,discount`.
Inventory: `date,store,sku,quantity,reserved,received_date`.

Dates accept ISO YYYY-MM-DD or unambiguous Indian DD/MM/YYYY. Quantity must be a finite integer. Negative sales quantities represent returns. Negative inventory is rejected. Unit price is nonnegative and discount is a fraction from 0 through 1. Blank discount/reserved becomes zero; blank received_date becomes snapshot date. Required values are never imputed. Unknown store/SKU and duplicate transaction IDs are rejected. Reserved quantity cannot exceed on-hand quantity. Workbook formulas are not executed. Source sheet names and physical row numbers are retained.

The archived sales CSV stores the already-discounted unit price with discount zero to reproduce the same net revenue; original random discount fractions are represented by the transaction net revenue in the database. The large archive is for inspection and reproducibility; uploads are limited to 20,000 rows per batch, so split large files if importing them separately.

Regenerate from the repository root:

```powershell
.\.venv\Scripts\python scripts/generate_samples.py
.\.venv\Scripts\python scripts/export_demo_dataset.py
```
