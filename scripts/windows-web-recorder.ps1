<#
.SYNOPSIS
  Windows 本地 Web 录制 Worker 管理脚本（本地弹窗录制，连接云端/远端 Redis）。

.DESCRIPTION
  启动本地 `python -m app.web_recording_worker` 进程，将当前 Windows 电脑注册为
  带桌面显示环境的 Web 录制 Worker。用户在平台点击录制时，真实 Chromium 窗口
  将直接在当前电脑屏幕弹出供人工交互录制，录制步骤实时同步至服务端，用例执行仍由远端集群承担。

.PARAMETER Action
  up, down, restart, status, logs, doctor
#>
[CmdletBinding()]
param(
  [ValidateSet('up', 'down', 'restart', 'status', 'logs', 'doctor')]
  [string]$Action = 'up',

  [string]$EnvFile = '.local-run\android-worker-196.env',

  [int]$Tail = 50
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot 'backend'
$BackendPython = Join-Path $BackendDir '.venv\Scripts\python.exe'
$RunDir = Join-Path $RepoRoot '.local-run'
$PidFile = Join-Path $RunDir 'web-recorder.pid'
$StdoutLog = Join-Path $RunDir 'web-recorder-out.log'
$StderrLog = Join-Path $RunDir 'web-recorder-err.log'

$ConfiguredEnvFile = if ([System.IO.Path]::IsPathRooted($EnvFile)) {
  $EnvFile
} else {
  Join-Path $RepoRoot $EnvFile
}

$ProcessEnvHelper = Join-Path $PSScriptRoot 'windows-process-env.ps1'
if (Test-Path $ProcessEnvHelper) {
  . $ProcessEnvHelper
  Add-AtpOptionalToolPath
}

function Ensure-RunDir {
  if (-not (Test-Path $RunDir)) {
    New-Item -ItemType Directory -Path $RunDir | Out-Null
  }
}

function Get-DotEnvValues {
  $values = @{}
  if (-not (Test-Path $ConfiguredEnvFile)) {
    return $values
  }
  foreach ($line in (Get-Content -Path $ConfiguredEnvFile -Encoding UTF8)) {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
      $key = $Matches[1]
      $value = $Matches[2]
      if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
        $value = $value.Substring(1, $value.Length - 2)
      }
      if ($key -in @('PATH', 'HOME') -and $value.StartsWith('/')) {
        continue
      }
      $values[$key] = $value
    }
  }
  return $values
}

function Get-WorkerProcess {
  if (-not (Test-Path $PidFile)) {
    return $null
  }
  $rawPid = (Get-Content -Raw -Path $PidFile -ErrorAction SilentlyContinue).Trim()
  $procId = 0
  if (-not [int]::TryParse($rawPid, [ref]$procId) -or $procId -le 0) {
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    return $null
  }
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
  if ($null -eq $proc) {
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    return $null
  }
  if ([string]$proc.CommandLine -notmatch 'web_recording_worker') {
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    return $null
  }
  return $proc
}

function Show-Doctor {
  Write-Host "=== Web Recorder Doctor ==="
  $ok = $true
  if (Test-Path $BackendPython) {
    Write-Host "[ok]   Python: $BackendPython"
  } else {
    Write-Host "[fail] Python not found: $BackendPython"
    $ok = $false
  }
  if (Test-Path $ConfiguredEnvFile) {
    Write-Host "[ok]   Env file: $ConfiguredEnvFile"
  } else {
    Write-Host "[fail] Env file not found: $ConfiguredEnvFile"
    $ok = $false
  }

  $prevEap = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  $pwCheck = & $BackendPython -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); print(p.chromium.executable_path); p.stop()" 2>&1
  $ErrorActionPreference = $prevEap
  if ($LASTEXITCODE -eq 0 -and $pwCheck) {
    Write-Host "[ok]   Playwright Chromium available: $pwCheck"
  } else {
    Write-Host "[fail] Playwright Chromium not found. Run: python -m playwright install chromium"
    $ok = $false
  }
  return [int](-not $ok)
}

function Start-Worker {
  Ensure-RunDir
  $existing = Get-WorkerProcess
  if ($null -ne $existing) {
    Write-Host "Local Web Recording Worker is already running (PID $($existing.ProcessId))."
    return
  }

  if ((Show-Doctor) -ne 0) {
    throw "Prerequisites check failed."
  }

  $prevEnv = $null
  try {
    $prevEnv = Push-AtpProcessEnvironment -Values (Get-DotEnvValues)
    $workerHost = ($env:COMPUTERNAME -replace '[^a-zA-Z0-9._-]', '-').Trim('-')
    if ([string]::IsNullOrWhiteSpace($workerHost)) { $workerHost = 'win' }
    $workerId = "web-win-$workerHost"
    $env:WEB_RECORDER_WORKER_ID = $workerId
    $env:WEB_RECORDER_MODE = 'worker'

    $arguments = @('-m', 'app.web_recording_worker')
    $proc = Start-Process -FilePath $BackendPython -ArgumentList $arguments -WorkingDirectory $BackendDir `
      -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -WindowStyle Hidden -PassThru
    Set-Content -Path $PidFile -Value "$($proc.Id)" -Encoding ascii
    Start-Sleep -Seconds 2

    $check = Get-WorkerProcess
    if ($null -eq $check) {
      throw "Worker process exited immediately. Check logs: $StderrLog"
    }
    Write-Host "Local Web Recording Worker started (PID $($proc.Id), worker_id=$workerId)."
    Write-Host "Web recording sessions will now launch visible Chromium on this desktop!"
  } finally {
    Pop-AtpProcessEnvironment -Previous $prevEnv
  }
}

function Stop-Worker {
  $proc = Get-WorkerProcess
  if ($null -eq $proc) {
    Write-Host "Local Web Recording Worker is not running."
    return
  }
  Stop-Process -Id $proc.ProcessId -Force
  Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
  Write-Host "Local Web Recording Worker stopped (PID $($proc.ProcessId))."
}

function Show-Status {
  $proc = Get-WorkerProcess
  if ($null -eq $proc) {
    Write-Host "Local Web Recording Worker: stopped"
  } else {
    Write-Host "Local Web Recording Worker: running (PID $($proc.ProcessId))"
  }

  $prevEnv = $null
  try {
    $prevEnv = Push-AtpProcessEnvironment -Values (Get-DotEnvValues)
    Push-Location $BackendDir
    & $BackendPython -c "import asyncio; from app.services.web_recording_transport import list_recording_workers; print('Registered Workers in Redis:', asyncio.run(list_recording_workers()))"
    Pop-Location
  } catch {
    Write-Host "Failed to query Redis for workers: $_"
  } finally {
    Pop-AtpProcessEnvironment -Previous $prevEnv
  }
}

function Show-Logs {
  foreach ($log in @($StdoutLog, $StderrLog)) {
    if (Test-Path $log) {
      Write-Host "=== $log ==="
      Get-Content -Path $log -Tail $Tail
    }
  }
}

switch ($Action) {
  'up' { Start-Worker }
  'down' { Stop-Worker }
  'restart' { Stop-Worker; Start-Worker }
  'status' { Show-Status }
  'logs' { Show-Logs }
  'doctor' { exit (Show-Doctor) }
}
