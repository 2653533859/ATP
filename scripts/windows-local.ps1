param(
  [ValidateSet('up', 'down', 'restart', 'status', 'logs', 'doctor')]
  [string]$Action = 'up',

  [ValidateRange(20, 500)]
  [int]$Tail = 120,

  [string]$EnvFile = ''
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunDir = Join-Path $RepoRoot '.local-run'
$BackendDir = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$BackendPython = Join-Path $BackendDir '.venv\Scripts\python.exe'
$ConfiguredEnvFile = if ([string]::IsNullOrWhiteSpace($EnvFile)) {
  Join-Path $RepoRoot '.env'
} elseif ([System.IO.Path]::IsPathRooted($EnvFile)) {
  $EnvFile
} else {
  Join-Path $RepoRoot $EnvFile
}
$ViteEntry = Join-Path $FrontendDir 'node_modules\vite\bin\vite.js'
$PlaywrightPackage = Join-Path $FrontendDir 'node_modules\@playwright\test'
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
    MatchPattern = 'app\.worker\.celery_app\s+worker\s+--loglevel=info(?:\s+-Q\s+\S+)?\s+--pool=solo'
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

function Test-PlaceholderValue {
  param([string]$Value)

  return [string]::IsNullOrWhiteSpace($Value) -or $Value -match '(?i)change[_-]?me|password[_-]?change[_-]?me|Admin@123456'
}

function Get-ConfiguredExecutors {
  param([hashtable]$Values)

  $raw = if ($Values.ContainsKey('PERFORMANCE_EXECUTORS')) { $Values['PERFORMANCE_EXECUTORS'] } else { '' }
  return @($raw -split ',' | ForEach-Object { $_.Trim().ToLowerInvariant() } | Where-Object { $_ })
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

function Show-DoctorCheck {
  param(
    [string]$Label,
    [bool]$Passed,
    [bool]$Required = $true,
    [string]$Hint = ''
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
  $warnings = 0
  $values = Get-DotEnvValues
  $envPath = $ConfiguredEnvFile

  $result = Show-DoctorCheck -Label ".env exists: $envPath" -Passed (Test-Path $envPath) -Hint 'Run Copy-Item .env.example .env and fill private values.'
  $failed += $result
  if (-not (Test-Path $envPath)) {
    Write-Host '[fail] doctor stopped because .env is missing.'
    return 1
  }

  $result = Show-DoctorCheck -Label 'Python virtual environment' -Passed (Test-Path $BackendPython) -Hint 'Create backend/.venv and install backend requirements.'
  $failed += $result
  $result = Show-DoctorCheck -Label 'Node.js 20+, Vite and Playwright packages' -Passed (($null -ne $NodeExe) -and (Test-Path $ViteEntry) -and (Test-Path $PlaywrightPackage)) -Hint 'Install Node.js 20+ and run npm ci in frontend.'
  $failed += $result

  foreach ($key in @('APP_SECRET_KEY', 'POSTGRES_PASSWORD', 'MINIO_ROOT_PASSWORD', 'FIRST_ADMIN_PASSWORD')) {
    $value = if ($values.ContainsKey($key)) { [string]$values[$key] } else { '' }
    $placeholder = Test-PlaceholderValue -Value $value
    if ($placeholder) {
      Write-Host "[warn] $key is empty or still uses a template value"
      $warnings++
    } else {
      Write-Host "[ok]   $key is configured (value hidden)"
    }
  }

  foreach ($service in $Services) {
    if (-not $service.ContainsKey('Port')) {
      continue
    }
    $listener = Get-ListeningProcessId -Port $service.Port
    $managed = @(Get-ServiceProcesses -Service $service)
    $managedIds = @()
    if ($managed.Count -gt 0) {
      $managedIds = @(Get-ProcessTree -RootProcessIds @($managed | Select-Object -ExpandProperty ProcessId) | Select-Object -ExpandProperty ProcessId)
    }
    $managedPort = @($managedIds | Where-Object { [int]$_ -eq [int]$listener })
    $portReady = ($null -eq $listener) -or ($managedPort.Count -gt 0)
    $result = Show-DoctorCheck -Label "port $($service.Port) for $($service.Name)" -Passed $portReady -Hint "Stop the process listening on $($service.Port), or use the managed local-dev process."
    $failed += $result
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
    $reachable = $portParsed -and -not [string]::IsNullOrWhiteSpace($hostName) -and (Test-TcpEndpoint -HostName $hostName -Port $port)
    $result = Show-DoctorCheck -Label "$($endpoint.Label) endpoint $hostName`:$port" -Passed $reachable -Hint 'Check .env host/port, firewall rules, and the remote service status.'
    $failed += $result
  }

  $adb = Get-Command adb.exe -ErrorAction SilentlyContinue
  $adbAvailable = $null -ne $adb
  if (-not $adbAvailable) {
    $warnings++
  }
  $result = Show-DoctorCheck -Label 'ADB executable' -Passed $adbAvailable -Required:$false -Hint 'Install Android Platform Tools when Android testing is needed.'
  if ($adbAvailable) {
    $deviceOutput = (& $adb.Source devices 2>&1 | Out-String)
    $hasDevice = $deviceOutput -match '(?m)^\S+\s+device\s*$'
    if (-not $hasDevice) {
      $warnings++
    }
    $result = Show-DoctorCheck -Label 'Android device online' -Passed $hasDevice -Required:$false -Hint 'Connect a device or use adb connect <device-ip>:5555; Web/API development does not require an Android device.'
  }

  $executors = Get-ConfiguredExecutors -Values $values
  foreach ($executor in $executors) {
    switch ($executor) {
      'k6' {
        $available = $null -ne (Get-Command k6.exe -ErrorAction SilentlyContinue)
        if (-not $available) {
          $warnings++
        }
        $result = Show-DoctorCheck -Label 'Performance executor k6' -Passed $available -Required:$false -Hint 'Install the Windows k6 binary or remove k6 from PERFORMANCE_EXECUTORS for this machine.'
      }
      'locust' {
        $available = Test-PythonModule -ModuleName 'locust'
        if (-not $available) {
          $warnings++
        }
        $result = Show-DoctorCheck -Label 'Performance executor Locust' -Passed $available -Required:$false -Hint 'Install backend requirements in backend/.venv.'
      }
      'grpc' {
        $available = (Test-PythonModule -ModuleName 'grpc') -and (Test-PythonModule -ModuleName 'grpc_tools')
        if (-not $available) {
          $warnings++
        }
        $result = Show-DoctorCheck -Label 'Performance executor gRPC' -Passed $available -Required:$false -Hint 'Install grpcio and grpcio-tools in backend/.venv.'
      }
      'jmeter' {
        $javaAvailable = $null -ne (Get-Command java.exe -ErrorAction SilentlyContinue)
        $jmeterAvailable = $null -ne (Get-Command jmeter.bat -ErrorAction SilentlyContinue) -or $null -ne (Get-Command jmeter.exe -ErrorAction SilentlyContinue)
        if (-not ($javaAvailable -and $jmeterAvailable)) {
          $warnings++
        }
        $result = Show-DoctorCheck -Label 'Performance executor JMeter' -Passed ($javaAvailable -and $jmeterAvailable) -Required:$false -Hint 'Install Java and JMeter 5.6.3, then add JMeter bin to PATH.'
      }
      default {
        Write-Host "[warn] Unknown PERFORMANCE_EXECUTORS entry: $executor"
        $warnings++
      }
    }
  }

  if ($failed -eq 0) {
    Write-Host "Doctor passed with $warnings warning(s)."
    return 0
  }

  Write-Host "Doctor found $failed blocking issue(s) and $warnings warning(s)."
  return 1
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

function Configure-WorkerQueues {
  $values = Get-DotEnvValues
  $rawQueues = if ($values.ContainsKey('CELERY_QUEUES')) { [string]$values['CELERY_QUEUES'] } else { '' }
  $queues = @(
    $rawQueues -split ',' |
      ForEach-Object { $_.Trim() } |
      Where-Object { $_ -match '^[A-Za-z0-9_-]+$' } |
      Select-Object -Unique
  )

  if ($queues.Count -eq 0) {
    $queues = @('default')
  }

  $worker = $Services | Where-Object { $_.Key -eq 'worker' } | Select-Object -First 1
  $worker.Arguments = @(
    '-m', 'celery', '-A', 'app.worker.celery_app', 'worker', '--loglevel=info',
    '-Q', ($queues -join ','), '--pool=solo'
  )
  Write-Host "Worker queues: $($queues -join ',')"
}

Ensure-RunDir

switch ($Action) {
  'up' {
    Ensure-Prerequisites
    Configure-WorkerQueues
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
    Configure-WorkerQueues
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
  'doctor' {
    exit (Show-Doctor)
  }
}
