# Windows-local ATP: isolated WSL Docker data services plus Windows app processes.
param(
  [ValidateSet('init', 'up', 'down', 'status', 'doctor', 'backup', 'restore')]
  [string]$Action = 'up',
  [string]$ArchiveDir = ''
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Profile = Join-Path $RepoRoot 'config\startup-profiles\local-all.env'
$Template = Join-Path $RepoRoot 'config\startup-profiles\local-all.env.example'
$Compose = Join-Path $RepoRoot 'docker-compose.windows-local.yml'
$Startup = Join-Path $PSScriptRoot 'startup.ps1'
$BackendPython = Join-Path $RepoRoot 'backend\.venv\Scripts\python.exe'

function New-RandomHex {
  param([int]$Bytes = 24)
  $buffer = New-Object byte[] $Bytes
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
  return [BitConverter]::ToString($buffer).Replace('-', '').ToLowerInvariant()
}

function Set-ProfileValue {
  param([string]$Content, [string]$Key, [string]$Value)
  $pattern = '(?m)^' + [regex]::Escape($Key) + '=.*$'
  $line = "$Key=$Value"
  if ([regex]::IsMatch($Content, $pattern)) {
    return [regex]::Replace($Content, $pattern, $line)
  }
  return $Content.TrimEnd() + "`r`n" + $line + "`r`n"
}

function Initialize-Profile {
  if (Test-Path -LiteralPath $Profile) {
    Write-Host "Local profile already exists: $Profile"
    return
  }
  $content = Get-Content -LiteralPath $Template -Raw -Encoding UTF8
  $values = @{
    POSTGRES_PORT = '15432'
    POSTGRES_PASSWORD = (New-RandomHex)
    REDIS_PORT = '16379'
    REDIS_PASSWORD = (New-RandomHex)
    MINIO_PORT = '19000'
    MINIO_ROOT_PASSWORD = (New-RandomHex)
    APP_SECRET_KEY = (New-RandomHex -Bytes 32)
    FIRST_ADMIN_PASSWORD = (New-RandomHex)
    VITE_BACKEND_ORIGIN = 'http://127.0.0.1:8000'
  }
  foreach ($key in $values.Keys) {
    $content = Set-ProfileValue -Content $content -Key $key -Value $values[$key]
  }
  [System.IO.File]::WriteAllText($Profile, $content, [System.Text.UTF8Encoding]::new($false))
  Write-Host "Created private local profile: $Profile"
  Write-Host 'Initial admin username: admin; initial password is in FIRST_ADMIN_PASSWORD of that ignored profile.'
}

function ConvertTo-WslPath {
  param([string]$Path)
  $absolute = [System.IO.Path]::GetFullPath($Path)
  if ($absolute -notmatch '^([A-Za-z]):\\(.*)$') {
    throw "WSL path conversion requires a Windows drive path: $absolute"
  }
  $drive = $Matches[1].ToLowerInvariant()
  $remainder = $Matches[2].Replace('\', '/')
  return "/mnt/$drive/$remainder"
}

function Invoke-Compose {
  param([string[]]$ComposeArgs)
  $wslProfile = ConvertTo-WslPath $Profile
  $wslCompose = ConvertTo-WslPath $Compose
  & wsl.exe -u root -e docker compose --project-name atp-windows-local --env-file $wslProfile -f $wslCompose @ComposeArgs
  if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed (exit $LASTEXITCODE)." }
}

function Invoke-Docker {
  param([string[]]$DockerArgs)
  & wsl.exe -u root -e docker @DockerArgs
  if ($LASTEXITCODE -ne 0) { throw "Docker failed (exit $LASTEXITCODE)." }
}

function Get-ArchiveDirectory {
  if ([string]::IsNullOrWhiteSpace($ArchiveDir)) {
    return (Join-Path $RepoRoot ('.local-run\portable-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss')))
  }
  return [System.IO.Path]::GetFullPath($ArchiveDir)
}

function Invoke-VolumeArchive {
  param([string]$Volume, [string]$Directory, [string]$Mode)
  $wslDirectory = ConvertTo-WslPath $Directory
  $archiveName = "$Volume.tar"
  if ($Mode -eq 'export') {
    Invoke-Docker -DockerArgs @('run', '--rm', '-v', "${Volume}:/source:ro", '-v', "${wslDirectory}:/backup", 'alpine:3.20', 'tar', '-C', '/source', '-cf', "/backup/$archiveName", '.')
  } else {
    Invoke-Docker -DockerArgs @('run', '--rm', '-v', "${Volume}:/source", '-v', "${wslDirectory}:/backup:ro", 'alpine:3.20', 'tar', '-C', '/source', '-xf', "/backup/$archiveName")
  }
}

function Wait-LocalPort {
  param([int]$Port, [int]$Seconds = 45)
  $deadline = (Get-Date).AddSeconds($Seconds)
  do {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
      $connect = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
      if ($connect.AsyncWaitHandle.WaitOne(1000)) {
        $client.EndConnect($connect)
        return
      }
    } catch { } finally { $client.Dispose() }
    Start-Sleep -Milliseconds 500
  } while ((Get-Date) -lt $deadline)
  throw "Local service on 127.0.0.1:$Port did not become reachable."
}

function Import-PrivateProfile {
  $previous = @{}
  foreach ($line in (Get-Content -LiteralPath $Profile -Encoding UTF8)) {
    if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { continue }
    $key = $Matches[1]
    $value = $Matches[2]
    $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
    [Environment]::SetEnvironmentVariable($key, $value, 'Process')
  }
  return $previous
}

function Restore-Environment {
  param([hashtable]$Previous)
  foreach ($key in $Previous.Keys) {
    [Environment]::SetEnvironmentVariable($key, $Previous[$key], 'Process')
  }
}

function Invoke-App {
  param([string]$AppAction)
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Startup -Action $AppAction -Profile local-all
  if ($LASTEXITCODE -ne 0) { throw "Windows ATP app action '$AppAction' failed (exit $LASTEXITCODE)." }
}

if ($Action -eq 'init') {
  Initialize-Profile
  exit 0
}

if ($Action -eq 'restore') {
  if ([string]::IsNullOrWhiteSpace($ArchiveDir)) { throw 'Restore requires -ArchiveDir.' }
  $directory = Get-ArchiveDirectory
  $sourceProfile = Join-Path $directory 'local-all.env'
  if (-not (Test-Path -LiteralPath $sourceProfile)) { throw "Backup profile missing: $sourceProfile" }
  if (Test-Path -LiteralPath $Profile) { throw "Local profile already exists; restore requires a fresh local environment: $Profile" }
  Invoke-Docker -DockerArgs @('info', '--format', '{{.ServerVersion}}')
  $volumes = @('atp-windows-local_postgres_data', 'atp-windows-local_redis_data', 'atp-windows-local_minio_data')
  $manifestPath = Join-Path $directory 'SHA256SUMS.txt'
  if (-not (Test-Path -LiteralPath $manifestPath)) { throw "Backup checksum manifest missing: $manifestPath" }
  $manifest = Get-Content -LiteralPath $manifestPath
  foreach ($name in @('local-all.env') + @($volumes | ForEach-Object { "${_}.tar" })) {
    $entry = @($manifest | Where-Object { $_ -match ('^[0-9a-fA-F]{64}  ' + [regex]::Escape($name) + '$') })
    if ($entry.Count -ne 1) { throw "Backup checksum entry missing or duplicated: $name" }
    $expected = $entry[0].Substring(0, 64)
    $actual = (Get-FileHash -LiteralPath (Join-Path $directory $name) -Algorithm SHA256).Hash
    if ($actual -ne $expected) { throw "Backup checksum mismatch: $name" }
  }
  foreach ($volume in $volumes) {
    if (-not (Test-Path -LiteralPath (Join-Path $directory "$volume.tar"))) { throw "Volume archive missing: $volume.tar" }
    & wsl.exe -u root -e docker volume inspect $volume *> $null
    if ($LASTEXITCODE -eq 0) { throw "Docker volume already exists; restore requires a fresh local environment: $volume" }
  }
  Copy-Item -LiteralPath $sourceProfile -Destination $Profile
  foreach ($volume in $volumes) {
    Invoke-Docker -DockerArgs @('volume', 'create', $volume)
    Invoke-VolumeArchive -Volume $volume -Directory $directory -Mode import
  }
  Write-Host "Restored local profile and three data volumes from $directory"
  Write-Host 'Run -Action up to start the restored local environment.'
  exit 0
}

if ($Action -eq 'up') { Initialize-Profile }
if (-not (Test-Path -LiteralPath $Profile)) {
  throw "Local profile missing. Run this script with -Action init first: $Profile"
}

switch ($Action) {
  'up' {
    Invoke-Compose -ComposeArgs @('up', '-d', '--wait')
    foreach ($port in @(15432, 16379, 19000)) { Wait-LocalPort -Port $port }
    if (-not (Test-Path -LiteralPath $BackendPython)) { throw "Backend Python missing: $BackendPython" }
    $previous = Import-PrivateProfile
    try {
      Push-Location (Join-Path $RepoRoot 'backend')
      try { & $BackendPython -m alembic upgrade head } finally { Pop-Location }
      if ($LASTEXITCODE -ne 0) { throw 'Local database migration failed.' }
    } finally { Restore-Environment -Previous $previous }
    Invoke-App -AppAction up
  }
  'down' {
    Invoke-App -AppAction down
    Invoke-Compose -ComposeArgs @('stop')
  }
  'status' {
    Invoke-Compose -ComposeArgs @('ps')
    Invoke-App -AppAction status
  }
  'doctor' {
    Invoke-Compose -ComposeArgs @('config', '--quiet')
    Invoke-App -AppAction doctor
  }
  'backup' {
    Invoke-Docker -DockerArgs @('info', '--format', '{{.ServerVersion}}')
    $directory = Get-ArchiveDirectory
    if (Test-Path -LiteralPath $directory) { throw "Backup directory already exists: $directory" }
    New-Item -ItemType Directory -Path $directory | Out-Null
    Invoke-App -AppAction down
    Invoke-Compose -ComposeArgs @('stop')
    Copy-Item -LiteralPath $Profile -Destination (Join-Path $directory 'local-all.env')
    foreach ($volume in @('atp-windows-local_postgres_data', 'atp-windows-local_redis_data', 'atp-windows-local_minio_data')) {
      Invoke-VolumeArchive -Volume $volume -Directory $directory -Mode export
    }
    $names = @('local-all.env', 'atp-windows-local_postgres_data.tar', 'atp-windows-local_redis_data.tar', 'atp-windows-local_minio_data.tar')
    $checksums = foreach ($name in $names) {
      $hash = (Get-FileHash -LiteralPath (Join-Path $directory $name) -Algorithm SHA256).Hash.ToLowerInvariant()
      "$hash  $name"
    }
    [System.IO.File]::WriteAllLines((Join-Path $directory 'SHA256SUMS.txt'), [string[]]$checksums)
    Write-Host "Portable backup created: $directory"
    Write-Host 'The backup contains the local profile and credentials. Keep it private.'
  }
}
