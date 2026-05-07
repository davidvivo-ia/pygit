# Build script — Windows PowerShell.
#
# Usage:
#   pwsh packaging/build.ps1
#
# Produces: dist/pygit/  (ready to zip and ship).

param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot/.."
Set-Location $root

if ($Clean) {
    Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
}

if (-not (Test-Path .venv)) {
    python -m venv .venv
}

.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -e ".[dev]"
pip install pyinstaller

pyinstaller --clean --noconfirm packaging/pygit.spec

Write-Host ""
Write-Host "Build complete: dist/pygit/  (zip this folder for distribution)"
