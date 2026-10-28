param([ValidateRange(1024,65535)][int]$Port=8877)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:RETAILIQ_DEBUG = '0'
$env:PYTHONUNBUFFERED = '1'
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run scripts\setup.ps1 first.' }
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { throw "Port $Port is already occupied. Choose a different -Port." }
& '.\.venv\Scripts\python.exe' manage.py collectstatic --noinput
if ($LASTEXITCODE -ne 0) { throw 'Static-file collection failed.' }
$server = Start-Process -FilePath (Join-Path $projectRoot '.venv\Scripts\waitress-serve.exe') -ArgumentList "--listen=127.0.0.1:$Port",'config.wsgi:application' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot '.runtime\server.log') -RedirectStandardError (Join-Path $projectRoot '.runtime\server-error.log') -PassThru
$worker = Start-Process -FilePath (Join-Path $projectRoot '.venv\Scripts\python.exe') -ArgumentList 'manage.py','run_worker' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot '.runtime\worker.log') -RedirectStandardError (Join-Path $projectRoot '.runtime\worker-error.log') -PassThru
@{ server=$server.Id;worker=$worker.Id } | ConvertTo-Json | Set-Content -LiteralPath '.runtime\processes.json'
$credentialPath = Join-Path $projectRoot '.runtime\review_credentials.txt'
if (Test-Path -LiteralPath $credentialPath) {
    $credentialText = Get-Content -LiteralPath $credentialPath -Raw
    ($credentialText -replace 'URL: http://127.0.0.1:\d+',"URL: http://127.0.0.1:$Port") | Set-Content -LiteralPath $credentialPath
}
$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/health/" -TimeoutSec 1
        if ($health.application -eq 'RetailIQ') { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 250 }
}
if (-not $ready) { throw 'RetailIQ did not become ready. Inspect .runtime\server-error.log.' }
Write-Host "RetailIQ: http://127.0.0.1:$Port"
Write-Host 'Private login: .runtime\review_credentials.txt'
