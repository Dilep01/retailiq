param([string]$Python = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
New-Item -ItemType Directory -Path '.runtime\tmp' -Force | Out-Null
$env:TEMP = Join-Path $projectRoot '.runtime\tmp'
$env:TMP = $env:TEMP
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if (-not $Python) {
        $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
        if (Test-Path -LiteralPath $bundledPython) { $Python = $bundledPython }
        else { $Python = (Get-Command python -ErrorAction Stop).Source }
    }
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed. Supply -Python with a Python 3.12 executable.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' }
& '.\.venv\Scripts\python.exe' manage.py prepare_demo
if ($LASTEXITCODE -ne 0) { throw 'Demo preparation failed.' }
& '.\.venv\Scripts\python.exe' manage.py collectstatic --noinput
Write-Host 'RetailIQ is ready. Run scripts\start.ps1. Private login: .runtime\review_credentials.txt'
