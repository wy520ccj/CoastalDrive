# Launch CoastalDrive with the new pixel UI, from the visual-upgrade copy.
#
# Usage:  .\run_new_ui.ps1      (or double-click the .bat launcher)
#
# This file is intentionally ASCII-only: Windows PowerShell 5.1 reads .ps1
# files as ANSI when there is no BOM, and non-ASCII comments then corrupt the
# script. Chinese paths are handled fine at runtime; only the source must stay
# ASCII.
#
# User data goes to logs\_localappdata inside the copy, so the real
# %LOCALAPPDATA% and the original repository are never touched.

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$copyRoot = $PSScriptRoot
$python = Join-Path (Split-Path $copyRoot -Parent) ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Project venv not found: $python" -ForegroundColor Red
    exit 1
}

$env:LOCALAPPDATA = Join-Path $copyRoot "logs\_localappdata"
New-Item -ItemType Directory -Force -Path $env:LOCALAPPDATA | Out-Null

Set-Location $copyRoot
Write-Host "Starting CoastalDrive (new pixel UI) ..." -ForegroundColor Cyan
& $python src/main.py --new-ui @args
$code = $LASTEXITCODE

if ($code -ne 0) {
    $crash = Join-Path $env:LOCALAPPDATA "CoastalDrive\crash.log"
    Write-Host "Launch failed (exit code $code)." -ForegroundColor Red
    if (Test-Path $crash) {
        Write-Host "Crash log: $crash" -ForegroundColor Yellow
        Get-Content $crash -Tail 20
    }
}
exit $code
