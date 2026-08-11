[CmdletBinding()]
param(
  [ValidateSet('up', 'down', 'restart', 'status', 'logs', 'doctor')]
  [string]$Action = 'up',

  [ValidateRange(20, 500)]
  [int]$Tail = 120,

  [string]$EnvFile = ''
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot 'backend'
$BackendPython = Join-Path $BackendDir '.venv\Scripts\python.exe'
$RunDir = Join-Path $RepoRoot '.local-run'
$PidFile = Join-Path $RunDir 'android-worker.pid'
$StdoutLog = Join-Path $RunDir 'android-worker-out.log'
$StderrLog = Join-Path $RunDir 'android-worker-err.log'
$ConfiguredEnvFile = if ([string]::IsNullOrWhiteSpace($EnvFile)) {
  Join-Path $RepoRoot '.env'
} elseif ([System.IO.Path]::IsPathRooted($EnvFile)) {
  $EnvFile
} else {
  Join-Path $RepoRoot $EnvFile
}
$QueueList = 'android,mobile_special'

function Ensure-RunDir {
  if (-not (Test-Path $RunDir)) {
    New-Item -ItemType Directory -Path $RunDir | Out-Null
  }
}

function Get-DotEnvValues {
  $values = @{}
  $envPath = $ConfiguredEnvFile
  if (-not (Test-Path $envPath)) {
    return $values
  }

  foreach ($line in (Get-Content -Path $envPath -Encoding UTF8)) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
      $key = $Matches[1]
      $value = $Matches[2]
      if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
        $value = $value.Substring(1, $value.Length - 2)
      }
      $values[$key] = $value
    }
  }

  return $values
}

function Test-TcpEndpoint {
  param(
    [string]$HostName,
    [int]$Port,
    [int]$TimeoutMilliseconds = 1500
  )

  if ([string]::IsNullOrWhiteSpace($HostName) -or $Port -le 0) {
    return $false
  }

  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $task = $client.ConnectAsync($HostName, $Port)
    if (-not $task.Wait($TimeoutMilliseconds)) {
      return $false
    }
    return $client.Connected
  } catch {
    return $false
  } finally {
    $client.Dispose()
  }
}

function Get-WorkerProcess {
  if (-not (Test-Path $PidFile)) {
    return $null
  }

  $rawPid = (Get-Content -Raw -Path $PidFile -ErrorAction SilentlyContinue).Trim()
  $processId = 0
  if (-not [int]::TryParse($rawPid, [ref]$processId) -or $processId -le 0) {
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    return $null
  }

  $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
  if ($null -eq $process) {
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    return $null
  }

  $commandLine = [string]$process.CommandLine
  if ($commandLine -notmatch 'app\.worker\.celery_app\s+worker' -or $commandLine -notmatch 'android,mobile_special') {
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    return $null
  }

  return $process
}

function Write-Check {
  param(
    [string]$Label,
    [bool]$Passed,
    [string]$Hint = '',
    [bool]$Required = $true
  )

  if ($Passed) {
    Write-Host "[ok]   $Label"
    return 0
  }

  $prefix = if ($Required) { '[fail]' } else { '[warn]' }
  Write-Host "$prefix $Label"
  if (-not [string]::IsNullOrWhiteSpace($Hint)) {
    Write-Host "       $Hint"
  }
  return [int]$Required
}

function Show-Doctor {
  $failed = 0
  $values = Get-DotEnvValues
  $envPath = $ConfiguredEnvFile

  $failed += Write-Check -Label ".env exists: $envPath" -Passed (Test-Path $envPath) -Hint 'Copy .env.example to .env and fill the public PostgreSQL, Redis and MinIO endpoints.'
  $failed += Write-Check -Label "Python virtual environment: $BackendPython" -Passed (Test-Path $BackendPython) -Hint 'Create backend/.venv and install backend/requirements.txt.'

  $adb = Get-Command adb.exe -ErrorAction SilentlyContinue
  $failed += Write-Check -Label 'adb.exe is available' -Passed ($null -ne $adb) -Hint 'Install Android Platform Tools and add its directory to PATH.'
  if ($null -ne $adb) {
    $devicesOutput = (& $adb.Source devices 2>&1 | Out-String)
    $hasDevice = $devicesOutput -match '(?m)^\S+\s+device\s*$'
    $null = Write-Check -Label 'at least one Android device is online' -Passed $hasDevice -Required:$false -Hint 'Connect USB debugging or run adb connect <device-ip>:5555.'
  }

  foreach ($endpoint in @(
      @{ Label = 'PostgreSQL'; HostKey = 'POSTGRES_HOST'; PortKey = 'POSTGRES_PORT'; DefaultPort = 5432 },
      @{ Label = 'Redis'; HostKey = 'REDIS_HOST'; PortKey = 'REDIS_PORT'; DefaultPort = 6379 },
      @{ Label = 'MinIO'; HostKey = 'MINIO_HOST'; PortKey = 'MINIO_PORT'; DefaultPort = 9000 }
    )) {
    $hostName = if ($values.ContainsKey($endpoint.HostKey)) { [string]$values[$endpoint.HostKey] } else { '' }
    $portText = if ($values.ContainsKey($endpoint.PortKey)) { [string]$values[$endpoint.PortKey] } else { [string]$endpoint.DefaultPort }
    $port = 0
    $portParsed = [int]::TryParse($portText, [ref]$port)
    $reachable = $portParsed -and (Test-TcpEndpoint -HostName $hostName -Port $port)
    $failed += Write-Check -Label "$($endpoint.Label) endpoint $hostName`:$port" -Passed $reachable -Hint 'Check the public endpoint, firewall and credentials in .env.'
  }

  if ($failed -eq 0) {
    Write-Host 'Doctor passed. The Windows Worker can consume android,mobile_special.'
  } else {
    Write-Host "Doctor found $failed blocking issue(s)."
  }
  return [int]($failed -gt 0)
}

function Start-AndroidWorker {
  Ensure-RunDir
  if ($null -ne (Get-WorkerProcess)) {
    throw 'Windows Android Worker is already running. Use status or restart.'
  }

  if (-not (Test-Path $BackendPython)) {
    throw "Missing $BackendPython. Run the backend dependency installation first."
  }

  $previousQueues = $env:CELERY_QUEUES
  $previousScan = $env:ADB_SCAN_ENABLED
  try {
    $env:CELERY_QUEUES = $QueueList
    $env:ADB_SCAN_ENABLED = 'true'
    $hostname = "android-win-$($env:COMPUTERNAME)@%h"
    $arguments = @(
      '-m', 'celery', '-A', 'app.worker.celery_app', 'worker',
      '--loglevel=info', '--pool=solo', '--concurrency=1',
      '--hostname', $hostname, '-Q', $QueueList
    )
    $process = Start-Process -FilePath $BackendPython -ArgumentList $arguments -WorkingDirectory $BackendDir `
      -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -WindowStyle Hidden -PassThru
    Set-Content -Path $PidFile -Value "$($process.Id)" -Encoding ascii
    Start-Sleep -Seconds 2
    if ($null -eq (Get-WorkerProcess)) {
      throw "Worker exited during startup. Check $StdoutLog and $StderrLog."
    }
    Write-Host "Windows Android Worker started (PID $($process.Id)); queues: $QueueList"
  } finally {
    if ($null -eq $previousQueues) { Remove-Item Env:CELERY_QUEUES -ErrorAction SilentlyContinue } else { $env:CELERY_QUEUES = $previousQueues }
    if ($null -eq $previousScan) { Remove-Item Env:ADB_SCAN_ENABLED -ErrorAction SilentlyContinue } else { $env:ADB_SCAN_ENABLED = $previousScan }
  }
}

function Stop-AndroidWorker {
  $process = Get-WorkerProcess
  if ($null -eq $process) {
    Write-Host 'Windows Android Worker is not running.'
    return
  }

  Stop-Process -Id $process.ProcessId -Force
  Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
  Write-Host "Windows Android Worker stopped (PID $($process.ProcessId))."
}

function Show-Status {
  $process = Get-WorkerProcess
  if ($null -eq $process) {
    Write-Host 'Windows Android Worker: stopped'
  } else {
    Write-Host "Windows Android Worker: running (PID $($process.ProcessId))"
    Write-Host "Queues: $QueueList"
  }

  $adb = Get-Command adb.exe -ErrorAction SilentlyContinue
  if ($null -eq $adb) {
    Write-Host 'ADB: unavailable'
  } else {
    Write-Host 'ADB devices:'
    & $adb.Source devices
  }
}

function Show-Logs {
  foreach ($path in @($StdoutLog, $StderrLog)) {
    if (-not (Test-Path $path)) {
      Write-Host "No log file: $path"
      continue
    }
    Write-Host "--- $path ---"
    Get-Content -Path $path -Tail $Tail
  }
}

switch ($Action) {
  'up' { Start-AndroidWorker }
  'down' { Stop-AndroidWorker }
  'restart' { Stop-AndroidWorker; Start-AndroidWorker }
  'status' { Show-Status }
  'logs' { Show-Logs }
  'doctor' { exit (Show-Doctor) }
}
