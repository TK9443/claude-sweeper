# Builds Claude Sweeper and installs it: Start Menu, desktop and, where the pin helper exists,
# the taskbar. It never adds a logon item.
#
#   install.ps1              build, install, launch
#   install.ps1 -NoLaunch    build and install only (for an install driven from another machine)

param([switch]$Quiet, [switch]$NoLaunch)

$ErrorActionPreference = "Stop"
trap { Write-Host $_; if (-not $Quiet) { Read-Host 'Press Enter to close' }; break }

& "$PSScriptRoot\build.ps1" -Quiet

$installer = Join-Path $env:LOCALAPPDATA "Temp\ClaudeSweeper-build\installer\ClaudeSweeper-Setup.exe"
if (-not (Test-Path $installer)) { throw "No installer at $installer" }

Get-Process ClaudeSweeper -ErrorAction SilentlyContinue | ForEach-Object { $_.CloseMainWindow() | Out-Null }
Start-Sleep -Milliseconds 700
Get-Process ClaudeSweeper -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "=== Installing ===" -ForegroundColor Cyan
$run = Start-Process -FilePath $installer -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
if ($run.ExitCode -ne 0) { throw "The installer exited with $($run.ExitCode)" }

$installed = Join-Path $env:LOCALAPPDATA "Programs\Claude Sweeper\ClaudeSweeper.exe"
if (-not (Test-Path $installed)) { throw "Installed, but $installed is missing" }

# Windows 11 has no public pin verb. An optional helper (set YKIT to a folder holding
# BuildKit.ps1) pins it; without one, pin it by hand. Add-TaskbarPin returns a word, not a boolean.
$pin = "no pin helper"
if ($env:YKIT -and (Test-Path "$env:YKIT\BuildKit.ps1")) {
    . "$env:YKIT\BuildKit.ps1"
    $pin = Add-TaskbarPin $installed
}

# The build directory is not a deliverable, and an installer left lying about is the thing that
# gets double-clicked six months from now.
Remove-Item -Recurse -Force (Join-Path $env:LOCALAPPDATA "Temp\ClaudeSweeper-build") -ErrorAction SilentlyContinue

Write-Host "Installed $installed" -ForegroundColor Green
if ($pin -ne "pinned") { "Taskbar pin: $pin - pin it by hand." }
if (-not $NoLaunch) { Start-Process $installed }
if (-not $Quiet) { Read-Host 'Press Enter to close' }
