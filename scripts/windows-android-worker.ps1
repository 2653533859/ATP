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
$ProcessEnvironmentHelper = Join-Path $PSScriptRoot 'windows-process-env.ps1'
if (-not (Test-Path -LiteralPath $ProcessEnvironmentHelper)) {
  throw "Missing process environment helper: $ProcessEnvironmentHelper"
}
. $ProcessEnvironmentHelper
Add-AtpOptionalToolPath
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

function Test-PythonModule {
  param([string]$ModuleName)

  if (-not (Test-Path $BackendPython)) {
    return $false
  }

  $previousPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    & $BackendPython -c "import $ModuleName" 2>&1 | Out-Null
    return $LASTEXITCODE -eq 0
  } finally {
    $ErrorActionPreference = $previousPreference
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

function Test-WorkerConsumesAndroidQueue {
  param([string]$CommandLine)

  if ([string]::IsNullOrWhiteSpace($CommandLine)) {
    return $false
  }

  if ($CommandLine -notmatch '(?i)(?:^|\s)(?:-Q|--queues)(?:\s+|=)([^\s]+)') {
    # A Celery worker without an explicit -Q listens to the application default,
    # which is the full queue set in this project and includes Android queues.
    return $true
  }

  foreach ($queue in ($Matches[1].Trim('"') -split ',')) {
    if (@('android', 'mobile_special') -contains $queue.Trim().ToLowerInvariant()) {
      return $true
    }
  }

  return $false
}

function Get-ConflictingLocalWorkerProcesses {
  $processes = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
      $commandLine = [string]$_.CommandLine
      -not [string]::IsNullOrWhiteSpace($commandLine) -and
        $commandLine.IndexOf($BackendPython, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $commandLine -match 'app\.worker\.celery_app\s+worker' -and
        $commandLine -notmatch '--hostname\s+android-win-' -and
        (Test-WorkerConsumesAndroidQueue -CommandLine $commandLine)
    })

  return @($processes | Sort-Object ProcessId -Unique)
}

function Assert-NoLocalWorkerQueueConflict {
  $conflictingWorkers = @(Get-ConflictingLocalWorkerProcesses)
  if ($conflictingWorkers.Count -eq 0) {
    return
  }

  $processIds = ($conflictingWorkers | Select-Object -ExpandProperty ProcessId | Sort-Object -Unique) -join ','
  throw "A local Celery Worker is already running with the android or mobile_special queue (PID $processIds). Stop local-all first, or use a local Worker environment that excludes android,mobile_special before starting android-agent."
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
  $pythonRuntimeReady = (Test-Path $BackendPython) -and (Test-PythonModule -ModuleName 'celery') -and (Test-PythonModule -ModuleName 'redis')
  $failed += Write-Check -Label 'Celery and Redis Python dependencies' -Passed $pythonRuntimeReady -Hint 'Install backend requirements in backend/.venv before starting the Android Worker.'

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
  if (-not (Test-Path $ConfiguredEnvFile)) {
    throw "Missing selected environment file $ConfiguredEnvFile. Run the doctor action first."
  }
  if ((Show-Doctor) -ne 0) {
    throw 'Windows Android Worker prerequisites failed. Fix the doctor errors before starting the Worker.'
  }
  Assert-NoLocalWorkerQueueConflict

  $previousEnvironment = $null
  try {
    $previousEnvironment = Push-AtpProcessEnvironment -Values (Get-DotEnvValues)
    Add-AtpOptionalToolPath
    $env:CELERY_QUEUES = $QueueList
    $env:ADB_SCAN_ENABLED = 'true'
    $env:ANDROID_WORKER_ID = "android-win-$($env:COMPUTERNAME)"
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
    Pop-AtpProcessEnvironment -Previous $previousEnvironment
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
