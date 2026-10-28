# GitHub, portfolio and interview presentation

## Repository presentation

Suggested repository name: `retailiq`. Use the README screenshot as the cover. Include source, migrations, exact dependency locks, tests, tiny synthetic samples, architecture, cards and measured evidence. Exclude runtime accounts, keys, raw data, local databases, model binaries and caches. The GitHub Actions workflow is prepared; it has not run remotely until the repository is published.

This delivery prepares local files for review. It does not publish a new repository or modify the existing portfolio.

## Portfolio description

RetailIQ is a local Python/Django application for retail sales forecasting and inventory planning. It combines validated CSV imports, chronological baseline/ML comparisons, explained replenishment proposals, constrained budget allocation and matched inventory simulations. Its custom interface works without a frontend build service or remote assets.

Public-data evaluation uses a training-selected 20-product UCI Online Retail cohort. Results remain limited by irregular wholesale demand and unavailable stock/supplier data. Inventory comparisons are simulations with explicit assumptions.

## Resume bullets

- Built a Python/Django retail planning application with validated sales imports, SKU-level forecasts, editable inventory inputs and CSV reporting.
- Implemented chronological backtests for seasonal-naive and pooled gradient-boosting models, with future-data leakage checks and empirical daily interval evaluation.
- Added pack/MOQ-aware replenishment, integer budget allocation and reproducible inventory simulations with documented service/cost assumptions.

Use measured numerical claims only with the exact cohort, time period, baseline and source type from EVALUATION.md. Do not claim live business savings, production customers or universal forecast accuracy.

## Three-to-five-minute demonstration script

1. Open Overview and identify the synthetic source, date and currency.
2. Open a product's forecast; point out the origin, 28-day outlook, baseline comparison and interval coverage.
3. Open Inventory planner. Reduce the budget, calculate, and explain one product's target, position, pack rounding and final allocation. Export the proposal.
4. Open Scenario lab and compare policies under funded and severely constrained budgets. Explain ending inventory and assumed penalties.
5. Switch to the public dataset and show the larger forecast errors and missing operational inventory inputs.
6. Finish with the tests, lineage manifest and stated limitations.

Screenshots in `docs/screenshots/` are actual rendered app views. `docs/demos/retailiq-walkthrough.mp4` is a 25-second visual walkthrough assembled from these captures and labeled as such. The above script supports recording a longer continuous live demonstration after review.

## Interview questions to prepare

- Why use Django instead of separate frontend/backend deployments?
- How do sales differ from unconstrained demand?
- What information is available at each forecast origin?
- How are direct-horizon training labels kept before the cutoff?
- Why can random train/test splits overstate performance?
- Why does the ML model sometimes lose to seasonal naive?
- How do daily interval quantiles differ from cumulative-demand uncertainty?
- What are inventory position, lead time, review interval and minimum order quantity?
- Why can a low budget make every model's inventory outcome equally poor?
- What does the integer solver optimize, and what does its gap mean?
- How does the simulator prevent future-demand leakage and double-counted receipts?
- What additional stock, supplier, cost and operational evidence is needed for a live trial?
