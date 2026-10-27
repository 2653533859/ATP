[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repoRoot 'backend\.venv\Scripts\python.exe'
$entry = Join-Path $repoRoot 'backend\frozen_entry.py'
$outputRoot = Join-Path $repoRoot '.local-run\pyinstaller'
$distPath = Join-Path $outputRoot 'dist'
$buildPath = Join-Path $outputRoot 'build'
$specPath = Join-Path $outputRoot 'spec'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
  throw "Backend virtual environment missing: $python"
}
& $python -c 'import PyInstaller'
if ($LASTEXITCODE -ne 0) {
  throw 'Install backend/requirements-build.txt into backend/.venv first.'
}
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

& $python -m PyInstaller `
  --noconfirm --onedir --console --noupx `
  --name atp-backend `
  --distpath $distPath --workpath $buildPath --specpath $specPath `
  --paths (Join-Path $repoRoot 'backend') `
  --collect-submodules app `
  --collect-submodules uvicorn `
  --collect-submodules sqlalchemy.dialects.sqlite `
  --collect-submodules passlib.handlers `
  --collect-submodules celery `
  --collect-submodules kombu `
  --collect-submodules grpc_tools `
  --collect-data grpc_tools `
  --hidden-import aiosqlite `
  --add-data "$(Join-Path $repoRoot 'backend\assets\scrcpy-server.jar');backend/assets" `
  --add-data "$(Join-Path $repoRoot 'scripts\device_agent.py');scripts" `
  $entry
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

$exe = Join-Path $distPath 'atp-backend\atp-backend.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Packaged backend missing: $exe" }
Write-Host "Bundled backend: $exe"
Write-Host 'For the portable layout, copy the atp-backend directory as backend/ beside frontend/dist/ and scripts/.'
