[CmdletBinding()]
param(
  [ValidateSet('up', 'down', 'restart', 'status', 'logs', 'doctor')]
  [string]$Action = 'up',

  [ValidateRange(20, 500)]
  [int]$Tail = 120,

  [ValidateRange(1024, 65535)]
  [int]$Port = 9090
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LocalApplicationData = [Environment]::GetFolderPath('LocalApplicationData')
$PrometheusHome = Join-Path $LocalApplicationData 'ATP\tools\prometheus'
$PrometheusExe = Join-Path $PrometheusHome 'prometheus.exe'
$ConfigFile = Join-Path $RepoRoot 'config\prometheus\windows-local.yml'
$DataDir = Join-Path $PrometheusHome 'data'
$RunDir = Join-Path $RepoRoot '.local-run'
$PidFile = Join-Path $RunDir 'prometheus.pid'
$StdoutLog = Join-Path $RunDir 'prometheus-out.log'
$StderrLog = Join-Path $RunDir 'prometheus-err.log'

function Ensure-Directory {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
  }
}

function Get-PrometheusProcess {
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
  if ($commandLine -notmatch '(?i)prometheus(?:\.exe)?' -or $commandLine -notmatch '(?i)--config\.file=') {
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    return $null
  }

  return $process
}

function Test-HttpReady {
  try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/-/ready" -UseBasicParsing -TimeoutSec 2
    return $response.StatusCode -eq 200
  } catch {
    return $false
  }
}

function Write-Check {
  param(
    [string]$Label,
    [bool]$Passed,
    [string]$Hint = ''
  )

  if ($Passed) {
    Write-Host "[ok]   $Label"
    return 0
  }

  Write-Host "[fail] $Label"
  if (-not [string]::IsNullOrWhiteSpace($Hint)) {
    Write-Host "       $Hint"
  }
  return 1
}

function Show-Doctor {
  $failed = 0
  $failed += Write-Check -Label "Prometheus binary: $PrometheusExe" `
    -Passed (Test-Path -LiteralPath $PrometheusExe) `
    -Hint 'Install the official Windows amd64 archive into %LOCALAPPDATA%\ATP\tools\prometheus.'
  $failed += Write-Check -Label "Prometheus config: $ConfigFile" `
    -Passed (Test-Path -LiteralPath $ConfigFile) `
    -Hint 'Restore config/prometheus/windows-local.yml from the repository.'

  $backendMetricsReady = $false
  try {
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/metrics' -UseBasicParsing -TimeoutSec 2
    $backendMetricsReady = $response.StatusCode -eq 200 -and $response.Content -match '^[#\w]'
  } catch {
    $backendMetricsReady = $false
  }
  $failed += Write-Check -Label 'ATP Backend /metrics: http://127.0.0.1:8000/metrics' `
    -Passed $backendMetricsReady `
    -Hint 'Start the Backend before starting Windows Prometheus.'

  $process = Get-PrometheusProcess
  if ($null -ne $process) {
    $failed += Write-Check -Label "Prometheus ready: http://127.0.0.1:$Port/-/ready" `
      -Passed (Test-HttpReady) `
      -Hint 'Inspect .local-run/prometheus-err.log for startup or port errors.'
  }

  if ($failed -eq 0) {
    Write-Host "Doctor passed. Prometheus will scrape ATP Backend on 127.0.0.1:8000 and listen on 127.0.0.1:$Port."
  } else {
    Write-Host "Doctor found $failed blocking issue(s)."
  }
  return [int]($failed -gt 0)
}

function Start-Prometheus {
  Ensure-Directory -Path $RunDir
  Ensure-Directory -Path $DataDir
  if ($null -ne (Get-PrometheusProcess)) {
    throw "Windows Prometheus is already running. Use status or restart."
  }
  if (-not (Test-Path -LiteralPath $PrometheusExe)) {
    throw "Prometheus binary not found: $PrometheusExe"
  }
  if (-not (Test-Path -LiteralPath $ConfigFile)) {
    throw "Prometheus config not found: $ConfigFile"
  }

  $arguments = @(
    ('--config.file="{0}"' -f $ConfigFile),
    ('--storage.tsdb.path="{0}"' -f $DataDir),
    "--web.listen-address=127.0.0.1:$Port"
  )
  $process = Start-Process -FilePath $PrometheusExe -ArgumentList $arguments -WorkingDirectory $PrometheusHome `
    -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -WindowStyle Hidden -PassThru
  Set-Content -Path $PidFile -Value "$($process.Id)" -Encoding ascii

  $ready = $false
  for ($attempt = 0; $attempt -lt 15; $attempt++) {
    Start-Sleep -Milliseconds 500
    if ($null -eq (Get-PrometheusProcess)) {
      throw "Prometheus exited during startup. Check $StderrLog."
    }
    if (Test-HttpReady) {
      $ready = $true
      break
    }
  }
  if (-not $ready) {
    throw "Prometheus process started but did not become ready. Check $StderrLog."
  }
  Write-Host "Windows Prometheus started (PID $($process.Id)); URL: http://127.0.0.1:$Port"
}

function Stop-Prometheus {
  $process = Get-PrometheusProcess
  if ($null -eq $process) {
    Write-Host 'Windows Prometheus is not running.'
    return
  }

  Stop-Process -Id $process.ProcessId -Force
  Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
  Write-Host "Windows Prometheus stopped (PID $($process.ProcessId))."
}

function Show-Status {
  $process = Get-PrometheusProcess
  if ($null -eq $process) {
    Write-Host "Windows Prometheus: stopped | URL: http://127.0.0.1:$Port | scrape: http://127.0.0.1:8000/metrics"
    return
  }

  $ready = if (Test-HttpReady) { 'ready' } else { 'starting/unready' }
  Write-Host "Windows Prometheus: running (PID $($process.ProcessId), $ready) | URL: http://127.0.0.1:$Port | scrape: http://127.0.0.1:8000/metrics"
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

Ensure-Directory -Path $RunDir
switch ($Action) {
  'up' { Start-Prometheus }
  'down' { Stop-Prometheus }
  'restart' { Stop-Prometheus; Start-Prometheus }
  'status' { Show-Status }
  'logs' { Show-Logs }
  'doctor' { exit (Show-Doctor) }
}
