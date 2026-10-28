# Architecture and implementation decisions

RetailIQ is a Django modular monolith. The browser renders server templates with custom CSS and dependency-free SVG charts. Forms use Django validation; business pages require session authentication. The local release uses Waitress and WhiteNoise.

## Boundaries

- `models.py`: Dataset, Product, Location, Sale, Stock, ImportBatch, ForecastRun, ForecastPoint, Plan, Simulation, Job and AuditEvent.
- `services/data.py`: validation, canonical imports, normalized frames and deterministic demo generation.
- `services/uci.py`: streaming XLSX adapter, training-period SKU selection and source attribution.
- `services/forecasting.py`: origin-only features, bounded pooled ML, baselines, chronological evaluation, approximate intervals, manifests and artifacts.
- `services/inventory.py`: order-up-to calculations, pack/MOQ rounding, stock signatures, heuristic and integer budget allocation.
- `services/simulation.py`: receipt/demand/review events, lost-sales conservation, matched demand paths and cost/service accounting.
- `services/jobs.py`: transactional job claim, execution and failure recording.

## Decisions relative to the original blueprint

1. One Django app with focused service modules keeps the beginner codebase navigable. Separate apps can be introduced when boundaries justify the migrations and import complexity.
2. Custom CSS replaces Bootstrap. Native SVG charts replace Chart.js. The UI is specific to RetailIQ, works without CDN assets, and requires no Node runtime.
3. A small local database-backed worker replaces Redis/Celery. The worker uses an OS lock to prevent two local workers, claims jobs transactionally, and marks interrupted running jobs failed on restart. Submit a new job to retry.
4. SQLite transactions begin IMMEDIATE to avoid read-to-write upgrade races. Parsing and training occur outside write transactions; published result batches are atomic. Only one planner/worker is supported.
5. Model selection uses earlier validation MAE. Interval bounds are normalized residual quantiles estimated on validation, rather than three additional quantile models. Daily empirical coverage and pinball losses are reported. No cumulative-quantile service guarantee is implied.
6. Inventory safety stock remains an explicitly labeled normal approximation. The optional MILP has a linear priority objective, integer packs, binary order activation, budget limits and MOQ constraints. It is not a stochastic multi-period inventory optimizer.
7. The operational inventory input is a dated aggregate snapshot. The simulator has its own dated in-transit events. A production PO/movement ledger is deferred, and outstanding stock timing is an explicit operational limitation.

## Data lineage

Sales dataset versions are immutable. Forecasts reference dataset checksums, origin, feature version, package/runtime versions, source-code digest, seed and artifact checksum. Published points are immutable. Plans reference a forecast and the stock-input signature; changed inputs trigger a stale warning. Scenario reports preserve dates, seeds, demand source, costs and budget assumptions.

The dashboard aggregates daily observations; it does not impute unknown observations. Historical revenue is calculated from stored price and quantity. Features exclude future prices and promotions. Public transaction customer identifiers are discarded.

## Operations

Only loopback hosts are intended. No external outbound calls occur in ordinary app views. Explicit package installation and the UCI download command are the network-dependent setup steps. The worker and server write separate logs. SQLite backup captures all operational snapshots and forecasts; model files are copied alongside. Raw downloaded input is reproducible through its URL and checksum.
