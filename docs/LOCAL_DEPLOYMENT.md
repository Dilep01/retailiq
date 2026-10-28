# Local deployment and recovery

## Initial setup

Requirements: Python 3.12, PowerShell on Windows, an existing computer, and internet for initial package installation. No GPU, paid API, Node runtime or database server is required.

`scripts\setup.ps1` creates an isolated environment, installs `requirements.lock`, migrates SQLite, prepares the synthetic demo and login, and collects static files. The script accepts `-Python` with an explicit Python executable. It can use the bundled Codex Python runtime on this computer. If PowerShell script execution is restricted by the user's policy, run the documented Python commands individually; changing machine policy is not required.

For development dependencies install `requirements-dev.lock`. Both locks contain exact tested versions; runtime requirements omit test/lint packages.

## Start and stop

`scripts\start.ps1` launches Waitress and a background worker with hidden windows, debug off, local static serving, and port 8877. `-Port` selects another unused port and updates the login note's URL. It records owned process IDs and verifies the health endpoint. `scripts\stop.ps1` verifies executable ownership and stops the owned process trees. Do not terminate unrelated Python applications.

Settings read process environment variables. `.env.example` is documentation, not an automatically loaded file. Optional overrides are `RETAILIQ_SECRET_KEY`, `RETAILIQ_DB`, and `RETAILIQ_DEBUG`. The default local key is generated into `.runtime/secret.key`; do not commit it. Login credentials live in `.runtime/review_credentials.txt`; do not share them. Use `manage.py createsuperuser` for a separate admin account.

The worker holds an OS lock. A second local worker exits. On recovery it marks interrupted jobs failed rather than silently publishing partial work. Use a new run to retry. Keep just one write worker; SQLite is intentional for this local workload.

## Backup

```powershell
.\.venv\Scripts\python.exe manage.py backup_workspace
```

The command uses SQLite's consistent backup API and copies referenced local model files. The database itself contains normalized sales snapshots, published forecasts, plans, simulations and accounts. Raw UCI files can be downloaded again using the stored source checksum. Secrets are excluded. Backups are still private because the database contains account password hashes and may later contain business data. Keep a small number of dated backups and remove older copies only after confirming the desired retention.

To inspect a backup safely, set `RETAILIQ_DB` to its database path in a separate terminal and run `manage.py check`. Use `manage.py shell` or a separate local server port to inspect counts. Do not overwrite the active workspace just to test recovery. A real restoration should be performed with the app/worker stopped, copying the selected database and matching models to a separately verified destination. Secrets can be regenerated for a new installation; account logins remain in the database.

## Deployment check

Run `manage.py check --deploy` with `RETAILIQ_DEBUG=0`. Local HTTP deliberately leaves HTTPS redirects, secure-only cookies and HSTS disabled; otherwise a localhost HTTP login would fail. The documented warnings are not authorization to expose this configuration publicly. An internet-facing deployment would need HTTPS, proper host settings, login throttling, operational backups, concurrency testing and a production security review.

## Troubleshooting

- Wrong app at port 8000: RetailIQ uses 8877 to avoid other local projects.
- Port occupied: stop the existing RetailIQ instance with its script, or choose a different `-Port`.
- Queue stays queued: inspect `.runtime/worker-error.log`; run `manage.py run_worker` if needed.
- Missing costs/stock: edit explicit scenario inputs; UCI does not supply them.
- Stale plan: recalculate after stock edits or a new forecast.
- Forecast skips series: inspect missing recent days. Do not fill unknown dates with zeros merely to bypass validation.
- Public-data errors remain high: report this honestly; do not convert WAPE into a general accuracy claim.
