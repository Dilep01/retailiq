# Review RetailIQ locally

Start with `scripts\start.ps1` and open http://127.0.0.1:8877/. The private generated login is in `.runtime/review_credentials.txt`. This is an ordinary local account; no bank credentials or API keys are involved.

1. **Overview:** leave “The everyday market” selected for the complete synthetic demo. Inspect revenue, product mix, on-hand stock and the forecast window. Each number comes from the selected dataset or saved plan.
2. **Demand forecasts:** inspect model choice, holdout errors, interval coverage and one product. Change the product selector. Export the future forecast. “Run backtest & forecast” submits a real worker job; it can take several seconds. Existing results remain usable while the next run computes.
3. **Activity & runs:** inspect queued/running/succeeded/failed jobs. A failed job shows its error. If the worker was stopped mid-run, startup marks it failed; submit a new run. A queue that never changes usually means the worker is not running.
4. **Inventory planner:** set budget, review interval, normal target parameter and allocation method. Calculate a proposal. Inspect requested versus allocated quantities and expand the calculation section. A low budget may leave risky products unfilled. An integer solution maximizes the defined priority score; it is not a claim about real profit.
5. **Inventory inputs:** edit one product's dated stock, allocated stock, costs, lead time and packs. Keep “scenario assumptions” checked for invented values. Changes require a new plan and trigger stale-plan warnings. A snapshot date must match the forecast origin.
6. **Scenario lab:** compare a funded scenario with a low-budget or delayed-delivery scenario. The budget is per weekly review, split equally among product/location series without carry-over. Compare fill rate, ending stock and costs together. Lower cost can conceal poor service if penalties are unrealistic.
7. **Product catalog:** search a name, SKU or category, open a product, and inspect its history and location stock. Package graphics are decorative illustrations, not product photography.
8. **Data workspace:** download the CSV template. Preview an invalid file to see row errors. Correct it, preview again, then confirm the import. Each successful distinct file becomes a dataset; existing snapshots remain selectable. Short datasets can be explored but need more history for the full backtest.
9. **Public-data review:** on Overview select the UCI dataset if imported. Inspect the public-data forecast. Its cost and stock inputs are intentionally absent; inventory needs explicit assumptions. Use the dataset selector to return to the synthetic demo.

Exports are UTF-8 CSV. Spreadsheet-like formulas in text fields are escaped. Forecast exports preserve origin/model; plan exports contain requested/allocated quantities and constraints. Scenario exports include purchasing spend and all policy metrics.

On narrow screens the menu button opens navigation and wide tables scroll inside their cards. Charts have tooltips and CSV equivalents; product illustrations and colors are not the only identifiers. The implementation is not claimed to meet a formally audited accessibility standard.

No actual purchase is submitted by any action in the app.
