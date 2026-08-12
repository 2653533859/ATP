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
$PidFile = Join-Path $RunDir 'performance-worker.pid'
$StdoutLog = Join-Path $RunDir 'performance-worker-out.log'
$StderrLog = Join-Path $RunDir 'performance-worker-err.log'
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

function Ensure-RunDir {
  if (-not (Test-Path $RunDir)) {
    New-Item -ItemType Directory -Path $RunDir | Out-Null
  }
}

function Get-DotEnvValues {
  $values = @{}
  if (-not (Test-Path -LiteralPath $ConfiguredEnvFile)) {
    return $values
  }

  foreach ($line in (Get-Content -Path $ConfiguredEnvFile -Encoding UTF8)) {
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

function Get-NodeConfig {
  param([hashtable]$Values)

  $nodeId = if ($Values.ContainsKey('PERFORMANCE_NODE_ID')) { [string]$Values['PERFORMANCE_NODE_ID'] } else { '' }
  $computer = ([string]$env:COMPUTERNAME).ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($nodeId)) {
    $nodeId = "performance-win-$computer"
  }
  $queue = if ($Values.ContainsKey('PERFORMANCE_NODE_QUEUE')) { [string]$Values['PERFORMANCE_NODE_QUEUE'] } else { '' }
  if ([string]::IsNullOrWhiteSpace($queue)) {
    $queue = "performance.$($nodeId.ToLowerInvariant())"
  }

  return @{ NodeId = $nodeId.Trim(); Queue = $queue.Trim() }
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

  if (-not (Test-Path -LiteralPath $BackendPython)) {
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

function Get-WorkerProcess {
  if (-not (Test-Path -LiteralPath $PidFile)) {
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
  if ($commandLine -notmatch 'app\.worker\.celery_app\s+worker' -or $commandLine -notmatch '--hostname\s+performance-win-') {
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    return $null
  }

  return $process
}

function Test-WorkerConsumesQueue {
  param(
    [string]$CommandLine,
    [string]$Queue
  )

  if ([string]::IsNullOrWhiteSpace($CommandLine) -or [string]::IsNullOrWhiteSpace($Queue)) {
    return $false
  }
  if ($CommandLine -notmatch '(?i)(?:^|\s)(?:-Q|--queues)(?:\s+|=)([^\s]+)') {
    return $true
  }

  return @($Matches[1].Trim('"') -split ',' | ForEach-Object { $_.Trim() }) -contains $Queue
}

function Get-ConflictingWorkerProcesses {
  param([string]$Queue)

  $processes = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
      $commandLine = [string]$_.CommandLine
      -not [string]::IsNullOrWhiteSpace($commandLine) -and
        $commandLine.IndexOf($BackendPython, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
        $commandLine -match 'app\.worker\.celery_app\s+worker' -and
        $commandLine -notmatch '--hostname\s+performance-win-' -and
        (Test-WorkerConsumesQueue -CommandLine $commandLine -Queue $Queue)
    })

  return @($processes | Sort-Object ProcessId -Unique)
}

function Assert-NoWorkerQueueConflict {
  param([string]$Queue)

  $conflictingWorkers = @(Get-ConflictingWorkerProcesses -Queue $Queue)
  if ($conflictingWorkers.Count -eq 0) {
    return
  }

  $processIds = ($conflictingWorkers | Select-Object -ExpandProperty ProcessId | Sort-Object -Unique) -join ','
  throw "A local Celery Worker already consumes performance node queue '$Queue' (PID $processIds). Stop local-all first or remove this queue from the other Worker."
}

function Show-Doctor {
  $failed = 0
  $warnings = 0
  $values = Get-DotEnvValues
  $node = Get-NodeConfig -Values $values
  $nodeIdValid = $node.NodeId -match '^[A-Za-z0-9_.-]{1,128}$'
  $queueValid = $node.Queue -match '^[A-Za-z0-9_.-]{1,128}$'

  $failed += Write-Check -Label ".env exists: $ConfiguredEnvFile" -Passed (Test-Path -LiteralPath $ConfiguredEnvFile) -Hint 'Copy config/startup-profiles/performance-agent.env.example and fill the ATP service endpoints.'
  $failed += Write-Check -Label "Python virtual environment: $BackendPython" -Passed (Test-Path -LiteralPath $BackendPython) -Hint 'Create backend/.venv and install backend/requirements.txt.'
  $pythonRuntimeReady = (Test-Path -LiteralPath $BackendPython) -and (Test-PythonModule -ModuleName 'celery') -and (Test-PythonModule -ModuleName 'redis')
  $failed += Write-Check -Label 'Celery and Redis Python dependencies' -Passed $pythonRuntimeReady -Hint 'Install backend requirements in backend/.venv before starting the performance Worker.'
  $failed += Write-Check -Label "Performance node ID: $($node.NodeId)" -Passed $nodeIdValid -Hint 'Use letters, numbers, dots, underscores or hyphens (maximum 128 characters).'
  $failed += Write-Check -Label "Performance node queue: $($node.Queue)" -Passed $queueValid -Hint 'Use letters, numbers, dots, underscores or hyphens (maximum 128 characters).'
  $failed += Write-Check -Label 'Performance node queue is not the shared queue' -Passed ($node.Queue -ne 'performance') -Hint 'Use a dedicated queue such as performance.worker-a so unassigned performance work remains on the shared Worker.'

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
    $failed += Write-Check -Label "$($endpoint.Label) endpoint $hostName`:$port" -Passed $reachable -Hint 'Check the ATP service endpoint, firewall and credentials in the selected environment file.'
  }

  $executors = if ($values.ContainsKey('PERFORMANCE_EXECUTORS')) { [string]$values['PERFORMANCE_EXECUTORS'] -split ',' } else { @('k6') }
  foreach ($executor in $executors) {
    $name = $executor.Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($name)) { continue }
    $available = switch ($name) {
      'k6' { $null -ne (Get-Command k6.exe -ErrorAction SilentlyContinue) }
      'locust' { Test-PythonModule -ModuleName 'locust' }
      'grpc' { (Test-PythonModule -ModuleName 'grpc') -and (Test-PythonModule -ModuleName 'grpc_tools') }
      'jmeter' { ($null -ne (Get-Command java.exe -ErrorAction SilentlyContinue)) -and (($null -ne (Get-Command jmeter.bat -ErrorAction SilentlyContinue)) -or ($null -ne (Get-Command jmeter.exe -ErrorAction SilentlyContinue))) }
      default { $false }
    }
    if (-not $available) { $warnings++ }
    $failed += Write-Check -Label "Performance executor $name" -Passed $available -Required:$false -Hint 'Install this executor or remove it from PERFORMANCE_EXECUTORS before assigning runs to this node.'
  }

  if ($failed -eq 0) {
    Write-Host "Doctor passed with $warnings warning(s). Node '$($node.NodeId)' will consume '$($node.Queue)'."
  } else {
    Write-Host "Doctor found $failed blocking issue(s) and $warnings warning(s)."
  }
  return [int]($failed -gt 0)
}

function Start-PerformanceWorker {
  Ensure-RunDir
  if ($null -ne (Get-WorkerProcess)) {
    throw 'Windows performance Worker is already running. Use status or restart.'
  }
  if ((Show-Doctor) -ne 0) {
    throw 'Windows performance Worker prerequisites failed. Fix the doctor errors before starting the Worker.'
  }

  $values = Get-DotEnvValues
  $node = Get-NodeConfig -Values $values
  Assert-NoWorkerQueueConflict -Queue $node.Queue
  $previousEnvironment = $null
  try {
    $previousEnvironment = Push-AtpProcessEnvironment -Values $values
    Add-AtpOptionalToolPath
    $env:PERFORMANCE_NODE_ENABLED = 'true'
    $env:PERFORMANCE_NODE_ID = $node.NodeId
    $env:PERFORMANCE_NODE_QUEUE = $node.Queue
    $env:CELERY_QUEUES = $node.Queue
    $hostname = "performance-win-$($node.NodeId)@%h"
    $arguments = @(
      '-m', 'celery', '-A', 'app.worker.celery_app', 'worker',
      '--loglevel=info', '--pool=solo', '--concurrency=1',
      '--hostname', $hostname, '-Q', $node.Queue
    )
    $process = Start-Process -FilePath $BackendPython -ArgumentList $arguments -WorkingDirectory $BackendDir `
      -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -WindowStyle Hidden -PassThru
    Set-Content -Path $PidFile -Value "$($process.Id)" -Encoding ascii
    Start-Sleep -Seconds 2
    if ($null -eq (Get-WorkerProcess)) {
      throw "Worker exited during startup. Check $StdoutLog and $StderrLog."
    }
    Write-Host "Windows performance Worker started (PID $($process.Id)); node: $($node.NodeId); queue: $($node.Queue)"
  } finally {
    Pop-AtpProcessEnvironment -Previous $previousEnvironment
  }
}

function Stop-PerformanceWorker {
  $process = Get-WorkerProcess
  if ($null -eq $process) {
    Write-Host 'Windows performance Worker is not running.'
    return
  }

  Stop-Process -Id $process.ProcessId -Force
  Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
  Write-Host "Windows performance Worker stopped (PID $($process.ProcessId))."
}

function Show-Status {
  $values = Get-DotEnvValues
  $node = Get-NodeConfig -Values $values
  $endpoints = "PostgreSQL=$($values['POSTGRES_HOST']):$($values['POSTGRES_PORT']), Redis=$($values['REDIS_HOST']):$($values['REDIS_PORT']), MinIO=$($values['MINIO_HOST']):$($values['MINIO_PORT'])"
  $process = Get-WorkerProcess
  if ($null -eq $process) {
    Write-Host "Windows performance Worker: stopped | node: $($node.NodeId) | queue: $($node.Queue) | $endpoints"
  } else {
    Write-Host "Windows performance Worker: running (PID $($process.ProcessId)) | node: $($node.NodeId) | queue: $($node.Queue) | $endpoints"
  }
}

function Show-Logs {
  foreach ($path in @($StdoutLog, $StderrLog)) {
    if (-not (Test-Path -LiteralPath $path)) {
      Write-Host "No log file: $path"
      continue
    }
    Write-Host "--- $path ---"
    Get-Content -Path $path -Tail $Tail
  }
}

Ensure-RunDir
switch ($Action) {
  'up' { Start-PerformanceWorker }
  'down' { Stop-PerformanceWorker }
  'restart' { Stop-PerformanceWorker; Start-PerformanceWorker }
  'status' { Show-Status }
  'logs' { Show-Logs }
  'doctor' { exit (Show-Doctor) }
}
