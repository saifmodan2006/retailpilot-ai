# A 3–4 minute walkthrough

Prepare: run the services, open the landing page, download the incremental sample and create a demo session. Allow initial data generation to finish before presenting. Show the “synthetic data” label clearly. Never describe these as records from a real business.

**0:00–0:30 · The retail problem**

“Retail teams already have spreadsheets. The hard part is turning disconnected files into consistent numbers and accountable action. RetailPilot connects Excel processing, Python analytics, MIS automation and explainable planning.” Load the reproducible 12-store demo. Explain revenue is calculated from stored transactions and inventory value is cost-based.

**0:30–1:15 · Excel to trusted data**

Open Data Import Center and upload `sales_import.xlsx`. Show the two sheet names, detected mappings, 15 accepted and four rejected rows. Open validation feedback: unknown SKU, missing date, duplicate record, invalid quantity. Download the error report. Import the accepted rows. Explain the revenue increase of INR 55,532.25; a repeated upload cannot add it twice. The import also triggers a saved daily report workflow.

**1:15–2:10 · Explainable inventory decision**

Open Inventory Intelligence and Review a suggested reorder. Read the actual demand, lead days, available quantity, safety units and supplier pack rounding. “The quantity is calculated from these inputs; an LLM did not guess it.” Submit for approval. Open Approval Center, switch explicitly to Demo manager, enter a review reason and approve. Show the resulting **Simulated Draft**. Explain that it neither contacts a supplier nor changes stock.

**2:10–2:45 · Management reporting**

Open MIS Report Builder, select Daily sales MIS and the desired date range, generate, then download XLSX. Show frozen header, numeric totals, filters and Summary worksheet. Download PDF if time allows. “The report and dashboard share the metric service. Saved report data remains reproducible after later imports.”

**2:45–3:20 · Practical analytics and forecasting**

Ask “What is our current inventory value?” Show the deterministic/no-LLM label, cost calculation, reporting dates and supporting table. Open Demand Forecasting: compare selected baseline and naive, then show MAE/WAPE backtests. “We evaluate on earlier holdouts and do not claim ML superiority or a false confidence interval.”

**3:20–3:50 · Evidence and business value**

Show workflow history and audit entries for import, approval and report. Optionally show the independent local ERP connection. “This reduces repetitive spreadsheet work, makes stock decisions explainable and keeps managers in control. The project demonstrates Excel/MIS, Python, reporting automation, authenticated API integration and practical AI tool routing.” Mention production identity, commercial ERP and public deployment as remaining work where applicable.
