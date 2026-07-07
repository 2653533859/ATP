param(
  [ValidateSet('up', 'down', 'restart', 'status', 'logs')]
  [string]$Action = 'up',

  [ValidateRange(20, 500)]
  [int]$Tail = 120
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunDir = Join-Path $RepoRoot '.local-run'
$BackendDir = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$BackendPython = Join-Path $BackendDir '.venv\Scripts\python.exe'
$ViteEntry = Join-Path $FrontendDir 'node_modules\vite\bin\vite.js'
$NodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
$NodeExe = if ($NodeCommand) { $NodeCommand.Source } else { $null }
$Services = @(
  @{
    Key = 'backend'
    Name = 'Backend API'
    MatchTokens = @($BackendPython, '-m', 'uvicorn', 'app.main:app', '--port', '8000')
    FilePath = $BackendPython
    Arguments = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--app-dir', $BackendDir)
    WorkingDirectory = $BackendDir
    Port = 8000
    HealthUrl = 'http://127.0.0.1:8000/health'
  },
  @{
    Key = 'worker'
    Name = 'Celery Worker'
    MatchTokens = @($BackendPython, '-m', 'celery', '-A', 'app.worker.celery_app', 'worker', '--pool=solo')
    MatchPattern = 'app\.worker\.celery_app\s+worker\s+--loglevel=info\s+--pool=solo'
    FilePath = $BackendPython
    Arguments = @('-m', 'celery', '-A', 'app.worker.celery_app', 'worker', '--loglevel=info', '--pool=solo')
    WorkingDirectory = $BackendDir
  },
  @{
    Key = 'beat'
    Name = 'Celery Beat'
    MatchTokens = @($BackendPython, '-m', 'celery', '-A', 'app.worker.celery_app', 'beat')
    MatchPattern = 'app\.worker\.celery_app\s+beat\s+--loglevel=info'
    FilePath = $BackendPython
    Arguments = @('-m', 'celery', '-A', 'app.worker.celery_app', 'beat', '--loglevel=info')
    WorkingDirectory = $BackendDir
  },
  @{
    Key = 'frontend'
    Name = 'Frontend Vite'
    MatchTokens = @($ViteEntry, '--host', '127.0.0.1', '--port', '5173')
    FilePath = $NodeExe
    Arguments = @($ViteEntry, '--host', '127.0.0.1', '--port', '5173')
    WorkingDirectory = $FrontendDir
    Port = 5173
    HealthUrl = 'http://127.0.0.1:5173/login'
  }
)

function Ensure-RunDir {
  if (-not (Test-Path $RunDir)) {
    New-Item -ItemType Directory -Path $RunDir | Out-Null
  }
}

function Get-PidFilePath {
  param([hashtable]$Service)

  Join-Path $RunDir "$($Service.Key).pid"
}

function Remove-PidFile {
  param([hashtable]$Service)

  $pidFile = Get-PidFilePath -Service $Service
  if (Test-Path $pidFile) {
    Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue
  }
}

function Write-PidFile {
  param(
    [hashtable]$Service,
    [int]$ProcessId
  )

  Set-Content -Path (Get-PidFilePath -Service $Service) -Value "$ProcessId" -Encoding ascii
}

function Get-ProcessByIdSafe {
  param([int]$ProcessId)

  if ($ProcessId -le 0) {
    return $null
  }

  Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
}

function Get-LatestLogFile {
  param(
    [hashtable]$Service,
    [ValidateSet('out', 'err')]
    [string]$Stream
  )

  Get-ChildItem -Path $RunDir -Filter "$($Service.Key)-*.$Stream.log" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
}

function Assert-Exists {
  param(
    [string]$Path,
    [string]$Message
  )

  if (-not (Test-Path $Path)) {
    throw $Message
  }
}

function Ensure-Prerequisites {
  Assert-Exists -Path $BackendPython -Message "Missing $BackendPython. Prepare backend/.venv first."
  if (-not $NodeExe) {
    throw 'Missing node.exe. Install Node.js 20+ and ensure it is on PATH.'
  }
  Assert-Exists -Path $ViteEntry -Message "Missing $ViteEntry. Run npm ci in frontend first."
}
function Test-ServiceProcessMatch {
  param(
    [hashtable]$Service,
    $Process
  )

  if ($null -eq $Process) {
    return $false
  }

  $commandLine = [string]$Process.CommandLine
  if ([string]::IsNullOrWhiteSpace($commandLine)) {
    return $false
  }

  foreach ($token in $Service.MatchTokens) {
    if ([string]::IsNullOrWhiteSpace([string]$token)) {
      continue
    }

    if ($commandLine.IndexOf($token, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
      return $false
    }
  }

  if ($Service.ContainsKey('MatchPattern') -and -not [string]::IsNullOrWhiteSpace([string]$Service.MatchPattern)) {
    return [bool]($commandLine -match $Service.MatchPattern)
  }

  return $true
}

function Get-TrackedProcesses {
  param([hashtable]$Service)

  $pidFile = Get-PidFilePath -Service $Service
  if (-not (Test-Path $pidFile)) {
    return @()
  }

  $rawPid = (Get-Content -Raw -Path $pidFile -ErrorAction SilentlyContinue).Trim()
  if ([string]::IsNullOrWhiteSpace($rawPid)) {
    Remove-PidFile -Service $Service
    return @()
  }

  $parsedPid = 0
  if (-not [int]::TryParse($rawPid, [ref]$parsedPid)) {
    Remove-PidFile -Service $Service
    return @()
  }

  $process = Get-ProcessByIdSafe -ProcessId $parsedPid
  if ($null -eq $process) {
    Remove-PidFile -Service $Service
    return @()
  }

  if (-not (Test-ServiceProcessMatch -Service $Service -Process $process)) {
    Remove-PidFile -Service $Service
    return @()
  }

  return @($process)
}

function Get-RepoProcesses {
  param([hashtable]$Service)

  @(Get-CimInstance Win32_Process | Where-Object {
      Test-ServiceProcessMatch -Service $Service -Process $_
    } | Sort-Object ProcessId -Unique)
}

function Get-ListeningProcessId {
  param([int]$Port)

  $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -First 1

  if ($null -eq $connection) {
    return $null
  }

  return $connection.OwningProcess
}

function Test-HttpReady {
  param([string]$Url)

  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
    return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
  } catch {
    return $false
  }
}

function Get-PortOwnedProcess {
  param([hashtable]$Service)

  if (-not $Service.ContainsKey('Port')) {
    return @()
  }

  $owner = Get-ListeningProcessId -Port $Service.Port
  if ($null -eq $owner) {
    return @()
  }

  $process = Get-ProcessByIdSafe -ProcessId $owner
  if ($null -eq $process) {
    return @()
  }

  if (Test-ServiceProcessMatch -Service $Service -Process $process) {
    return @($process)
  }

  if ($Service.ContainsKey('HealthUrl') -and (Test-HttpReady -Url $Service.HealthUrl)) {
    return @($process)
  }

  return @()
}

function Get-ServiceProcesses {
  param([hashtable]$Service)

  $tracked = @(Get-TrackedProcesses -Service $Service)
  if ($tracked.Count -gt 0) {
    return @($tracked | Sort-Object ProcessId -Unique)
  }

  $running = @(Get-RepoProcesses -Service $Service)
  if ($running.Count -gt 0) {
    if ($running.Count -eq 1) {
      Write-PidFile -Service $Service -ProcessId $running[0].ProcessId
    }
    return @($running | Sort-Object ProcessId -Unique)
  }

  $portOwned = @(Get-PortOwnedProcess -Service $Service)
  if ($portOwned.Count -gt 0) {
    if ($portOwned.Count -eq 1 -and (Test-ServiceProcessMatch -Service $Service -Process $portOwned[0])) {
      Write-PidFile -Service $Service -ProcessId $portOwned[0].ProcessId
    }
    return @($portOwned | Sort-Object ProcessId -Unique)
  }

  return @()
}

function Assert-PortAvailable {
  param([hashtable]$Service)

  if (-not $Service.ContainsKey('Port')) {
    return
  }

  $owner = Get-ListeningProcessId -Port $Service.Port
  if ($null -eq $owner) {
    return
  }

  $ownedByRepo = @(Get-PortOwnedProcess -Service $Service | Where-Object { $_.ProcessId -eq $owner })
  if ($ownedByRepo.Count -gt 0) {
    return
  }

  $process = Get-ProcessByIdSafe -ProcessId $owner
  $commandLine = if ($process) { $process.CommandLine } else { '' }
  throw "Port $($Service.Port) is already occupied by PID=$owner. CommandLine: $commandLine"
}
function Wait-HttpReady {
  param(
    [string]$Name,
    [string]$Url,
    [int]$TimeoutSec = 60
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    if (Test-HttpReady -Url $Url) {
      return
    }

    Start-Sleep -Seconds 1
  }

  throw "$Name startup timed out. Check logs under $RunDir."
}

function Wait-ProcessReady {
  param(
    [string]$Name,
    [int]$ProcessId,
    [int]$TimeoutSec = 20
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    $process = Get-ProcessByIdSafe -ProcessId $ProcessId
    if ($null -ne $process) {
      return $process
    }

    Start-Sleep -Seconds 1
  }

  throw "$Name startup timed out. Check logs under $RunDir."
}

function Format-ProcessIds {
  param($Processes)

  (($Processes | Select-Object -ExpandProperty ProcessId | Sort-Object -Unique) -join ',')
}

function Get-ProcessTree {
  param([int[]]$RootProcessIds)

  if ($null -eq $RootProcessIds -or $RootProcessIds.Count -eq 0) {
    return @()
  }

  $allProcesses = @(Get-CimInstance Win32_Process)
  $queue = [System.Collections.Generic.Queue[int]]::new()
  $seen = [System.Collections.Generic.HashSet[int]]::new()

  foreach ($rootId in $RootProcessIds) {
    if ($rootId -gt 0 -and $seen.Add($rootId)) {
      $queue.Enqueue($rootId)
    }
  }

  while ($queue.Count -gt 0) {
    $currentId = $queue.Dequeue()
    foreach ($child in ($allProcesses | Where-Object { $_.ParentProcessId -eq $currentId })) {
      $childId = [int]$child.ProcessId
      if ($seen.Add($childId)) {
        $queue.Enqueue($childId)
      }
    }
  }

  return @($allProcesses | Where-Object { $seen.Contains([int]$_.ProcessId) } | Sort-Object ProcessId -Descending)
}

function Start-ServiceProcess {
  param([hashtable]$Service)

  Write-Host "[start] $($Service.Name)"

  $existing = @(Get-ServiceProcesses -Service $Service)
  if ($existing.Count -gt 0) {
    Write-Host "[skip] $($Service.Name) already running | PID: $(Format-ProcessIds -Processes $existing)"
    return
  }

  Assert-PortAvailable -Service $Service

  $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $stdoutLog = Join-Path $RunDir "$($Service.Key)-$timestamp.out.log"
  $stderrLog = Join-Path $RunDir "$($Service.Key)-$timestamp.err.log"
  $process = $null

  try {
    $process = Start-Process -FilePath $Service.FilePath -ArgumentList $Service.Arguments -WorkingDirectory $Service.WorkingDirectory -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
    Write-PidFile -Service $Service -ProcessId $process.Id

    Start-Sleep -Seconds 2

    if ($Service.ContainsKey('HealthUrl')) {
      Wait-HttpReady -Name $Service.Name -Url $Service.HealthUrl
    } else {
      Wait-ProcessReady -Name $Service.Name -ProcessId $process.Id | Out-Null
    }
  } catch {
    Remove-PidFile -Service $Service
    if ($null -ne $process) {
      try {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
      } catch {
      }
    }
    throw
  }

  $running = @(Get-ServiceProcesses -Service $Service)
  if ($running.Count -eq 0) {
    $running = @(Get-ProcessByIdSafe -ProcessId $process.Id | Where-Object { $null -ne $_ })
  }

  if ($running.Count -eq 0) {
    throw "$($Service.Name) failed to stay alive. Check logs under $RunDir."
  }

  Write-Host "[ok] $($Service.Name) started | PID: $(Format-ProcessIds -Processes $running)"
}

function Stop-ServiceProcess {
  param([hashtable]$Service)

  $running = @(Get-ServiceProcesses -Service $Service)
  if ($running.Count -eq 0) {
    Remove-PidFile -Service $Service
    Write-Host "[skip] $($Service.Name) not running"
    return
  }

  $targets = @(Get-ProcessTree -RootProcessIds ($running | Select-Object -ExpandProperty ProcessId))
  if ($targets.Count -eq 0) {
    $targets = @($running | Sort-Object ProcessId -Descending)
  }

  foreach ($process in ($targets | Sort-Object ProcessId -Descending -Unique)) {
    try {
      Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
      Write-Host "[ok] $($Service.Name) stopped | PID: $($process.ProcessId)"
    } catch {
      Write-Host "[warn] Failed to stop $($Service.Name) PID $($process.ProcessId): $($_.Exception.Message)"
    }
  }

  Start-Sleep -Milliseconds 500
  Remove-PidFile -Service $Service
}

function Show-Status {
  foreach ($service in $Services) {
    $running = @(Get-ServiceProcesses -Service $service)

    if ($running.Count -gt 0) {
      $suffix = if ($service.ContainsKey('HealthUrl')) { " => $($service.HealthUrl)" } else { '' }
      Write-Host "[running] $($service.Name) | PID: $(Format-ProcessIds -Processes $running)$suffix"
      continue
    }

    Write-Host "[stopped] $($service.Name)"
  }
}

function Show-Logs {
  foreach ($service in $Services) {
    $stdoutLog = Get-LatestLogFile -Service $service -Stream out
    $stderrLog = Get-LatestLogFile -Service $service -Stream err

    Write-Host "===== $($service.Name) stdout ====="
    if ($null -ne $stdoutLog) {
      Get-Content $stdoutLog.FullName -Tail $Tail
    } else {
      Write-Host '(no stdout log)'
    }

    Write-Host "===== $($service.Name) stderr ====="
    if ($null -ne $stderrLog) {
      Get-Content $stderrLog.FullName -Tail $Tail
    } else {
      Write-Host '(no stderr log)'
    }
  }
}
Ensure-RunDir

switch ($Action) {
  'up' {
    Ensure-Prerequisites
    foreach ($service in $Services) {
      Start-ServiceProcess -Service $service
    }
    Write-Host ''
    Show-Status
  }
  'down' {
    foreach ($service in @($Services[3], $Services[2], $Services[1], $Services[0])) {
      Stop-ServiceProcess -Service $service
    }
  }
  'restart' {
    foreach ($service in @($Services[3], $Services[2], $Services[1], $Services[0])) {
      Stop-ServiceProcess -Service $service
    }
    Ensure-Prerequisites
    foreach ($service in $Services) {
      Start-ServiceProcess -Service $service
    }
    Write-Host ''
    Show-Status
  }
  'status' {
    Show-Status
  }
  'logs' {
    Show-Logs
  }
}
