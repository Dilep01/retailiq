$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$env:TEMP=Join-Path (Get-Location) '.runtime\tmp'
$env:TMP=$env:TEMP
& '.\.venv\Scripts\python.exe' -m ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Lint failed' }
& '.\.venv\Scripts\python.exe' manage.py check
if ($LASTEXITCODE -ne 0) { throw 'System check failed' }
& '.\.venv\Scripts\python.exe' manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { throw 'Migrations missing' }
& '.\.venv\Scripts\python.exe' -m pytest --cov=retailiq
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
