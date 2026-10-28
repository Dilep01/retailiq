$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot '.runtime\processes.json'
if (Test-Path -LiteralPath $pidFile) {
    $processInfo = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
    $processSnapshot = Get-CimInstance Win32_Process
    function Stop-OwnedProcessTree([int]$OwnedId) {
        foreach ($child in @($processSnapshot | Where-Object { $_.ParentProcessId -eq $OwnedId })) {
            Stop-OwnedProcessTree -OwnedId $child.ProcessId
        }
        Stop-Process -Id $OwnedId -ErrorAction SilentlyContinue
        Wait-Process -Id $OwnedId -Timeout 5 -ErrorAction SilentlyContinue
    }
    foreach ($processIdValue in @($processInfo.server,$processInfo.worker)) {
        $process = $processSnapshot | Where-Object { $_.ProcessId -eq $processIdValue }
        # Guard against a stale PID that has been reused by another program.
        if ($process -and $process.ExecutablePath -and $process.ExecutablePath.StartsWith((Join-Path $projectRoot '.venv'),[System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-OwnedProcessTree -OwnedId $processIdValue
        }
    }
    Remove-Item -LiteralPath $pidFile
}
Write-Host 'RetailIQ processes stopped.'
