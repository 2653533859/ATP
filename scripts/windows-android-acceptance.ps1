[CmdletBinding()]
param(
  [string]$Target = '',
  [string]$AppPackage = '',
  [string]$ReportPath = ''
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunDir = Join-Path $RepoRoot '.local-run'
$ProcessEnvironmentHelper = Join-Path $PSScriptRoot 'windows-process-env.ps1'
if (Test-Path -LiteralPath $ProcessEnvironmentHelper) {
  . $ProcessEnvironmentHelper
  Add-AtpOptionalToolPath
}

if ([string]::IsNullOrWhiteSpace($ReportPath)) {
  $ReportPath = Join-Path $RunDir ("android-acceptance-{0}.json" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
} elseif (-not [System.IO.Path]::IsPathRooted($ReportPath)) {
  $ReportPath = Join-Path $RepoRoot $ReportPath
}

$reportDirectory = Split-Path -Parent $ReportPath
if (-not (Test-Path -LiteralPath $reportDirectory)) {
  New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
}

$checks = [System.Collections.Generic.List[object]]::new()
$device = [ordered]@{}
$deviceStatus = [ordered]@{
  online       = @()
  unauthorized = @()
  offline      = @()
  other        = @()
}
$resolvedTarget = $Target
$adbPath = $null

function Add-Check {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][bool]$Passed,
    [Parameter(Mandatory = $true)][bool]$Required,
    [string]$Detail = ''
  )

  [void]$checks.Add([ordered]@{
      name     = $Name
      passed   = $Passed
      required = $Required
      detail   = $Detail
    })
  $prefix = if ($Passed) { '[ok]  ' } elseif ($Required) { '[fail]' } else { '[warn]' }
  Write-Host "$prefix $Name$(if ($Detail) { ": $Detail" })"
}

function Invoke-Adb {
  param([Parameter(Mandatory = $true)][string[]]$Arguments)

  $output = (& $script:AdbPath @Arguments 2>&1 | Out-String).Trim()
  [pscustomobject]@{
    Output   = $output
    ExitCode = $LASTEXITCODE
  }
}

function Get-OnlineSerials {
  param([Parameter(Mandatory = $true)][string]$Output)

  @(
    $Output -split "`r?`n" |
      Where-Object { $_ -match '^\s*(\S+)\s+device\s*$' } |
      ForEach-Object { $Matches[1] }
  )
}

function Write-Report {
  $requiredFailed = @($checks | Where-Object { $_.required -and -not $_.passed })
  $report = [ordered]@{
    schema_version   = 1
    kind             = 'windows_android_acceptance'
    started_at       = $script:startedAt.ToUniversalTime().ToString('o')
    completed_at     = (Get-Date).ToUniversalTime().ToString('o')
    target           = $resolvedTarget
    adb_path         = $adbPath
    device           = $device
    device_status    = [ordered]@{
      online       = @($deviceStatus.online).Count
      unauthorized = @($deviceStatus.unauthorized).Count
      offline      = @($deviceStatus.offline).Count
      other        = @($deviceStatus.other).Count
    }
    checks           = @($checks)
    required_passed  = $requiredFailed.Count -eq 0
    required_failures = $requiredFailed.Count
  }
  $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
  Write-Host "Report: $ReportPath"
  return ($requiredFailed.Count -eq 0)
}

$script:startedAt = Get-Date
Write-Host '=== ATP Windows Android device acceptance ==='

$adb = Get-Command adb.exe -ErrorAction SilentlyContinue
if ($null -eq $adb) {
  Add-Check -Name 'adb.exe is available' -Passed $false -Required $true -Detail 'Install Android Platform Tools or configure ATP_ADB_HOME/ANDROID_HOME.'
  if (Write-Report) { exit 0 } else { exit 1 }
}

$script:AdbPath = $adb.Source
$adbPath = $adb.Source
$version = Invoke-Adb -Arguments @('version')
Add-Check -Name 'adb command responds' -Passed ($version.ExitCode -eq 0) -Required $true -Detail 'ADB command completed.'

$devicesResult = Invoke-Adb -Arguments @('devices')
$deviceLines = @(
  $devicesResult.Output -split "`r?`n" |
    Where-Object { $_ -match '^\s*\S+\s+(device|unauthorized|offline)\b' }
)
foreach ($line in $deviceLines) {
  if ($line -match '^\s*\S+\s+device\b') {
    $deviceStatus.online += 1
  } elseif ($line -match '^\s*\S+\s+unauthorized\b') {
    $deviceStatus.unauthorized += 1
  } elseif ($line -match '^\s*\S+\s+offline\b') {
    $deviceStatus.offline += 1
  } else {
    $deviceStatus.other += 1
  }
}
$onlineSerials = Get-OnlineSerials -Output $devicesResult.Output
if ([string]::IsNullOrWhiteSpace($resolvedTarget)) {
  if ($onlineSerials.Count -gt 0) {
    $resolvedTarget = $onlineSerials[0]
  }
}

$targetOnline = $onlineSerials -contains $resolvedTarget
$deviceDetail = if ($targetOnline) {
  $resolvedTarget
} elseif (@($deviceStatus.unauthorized).Count -gt 0) {
  'An unauthorized device was detected. Unlock the phone and accept the USB debugging RSA prompt, then rerun adb devices.'
} elseif (@($deviceStatus.offline).Count -gt 0) {
  'An offline device was detected. Reconnect USB or run adb reconnect, then rerun adb devices.'
} else {
  'No authorized device detected. Connect it, authorize USB debugging, or use adb connect <device-ip>:5555.'
}
Add-Check -Name 'an authorized Android device is online' -Passed $targetOnline -Required $true -Detail $deviceDetail

if ($targetOnline) {
  $state = Invoke-Adb -Arguments @('-s', $resolvedTarget, 'get-state')
  Add-Check -Name 'device state is usable' -Passed ($state.ExitCode -eq 0 -and $state.Output.Trim() -eq 'device') -Required $true -Detail 'ADB get-state returned device.'

  $echo = Invoke-Adb -Arguments @('-s', $resolvedTarget, 'shell', 'echo', 'atp-android-acceptance')
  Add-Check -Name 'ADB shell command executes' -Passed ($echo.ExitCode -eq 0 -and $echo.Output.Trim() -eq 'atp-android-acceptance') -Required $true -Detail 'ADB shell echo completed.'

  foreach ($property in @(
      @{ Key = 'model'; Command = 'ro.product.model' },
      @{ Key = 'android_version'; Command = 'ro.build.version.release' },
      @{ Key = 'sdk'; Command = 'ro.build.version.sdk' },
      @{ Key = 'abi'; Command = 'ro.product.cpu.abi' }
    )) {
    $propertyResult = Invoke-Adb -Arguments @('-s', $resolvedTarget, 'shell', 'getprop', $property.Command)
    $device[$property.Key] = $propertyResult.Output.Trim()
  }
  Add-Check -Name 'device properties are readable' -Passed ($device.model -and $device.android_version -and $device.sdk) -Required $true -Detail 'Model, Android version and SDK were read.'

  $packages = Invoke-Adb -Arguments @('-s', $resolvedTarget, 'shell', 'pm', 'list', 'packages')
  $packageLines = @($packages.Output -split "`r?`n" | Where-Object { $_ -match '^package:' })
  Add-Check -Name 'package manager is readable' -Passed ($packages.ExitCode -eq 0) -Required $true -Detail ("{0} packages reported." -f $packageLines.Count)

  $logcat = Invoke-Adb -Arguments @('-s', $resolvedTarget, 'logcat', '-d', '-t', '20')
  $logLines = @($logcat.Output -split "`r?`n" | Where-Object { $_.Trim() })
  Add-Check -Name 'device logcat is readable' -Passed ($logcat.ExitCode -eq 0) -Required $false -Detail ("{0} recent lines readable; log content is not stored in the report." -f $logLines.Count)

  if (-not [string]::IsNullOrWhiteSpace($AppPackage)) {
    $packagePath = Invoke-Adb -Arguments @('-s', $resolvedTarget, 'shell', 'pm', 'path', $AppPackage)
    Add-Check -Name "application package is installed: $AppPackage" -Passed ($packagePath.ExitCode -eq 0 -and $packagePath.Output -match '^package:') -Required $true -Detail 'The requested package is installed.'
  }
}

$result = Write-Report
if ($result) {
  Write-Host 'Android device acceptance passed.'
  exit 0
}

Write-Host 'Android device acceptance failed. Fix required checks and rerun the command.'
exit 1
