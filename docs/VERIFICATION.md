# Verification record

Local verification on Windows / Python 3.12.14. This document records executed checks; a prepared CI configuration is not a remote CI pass.

Publication verification: [GitHub Actions run 40716538724](https://github.com/Dilep01/retailiq/actions/runs/40716538724) passed on Ubuntu for commit `475bfe72bc0fcf1b1bf5e3ab12acbedc4c072c92`, including dependency installation, lint, Django/migration checks, static collection and the test suite.

- Automated checks: the final suite includes 63 tests. Results, overall line coverage and command timings are recorded in `docs/evidence/verification.json`; individual cases are recorded in `docs/evidence/test-results.xml`.
- Django system checks and migration creation passed. A final check verifies that no model changes lack migrations.
- Ruff lint passed; Python files are formatted with Ruff.
- Synthetic end-to-end preparation: 20 SKUs, one location, 730 days, 14,600 daily rows; ML/baseline evaluation, integer allocation and 56-day/three-seed simulation completed.
- UCI download/import completed from the official source. A 20-product cohort was selected from the first 180 days; the subsequent public-data forecasting run completed.
- Browser: signed into the real local application; overview, forecasts, inventory, scenarios and catalog rendered. Submitted a real forecast job and verified successful completion. Calculated a 1,000-budget integer proposal; observed spend 805, within the cap. Restored the 25,000 plan. Submitted a 750,000-per-review scenario and inspected distinct policy results. Searched the catalog for coffee.
- Browser layout: inspected desktop at 1440×1000 and mobile at 390×844; the document width stayed inside the viewport. Verified the mobile navigation menu and saved screenshots. Wide data tables scroll inside their cards. Chart drawing adapts to the viewport.
- Browser console: no captured error entries during the inspected flows.
- Windows startup/shutdown: tested owned-process-tree shutdown, restart on the same port, static collection and application health response. The original port 8000 was occupied by another local project; RetailIQ uses 8877.
- Backup recovery: a consistent SQLite snapshot passed integrity/foreign-key checks and reopened through Django using the backup database override. Dataset and sales counts were verified. No active workspace was overwritten.
- Debug-off deployment check returned four expected local-HTTP warnings: HSTS, HTTPS redirect, secure session cookie and secure CSRF cookie. They are documented in LOCAL_DEPLOYMENT.md; this loopback-only configuration is not a public deployment configuration.
- A concurrent long XLSX import initially caused SQLite lock upgrade contention. Parsing was moved outside the write transaction and transaction mode set to IMMEDIATE; the retried real import and subsequent workflow completed.

Not verified: real retailer effectiveness, public hosting, Linux execution on this local Windows machine, universal accessibility conformance, physical supplier integrations, arbitrary-sized datasets or simultaneous multi-user workload. Review known limitations in README.md and MODEL_CARD.md before interpreting metrics.
