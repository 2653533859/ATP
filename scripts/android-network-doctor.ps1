param(
  [string]$Target = '127.0.0.1:5555',
  [switch]$SkipServerRestart,
  [switch]$SkipConnect
)

$ErrorActionPreference = 'Stop'
$failed = 0

function Write-Ok {
  param([string]$Message)
  Write-Host "[OK]   $Message"
}

function Write-Fail {
  param([string]$Message)
  $script:failed++
  Write-Host "[FAIL] $Message"
}

Write-Host '=== ATP Android Network Doctor (PowerShell) ==='
Write-Host "Target: $Target"
Write-Host ''

$adb = Get-Command adb.exe -ErrorAction SilentlyContinue
if ($null -eq $adb) {
  Write-Fail 'adb.exe not found in PATH'
  Write-Host 'Hint: install Android Platform Tools and ensure adb.exe is in PATH'
  exit 1
}
Write-Ok "adb binary found: $($adb.Source)"
$script:AdbPath = $adb.Source

function Invoke-AdbCapture {
  param([string[]]$Arguments)

  $previousPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    $output = (& $script:AdbPath @Arguments 2>$null | Out-String).Trim()
    return [pscustomobject]@{
      Output   = $output
      ExitCode = $LASTEXITCODE
    }
  } finally {
    $ErrorActionPreference = $previousPreference
  }
}

if ($SkipServerRestart) {
  Write-Ok 'adb server restart skipped'
} else {
  $null = Invoke-AdbCapture -Arguments @('kill-server')
  $serverStart = Invoke-AdbCapture -Arguments @('start-server')
  if ($serverStart.ExitCode -eq 0) {
    Write-Ok 'adb server restarted'
  } else {
    Write-Fail 'adb server restart failed'
    Write-Host 'Hint: check adb permissions or other running adb processes'
  }
}

if ($SkipConnect) {
  Write-Ok "connect skipped for existing serial: $Target"
} else {
  $connectResult = Invoke-AdbCapture -Arguments @('connect', $Target)
  if ($connectResult.Output -match '(?i)connected|already connected') {
    Write-Ok "connect $Target"
  } else {
    Write-Fail "connect ${Target}: $($connectResult.Output)"
    Write-Host "Hint: check device IP/port, firewall (5555/tcp), and that 'adb tcpip 5555' ran on device first"
  }
}

$devicesResult = Invoke-AdbCapture -Arguments @('devices')
$devicesOutput = $devicesResult.Output
$escapedTarget = [regex]::Escape($Target)
if ($devicesOutput -match "(?m)^$escapedTarget\s+device\s*$") {
  Write-Ok "device listed: $Target  device"
} elseif ($devicesOutput -match "(?m)^$escapedTarget\s+offline\s*$") {
  Write-Fail 'device offline'
  Write-Host "Hint: try 'adb disconnect $Target' then 'adb connect $Target'; or wake the device screen"
} elseif ($devicesOutput -match "(?m)^$escapedTarget\s+unauthorized\s*$") {
  Write-Fail 'device unauthorized'
  Write-Host "Hint: connect over USB once and tap 'Allow USB debugging' on the device"
} else {
  Write-Fail "device not in 'adb devices' list"
  Write-Host '--- adb devices output ---'
  Write-Host $devicesOutput.TrimEnd()
  Write-Host '--------------------------'
}

$shellResult = Invoke-AdbCapture -Arguments @('-s', $Target, 'shell', 'echo', 'ok')
if ($shellResult.ExitCode -eq 0 -and ($shellResult.Output -replace '\s', '') -eq 'ok') {
  Write-Ok 'shell echo: ok'
} else {
  Write-Fail "shell command failed: $($shellResult.Output)"
}

Write-Host ''
if ($failed -eq 0) {
  Write-Host 'All checks passed.'
  exit 0
}

Write-Host 'One or more checks failed; see hints above.'
exit 1
