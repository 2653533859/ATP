# Open either independent ATP profile without modifying the other profile.
param(
  [ValidateSet('local', 'server', 'status', 'open')]
  [string]$Action = 'status',
  [ValidateSet('local', 'server')]
  [string]$Mode = 'local',
  [ValidateSet('dev', 'static')]
  [string]$Frontend = 'static',
  [string]$ServerUrl = 'http://127.0.0.1:5173'
)

$ErrorActionPreference = 'Stop'
$LocalRunner = Join-Path $PSScriptRoot 'windows-standalone.ps1'
$LocalDevUrl = 'http://127.0.0.1:5174/'
$LocalStaticUrl = 'http://127.0.0.1:8001/'

function Test-LocalReady {
  try {
    $identity = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/v1/runtime' -TimeoutSec 3
    return $identity.mode -eq 'local' -and $identity.database -eq 'sqlite'
  } catch { return $false }
}

function Test-ServerReady {
  try {
    $response = Invoke-WebRequest -Uri ($ServerUrl.TrimEnd('/') + '/login') -UseBasicParsing -TimeoutSec 3
    return $response.StatusCode -eq 200
  } catch { return $false }
}

if ($Action -eq 'status') {
  Write-Host "local: $(if (Test-LocalReady) { 'ready' } else { 'stopped' })"
  Write-Host "server page: $(if (Test-ServerReady) { 'ready' } else { 'unavailable' })"
  exit 0
}

if ($Action -eq 'local') {
  if (-not (Test-LocalReady)) {
    & $LocalRunner -Action up -Frontend $Frontend
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  }
  $url = if ($Frontend -eq 'static') { $LocalStaticUrl } else { $LocalDevUrl }
  if ($Frontend -eq 'dev') {
    try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 | Out-Null }
    catch { throw 'Local Vite page is unavailable; start local profile with -Frontend dev.' }
  }
  Start-Process $url
  Write-Host "Opened local ATP: $url"
  exit 0
}

if ($Action -eq 'server') {
  if (-not (Test-ServerReady)) { throw "Server page is unavailable: $ServerUrl" }
  Start-Process $ServerUrl
  Write-Host "Opened server ATP: $ServerUrl"
  exit 0
}

if ($Mode -eq 'local') {
  if (-not (Test-LocalReady)) { throw 'Local ATP is stopped. Run -Action local first.' }
  $url = if ($Frontend -eq 'static') { $LocalStaticUrl } else { $LocalDevUrl }
} else {
  if (-not (Test-ServerReady)) { throw "Server page is unavailable: $ServerUrl" }
  $url = $ServerUrl
}
Start-Process $url
Write-Host "Opened $Mode ATP: $url"
