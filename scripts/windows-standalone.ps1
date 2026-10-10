# Independent Windows profile: SQLite, local files, API and Vite only.
param(
  [ValidateSet('init', 'up', 'down', 'status', 'backup', 'restore')]
  [string]$Action = 'up',
  [string]$ArchiveDir = '',
  [ValidateSet('dev', 'static')]
  [string]$Frontend = 'dev'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Profile = Join-Path $RepoRoot 'config\startup-profiles\local-lite.env'
$DataDir = Join-Path $RepoRoot '.local-data'
$RunDir = Join-Path $RepoRoot '.local-run\standalone'
$StatePath = Join-Path $RunDir 'processes.json'
$BackendPython = Join-Path $RepoRoot 'backend\.venv\Scripts\python.exe'
$ViteEntry = Join-Path $RepoRoot 'frontend\node_modules\vite\bin\vite.js'

function New-RandomHex {
  param([int]$Bytes = 24)
  $buffer = New-Object byte[] $Bytes
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
  return [BitConverter]::ToString($buffer).Replace('-', '').ToLowerInvariant()
}

function Initialize-Profile {
  if (Test-Path -LiteralPath $Profile) { return }
  $content = @(
    'ATP_LOCAL_MODE=true'
    'ATP_LOCAL_DATA_DIR=.local-data'
    'APP_ENV=local'
    'APP_AUTH_COOKIE_SECURE=false'
    'APP_AUTH_COOKIE_SAMESITE=lax'
    'APP_AUTO_CREATE_TABLES=false'
    'ENCRYPTION_KEY='
    'APP_CORS_ORIGINS=http://127.0.0.1:5174,http://localhost:5174'
    'ADB_SCAN_ENABLED=false'
    'PERFORMANCE_NODE_ENABLED=false'
    'FIRST_ADMIN_USERNAME=admin'
    "FIRST_ADMIN_PASSWORD=$(New-RandomHex)"
    "APP_SECRET_KEY=$(New-RandomHex -Bytes 32)"
    'VITE_BACKEND_ORIGIN=http://127.0.0.1:8001'
    'VITE_ATP_LOCAL_MODE=true'
  ) -join "`r`n"
  [System.IO.File]::WriteAllText($Profile, "$content`r`n", [System.Text.UTF8Encoding]::new($false))
  Write-Host "Created private local profile: $Profile"
}

function Get-OwnProcess {
  param([int]$ProcessId, [string]$Marker)
  $process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
  if ($process -and $process.CommandLine -like "*$Marker*") { return $process }
  return $null
}

function Stop-OwnProcesses {
  if (-not (Test-Path -LiteralPath $StatePath)) { return }
  $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
  foreach ($entry in @($state.backend, $state.frontend)) {
    if ($null -eq $entry) { continue }
    $process = Get-OwnProcess -ProcessId ([int]$entry.pid) -Marker ([string]$entry.marker)
    if ($process) {
      # Kill this verified process tree so browser/load-injector children cannot outlive local ATP.
      & taskkill.exe /PID $process.ProcessId /T /F 2>&1 | Out-Null
    }
  }
  Remove-Item -LiteralPath $StatePath -Force
}

function Assert-FreePort {
  param([int]$Port)
  $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  if ($listener) { throw "Port $Port is occupied; stop the other process before starting local ATP." }
}

function Wait-Ready {
  param([string]$Url, [int]$Seconds = 120)
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -eq 200) { return }
    } catch { }
    Start-Sleep -Milliseconds 500
  }
  throw "Local service did not become ready: $Url. See logs in $RunDir"
}

function Write-BackupManifest {
  param([string]$TargetDir)
  $rootPath = (Resolve-Path -LiteralPath $TargetDir).Path
  $entries = @(Get-ChildItem -LiteralPath $TargetDir -File -Recurse | ForEach-Object {
    $relative = $_.FullName.Substring($rootPath.Length + 1).Replace('\', '/')
    @{ path = $relative; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
  })
  @{ format = 1; files = $entries } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $TargetDir 'manifest.json') -Encoding UTF8
}

function Assert-BackupManifest {
  param([string]$SourceDir)
  $manifestPath = Join-Path $SourceDir 'manifest.json'
  if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Backup manifest is missing.' }
  $rootPath = (Resolve-Path -LiteralPath $SourceDir).Path
  $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  if ($manifest.format -ne 1) { throw 'Unsupported backup manifest format.' }
  $listed = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
  foreach ($entry in @($manifest.files)) {
    if (-not $listed.Add([string]$entry.path)) { throw 'Backup manifest contains a duplicate path.' }
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $rootPath $entry.path))
    if (-not $candidate.StartsWith($rootPath + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Backup manifest contains an invalid path.' }
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { throw "Backup file missing: $($entry.path)" }
    $actual = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash
    if ($actual -ine $entry.sha256) { throw "Backup checksum mismatch: $($entry.path)" }
  }
  foreach ($file in @(Get-ChildItem -LiteralPath $SourceDir -File -Recurse)) {
    $relative = $file.FullName.Substring($rootPath.Length + 1).Replace('\', '/')
    if ($relative -ne 'manifest.json' -and -not $listed.Contains($relative)) { throw "Unlisted backup file: $relative" }
  }
}

if ($Action -eq 'init') { Initialize-Profile; exit 0 }
if ($Action -eq 'down') { Stop-OwnProcesses; exit 0 }
if ($Action -eq 'status') {
  if (-not (Test-Path -LiteralPath $StatePath)) { Write-Host 'Local profile is stopped.'; exit 0 }
  $state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
  foreach ($entry in @($state.backend, $state.frontend)) {
    if ($null -eq $entry) { continue }
    $process = Get-OwnProcess -ProcessId ([int]$entry.pid) -Marker ([string]$entry.marker)
    Write-Host "$($entry.name): $(if ($process) { 'running' } else { 'stopped' })"
  }
  exit 0
}

if ($Action -eq 'backup') {
  if (-not $ArchiveDir) { throw 'Backup requires -ArchiveDir.' }
  $absoluteArchive = [System.IO.Path]::GetFullPath($ArchiveDir)
  $absoluteData = [System.IO.Path]::GetFullPath($DataDir)
  if ($absoluteArchive.StartsWith($absoluteData + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Backup destination cannot be inside the local data directory.' }
  if (Test-Path -LiteralPath $StatePath) { throw 'Stop local ATP before backup to keep SQLite and files consistent.' }
  if (Test-Path -LiteralPath $ArchiveDir) { throw "Backup destination exists: $ArchiveDir" }
  if (-not (Test-Path -LiteralPath $Profile)) { throw 'Local profile is missing.' }
  New-Item -ItemType Directory -Path $ArchiveDir | Out-Null
  Copy-Item -LiteralPath $Profile -Destination (Join-Path $ArchiveDir 'local-lite.env')
  if (Test-Path -LiteralPath $DataDir) { Copy-Item -LiteralPath $DataDir -Destination (Join-Path $ArchiveDir 'data') -Recurse }
  Write-BackupManifest -TargetDir $ArchiveDir
  Write-Host "Backup saved: $ArchiveDir"
  exit 0
}
if ($Action -eq 'restore') {
  if (-not $ArchiveDir) { throw 'Restore requires -ArchiveDir.' }
  if ((Test-Path -LiteralPath $Profile) -or (Test-Path -LiteralPath $DataDir)) { throw 'Restore requires a fresh local profile and data directory.' }
  $sourceProfile = Join-Path $ArchiveDir 'local-lite.env'
  if (-not (Test-Path -LiteralPath $sourceProfile)) { throw 'Backup profile is missing.' }
  Assert-BackupManifest -SourceDir $ArchiveDir
  Copy-Item -LiteralPath $sourceProfile -Destination $Profile
  $sourceData = Join-Path $ArchiveDir 'data'
  if (Test-Path -LiteralPath $sourceData) { Copy-Item -LiteralPath $sourceData -Destination $DataDir -Recurse }
  Write-Host 'Local profile restored. Run -Action up.'
  exit 0
}

Initialize-Profile
if (-not (Test-Path -LiteralPath $BackendPython)) { throw "Backend Python missing: $BackendPython" }
if ($Frontend -eq 'dev' -and -not (Test-Path -LiteralPath $ViteEntry)) { throw "Frontend dependencies missing: $ViteEntry" }
if ($Frontend -eq 'static' -and -not (Test-Path -LiteralPath (Join-Path $RepoRoot 'frontend\dist\index.html'))) { throw 'Static frontend missing. Build it with VITE_ATP_LOCAL_MODE=true npm run build.' }
if (Test-Path -LiteralPath $StatePath) { throw 'Local ATP already has process state. Run -Action status or down first.' }
Assert-FreePort -Port 8001
if ($Frontend -eq 'dev') { Assert-FreePort -Port 5174 }
New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
foreach ($line in (Get-Content -LiteralPath $Profile -Encoding UTF8)) {
  if ($line -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
    [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
  }
}
$backend = Start-Process -FilePath $BackendPython -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8001') -WorkingDirectory (Join-Path $RepoRoot 'backend') -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RunDir 'backend.out.log') -RedirectStandardError (Join-Path $RunDir 'backend.err.log')
try {
  Wait-Ready -Url 'http://127.0.0.1:8001/health'
  if ($Frontend -eq 'dev') {
    $frontendProcess = Start-Process -FilePath 'node.exe' -ArgumentList @($ViteEntry, '--host', '127.0.0.1', '--port', '5174', '--strictPort') -WorkingDirectory (Join-Path $RepoRoot 'frontend') -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RunDir 'frontend.out.log') -RedirectStandardError (Join-Path $RunDir 'frontend.err.log')
    try {
      Wait-Ready -Url 'http://127.0.0.1:5174/login'
    } catch {
      & taskkill.exe /PID $frontendProcess.Id /T /F 2>&1 | Out-Null
      throw
    }
    $frontendState = @{ name = 'frontend'; pid = $frontendProcess.Id; marker = 'vite.js' }
    $localUrl = 'http://127.0.0.1:5174/'
  } else {
    Wait-Ready -Url 'http://127.0.0.1:8001/login'
    $frontendState = $null
    $localUrl = 'http://127.0.0.1:8001/'
  }
  @{ backend = @{ name = 'backend'; pid = $backend.Id; marker = 'app.main:app' }; frontend = $frontendState; url = $localUrl } | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $StatePath -Encoding UTF8
  Write-Host "Local ATP is running at $localUrl"
} catch {
  & taskkill.exe /PID $backend.Id /T /F 2>&1 | Out-Null
  throw
}
