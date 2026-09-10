# Builds Claude Sweeper for Windows: the purge engine's modules, the PyInstaller bundle and the
# Inno Setup installer. Nothing built lands in the repo; everything goes to
# %LOCALAPPDATA%\Temp\ClaudeSweeper-build. install.ps1 is the one to run.

param([switch]$Quiet)

$ErrorActionPreference = "Stop"
trap { Write-Host $_; if (-not $Quiet) { Read-Host 'Press Enter to close' }; break }

$repo = $PSScriptRoot
$build = Join-Path $env:LOCALAPPDATA "Temp\ClaudeSweeper-build"
$dist = Join-Path $build "dist"
$work = Join-Path $build "work"
$out = Join-Path $build "installer"

$uv = (Get-Command uv.exe -ErrorAction SilentlyContinue).Path
if (-not $uv) { $uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe" }
if (-not (Test-Path $uv)) { throw "uv not found" }

Write-Host "=== 1. Clearing the last build ===" -ForegroundColor Cyan
if (Test-Path $build) { Remove-Item -Recurse -Force $build }
New-Item -ItemType Directory -Force -Path $build | Out-Null

Write-Host "`n=== 2. Environment and purge engine ===" -ForegroundColor Cyan
Push-Location $repo
try {
    & $uv sync --quiet
    Push-Location "$repo\purge"
    try { npm ci --no-audit --no-fund --silent } finally { Pop-Location }
    if (-not (Test-Path "$repo\purge\node_modules\classic-level")) { throw "npm ci left no classic-level in purge\node_modules" }

    Write-Host "`n=== 3. PyInstaller ===" -ForegroundColor Cyan
    & $uv run pyinstaller --noconfirm --distpath $dist --workpath $work "$repo\ClaudeSweeper.spec"
} finally {
    Pop-Location
}
if (-not (Test-Path "$dist\ClaudeSweeper\ClaudeSweeper.exe")) { throw "PyInstaller produced no ClaudeSweeper.exe in $dist" }

Write-Host "`n=== 4. Inno Setup ===" -ForegroundColor Cyan
$iscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $iscc)) { $iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Path }
if (-not $iscc) { throw "Inno Setup (ISCC.exe) not found" }

& $iscc "/O$out" "/DPayloadDir=$dist\ClaudeSweeper" "$repo\docs\installer.iss"
$installer = Join-Path $out "ClaudeSweeper-Setup.exe"
if (-not (Test-Path $installer)) { throw "Inno Setup produced no installer" }

Write-Host "`nBuilt $installer" -ForegroundColor Green
if (-not $Quiet) { Read-Host 'Press Enter to close' }
