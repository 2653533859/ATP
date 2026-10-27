# Independent Windows profile: SQLite, local files, API and Vite only.
param(
  [ValidateSet('init', 'up', 'down', 'status', 'backup', 'restore', 'desktop')]
  [string]$Action = 'up',
  [string]$ArchiveDir = '',
  [string]$DataDir = '',
  [ValidateSet('dev', 'static')]
  [string]$Frontend = 'dev'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Profile = Join-Path $RepoRoot 'config\startup-profiles\local-lite.env'
$RequestedDataDir = $DataDir
$LegacyDataDir = Join-Path $RepoRoot '.local-data'
$RunDir = Join-Path $RepoRoot '.local-run\standalone'
$StatePath = Join-Path $RunDir 'processes.json'
$BackendPython = Join-Path $RepoRoot 'backend\.venv\Scripts\python.exe'
$BackendExe = Join-Path $RepoRoot 'backend\atp-backend.exe'
$ViteEntry = Join-Path $RepoRoot 'frontend\node_modules\vite\bin\vite.js'

function New-RandomHex {
  param([int]$Bytes = 24)
  $buffer = New-Object byte[] $Bytes
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
  return [BitConverter]::ToString($buffer).Replace('-', '').ToLowerInvariant()
}

function Resolve-DataDir {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) { throw 'ATP_LOCAL_DATA_DIR is empty.' }
  $fullPath = if ([System.IO.Path]::IsPathRooted($Value)) {
    [System.IO.Path]::GetFullPath($Value)
  } else {
    [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Value))
  }
  return $fullPath.TrimEnd('\', '/')
}

function Assert-RequestedDataDir {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) { throw '-DataDir is empty.' }
  $resolved = [System.IO.Path]::GetFullPath($Value).TrimEnd('\', '/')
  if ($resolved -notmatch '^[A-Za-z]:\\') {
    throw '-DataDir must be an absolute path on a local drive.'
  }
  $drive = [System.IO.Path]::GetPathRoot($resolved).TrimEnd('\')
  if ($resolved -ieq $drive) { throw '-DataDir cannot be a drive root.' }
  $disk = Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' |
    Where-Object { $_.DeviceID -ieq $drive } | Select-Object -First 1
  if (-not $disk) { throw '-DataDir must be on a fixed local drive.' }
  if ($disk.FreeSpace -lt 20GB) { throw '-DataDir drive needs at least 20 GB free space.' }
  return $resolved
}

function Select-NewAtpDataDir {
  $candidateDisks = Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' |
    Where-Object { $_.DeviceID -ine 'C:' -and $_.FreeSpace -ge 20GB } |
    Sort-Object -Property @{ Expression = 'FreeSpace'; Descending = $true }, 'DeviceID'
  foreach ($disk in $candidateDisks) {
    $candidate = Join-Path "$($disk.DeviceID)\" 'ATP_resources'
    if (-not (Test-Path -LiteralPath $candidate)) { return $candidate }
    if (-not @(Get-ChildItem -LiteralPath $candidate -Force | Select-Object -First 1).Count) { return $candidate }
  }
  throw 'No non-C fixed drive has 20 GB free with an unused ATP_resources directory. Specify -DataDir.'
}

function Get-ProfileDataDir {
  param([string]$ProfilePath)
  $line = Get-Content -LiteralPath $ProfilePath -Encoding UTF8 |
    Where-Object { $_ -match '^ATP_LOCAL_DATA_DIR=' } | Select-Object -Last 1
  if (-not $line) { return Resolve-DataDir '.local-data' }
  $value = $line.Substring('ATP_LOCAL_DATA_DIR='.Length).Trim()
  if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
    $value = $value.Substring(1, $value.Length - 2)
  }
  return Resolve-DataDir $value
}

function Initialize-Profile {
  if (Test-Path -LiteralPath $Profile) {
    if ($RequestedDataDir -and (Assert-RequestedDataDir $RequestedDataDir) -ine (Get-ProfileDataDir $Profile)) {
      throw 'Existing local profile uses a different data directory; data is not moved automatically.'
    }
    return
  }
  if (Test-Path -LiteralPath $LegacyDataDir) {
    throw 'Legacy .local-data exists without a profile; choose a recovery path before initializing.'
  }
  $selectedDataDir = if ($RequestedDataDir) { Assert-RequestedDataDir $RequestedDataDir } else { Select-NewAtpDataDir }
  if (Test-Path -LiteralPath $selectedDataDir) {
    $contents = @(Get-ChildItem -LiteralPath $selectedDataDir -Force | Select-Object -First 1)
    if ($contents.Count -gt 0) { throw "Data directory is not empty: $selectedDataDir" }
  }
  New-Item -ItemType Directory -Path $selectedDataDir -Force | Out-Null
  $content = @(
    'ATP_LOCAL_MODE=true'
    "ATP_LOCAL_DATA_DIR=$selectedDataDir"
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
  $profileParent = Split-Path -Parent $Profile
  if ($profileParent -and -not (Test-Path -LiteralPath $profileParent)) {
    New-Item -ItemType Directory -Path $profileParent -Force | Out-Null
  }
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

function Get-FileSha256 {
  param([string]$Path)
  $stream = [System.IO.File]::OpenRead($Path)
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
  } finally {
    $sha.Dispose()
    $stream.Dispose()
  }
}

function Write-BackupManifest {
  param([string]$TargetDir)
  $rootPath = (Resolve-Path -LiteralPath $TargetDir).Path
  $entries = @(Get-ChildItem -LiteralPath $TargetDir -File -Recurse | ForEach-Object {
    $relative = $_.FullName.Substring($rootPath.Length + 1).Replace('\', '/')
    @{ path = $relative; sha256 = (Get-FileSha256 $_.FullName) }
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
    $actual = Get-FileSha256 $candidate
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
if ($Action -eq 'desktop') {
  $DesktopScript = Join-Path $RepoRoot 'scripts\windows-desktop.py'
  if (-not (Test-Path -LiteralPath $BackendPython -PathType Leaf)) {
    throw "Backend Python virtual environment missing for desktop mode: $BackendPython"
  }
  if (-not (Test-Path -LiteralPath $DesktopScript -PathType Leaf)) {
    throw "Desktop host script missing: $DesktopScript"
  }
  & $BackendPython $DesktopScript
  exit $LASTEXITCODE
}

if ($Action -eq 'backup') {
  if (-not $ArchiveDir) { throw 'Backup requires -ArchiveDir.' }
  $absoluteArchive = [System.IO.Path]::GetFullPath($ArchiveDir)
  if (-not (Test-Path -LiteralPath $Profile)) { throw 'Local profile is missing.' }
  $profileDataDir = Get-ProfileDataDir $Profile
  $absoluteData = [System.IO.Path]::GetFullPath($profileDataDir)
  if ($absoluteArchive -ieq $absoluteData -or $absoluteArchive.StartsWith($absoluteData + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Backup destination cannot be inside the local data directory.' }
  if (Test-Path -LiteralPath $StatePath) { throw 'Stop local ATP before backup to keep SQLite and files consistent.' }
  if (Test-Path -LiteralPath $ArchiveDir) { throw "Backup destination exists: $ArchiveDir" }
  New-Item -ItemType Directory -Path $ArchiveDir | Out-Null
  Copy-Item -LiteralPath $Profile -Destination (Join-Path $ArchiveDir 'local-lite.env')
  if (Test-Path -LiteralPath $profileDataDir) { Copy-Item -LiteralPath $profileDataDir -Destination (Join-Path $ArchiveDir 'data') -Recurse }
  Write-BackupManifest -TargetDir $ArchiveDir
  Write-Host "Backup saved: $ArchiveDir"
  exit 0
}
if ($Action -eq 'restore') {
  if (-not $ArchiveDir) { throw 'Restore requires -ArchiveDir.' }
  $sourceProfile = Join-Path $ArchiveDir 'local-lite.env'
  if (-not (Test-Path -LiteralPath $sourceProfile)) { throw 'Backup profile is missing.' }
  Assert-BackupManifest -SourceDir $ArchiveDir
  $restoreDataDir = if ($RequestedDataDir) { Assert-RequestedDataDir $RequestedDataDir } else { Get-ProfileDataDir $sourceProfile }
  if ((Test-Path -LiteralPath $Profile) -or (Test-Path -LiteralPath $restoreDataDir)) { throw 'Restore requires a fresh local profile and data directory.' }
  $absoluteArchive = [System.IO.Path]::GetFullPath($ArchiveDir)
  if ($restoreDataDir.StartsWith($absoluteArchive + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Restore data directory cannot be inside the backup archive.'
  }
  $profileLines = @(Get-Content -LiteralPath $sourceProfile -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^ATP_LOCAL_DATA_DIR=') { "ATP_LOCAL_DATA_DIR=$restoreDataDir" } else { $_ }
  })
  if (-not @($profileLines | Where-Object { $_ -match '^ATP_LOCAL_DATA_DIR=' }).Count) {
    $profileLines += "ATP_LOCAL_DATA_DIR=$restoreDataDir"
  }
  $sourceData = Join-Path $ArchiveDir 'data'
  $parentDir = Split-Path -Parent $restoreDataDir
  if ($parentDir -and -not (Test-Path -LiteralPath $parentDir)) {
    New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
  }
  if (Test-Path -LiteralPath $sourceData) {
    Copy-Item -LiteralPath $sourceData -Destination $restoreDataDir -Recurse
  } else {
    New-Item -ItemType Directory -Path $restoreDataDir | Out-Null
  }
  $profileParent = Split-Path -Parent $Profile
  if ($profileParent -and -not (Test-Path -LiteralPath $profileParent)) {
    New-Item -ItemType Directory -Path $profileParent -Force | Out-Null
  }
  [System.IO.File]::WriteAllLines($Profile, $profileLines, [System.Text.UTF8Encoding]::new($false))
  Write-Host 'Local profile restored. Run -Action up.'
  exit 0
}

Initialize-Profile
$useFrozenBackend = Test-Path -LiteralPath $BackendExe -PathType Leaf
if (-not $useFrozenBackend -and -not (Test-Path -LiteralPath $BackendPython -PathType Leaf)) {
  throw "Bundled backend or Backend Python missing: $BackendExe / $BackendPython"
}
if ($useFrozenBackend -and -not (Test-Path -LiteralPath $ViteEntry -PathType Leaf)) { $Frontend = 'static' }
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
$backendCommand = if ($useFrozenBackend) { $BackendExe } else { $BackendPython }
$backendArgs = if ($useFrozenBackend) { @('--host', '127.0.0.1', '--port', '8001') } else { @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8001') }
$backendMarker = if ($useFrozenBackend) { 'atp-backend.exe' } else { 'app.main:app' }
$backend = Start-Process -FilePath $backendCommand -ArgumentList $backendArgs -WorkingDirectory (Join-Path $RepoRoot 'backend') -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $RunDir 'backend.out.log') -RedirectStandardError (Join-Path $RunDir 'backend.err.log')
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
  @{ backend = @{ name = 'backend'; pid = $backend.Id; marker = $backendMarker }; frontend = $frontendState; url = $localUrl } | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $StatePath -Encoding UTF8
  Write-Host "Local ATP is running at $localUrl"
} catch {
  & taskkill.exe /PID $backend.Id /T /F 2>&1 | Out-Null
  throw
}
