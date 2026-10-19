# Business logic and assumptions

## Reporting context

The fixed fictional business date is 18 October 2026. Default dashboard range is 19 September–18 October inclusive. Filters cover date, store, category, brand and SKU. Store–SKU positions, not organization-wide distinct SKU codes, are the unit of stock alerts. All timestamps are persisted in UTC; the browser formats Indian dates in the browser timezone, and scheduled idempotency keys use Asia/Kolkata.

| Metric | Calculation |
|---|---|
| Net revenue | Sum of signed transaction quantity × unit price × (1 − discount), rounded to paise per line |
| Net units sold | Sum of signed quantities; returns are negative |
| Cost of goods sold | Signed transaction quantity × SKU cost at ingestion |
| Gross profit | Net revenue − signed COGS; no rent, salaries, tax or other absent expenses |
| Gross margin | Gross profit ÷ net revenue × 100; zero when revenue is zero |
| On hand | Sum of latest supplied snapshot quantities, independently per store/SKU on/before end date |
| Inventory at cost | Sum of snapshot quantity × current SKU purchase cost |
| Available stock | max(on hand − reserved, 0) |
| Daily demand | Positive unit sales over trailing 30 **calendar** days ÷ 30, including zero-sale days |
| Stock cover | Available ÷ daily demand; null / “No demand” when denominator is zero |
| Aggregate cover | Total available units ÷ sum of position daily demand |
| Sell-through proxy | max(net selected-period units, 0) ÷ (max(net units, 0) + ending on hand) × 100 |
| Low stock | Cover below configurable threshold (default 14 days) with observed positive demand |
| Coverage stockout estimate | Position cover < 14 days; a constant-demand planning estimate, not an ML guarantee |
| Dead stock | On hand > 0 and last positive sale at least configured inactivity days ago (default 90); if never sold, use receipt age |
| Dead-stock value | Dead-stock on hand × purchase cost |
| Slow moving | Cover > 60 and ≤ 90 days, unless dead stock |
| Overstock | Cover > 90 days, including no observed demand unless already dead stock |
| Ageing | Positive stock with latest receipt date at least 90 days old |
| High demand | Positive trailing demand at/above the selected positions' 90th percentile |

Sell-through is explicitly a period/end-stock proxy because an opening balance plus complete receipts ledger is not available. Receipt date approximates ageing; it is not FIFO lot ageing. Inventory “excess capital” is shown as cost value of dead/overstock positions; no valuation markdown is guessed.

## Purchasing

```
d = positive units in trailing 30 calendar days / 30
safety = ceil(d × configured safety days)
reorder point = ceil(d × supplier lead days + safety)
inventory position = max(on hand − reserved, 0) + confirmed inbound
shortfall = max(reorder point − inventory position, 0)
reorder = ceil(max(shortfall, MOQ) / pack size) × pack size, if shortfall > 0; otherwise 0
estimated cost = reorder × SKU purchase cost
```

Safety days are a transparent management assumption, not a statistical service-level percentage. Supplier lead days, MOQ and pack sizes are configurable through the manager API. Reservations reduce availability; only Confirmed purchase orders count inbound. A simulated draft has no effect on inventory or inbound. Existing Suggested, Awaiting Approval and Approved recommendations prevent duplicate outstanding proposals for the same position.

Submission revalidates against current business rules. Approval records requester, reviewer, reason, decision and UTC timestamp, and creates an explicitly simulated draft. Terminal decisions cannot be replayed to create another order. No real purchasing authority is granted to the analyst or the optional LLM. Unsubmitted suggestions are recalculated after planning changes; pending decisions retain their evidence for review.

## Import rules

Required values are rejected, not guessed. Optional discount/reserved defaults to zero; blank received_date defaults to snapshot date. INR symbols and grouping commas normalize before finite Decimal validation. Integer signed sales quantities allow returns; inventory and reservation values must be nonnegative and reserved ≤ on hand. Price is nonnegative, discount is 0–1, future dates are rejected, and every store/SKU must belong to this tenant. Transaction IDs are line IDs, scoped to organization. Duplicate rows reject their later occurrence. Repeated bytes are detected by SHA-256; changed bytes still encounter transaction uniqueness.

## Forecast evaluation

Daily demand is formed on a complete grid from the requested/history start through the end date. Sales after the cutoff are excluded before model fitting. At least 42 days are required. Four models: last daily observation; repeated last seven days; trailing 28-day mean; EWMA with span 14. Three rolling seven-day holdouts use origins N−21, N−14 and N−7. Every prediction receives only observations preceding its origin. MAE averages absolute unit error; WAPE = total absolute error ÷ total actual units × 100, or null if all holdout actuals are zero. The minimum-MAE baseline is fitted on the complete available series and shown alongside naive predictions for 7 or 30 days. Version `baselines-v1` and selected filters persist.

No synthetic “confidence” band is fabricated. Validation MAE is shown as empirical error, explicitly not a probability interval. Sparse series retain zero days; users can choose store/category aggregation. Automatic hierarchical fallback, intermittent-demand specialty models and trained ML remain future work.

## Reports and deterministic answers

Report types select appropriate daily/store/category or inventory tables while preserving the exact filter range. Labels do not silently change the selected dates: choose a day/week/month in the filters for a daily/weekly/monthly report. Automatic daily/weekly workflows use one and seven days respectively; weekly additionally saves the preceding seven-day comparison. Reports persist calculated metrics and rows, making exports stable across later imports. XLSX uses numeric cells, totals, filters, frozen headers and formula-injection escaping; PDF prints key columns for readability.

The analyst resolves only six allowlisted questions. “Last month” means the calendar month before the filter end date. Revenue change is a comparison; it does not invent causal explanations from absent traffic/promotion data. Stock queries return bounded supporting rows. Missing datasets return empty tables or an explicit insufficient-history error. Unsupported questions return a helpful 422 response rather than a fabricated answer.
