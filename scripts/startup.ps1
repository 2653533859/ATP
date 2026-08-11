[CmdletBinding()]
param(
  [ValidateSet('up', 'down', 'restart', 'status', 'logs', 'doctor')]
  [string]$Action = 'up',

  [string]$Profile = '',

  [string]$ConfigFile = ''
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ProfileRoot = Join-Path $RepoRoot 'config\startup-profiles'
$ProfileDefinitions = @{
  'local-all' = @{
    Label = 'Windows local full stack (Backend/Worker/Beat/Frontend)'
    Config = (Join-Path $ProfileRoot 'local-all.env')
    Example = (Join-Path $ProfileRoot 'local-all.env.example')
    Script = (Join-Path $RepoRoot 'scripts\windows-local.ps1')
  }
  'remote-infra' = @{
    Label = 'Windows full stack with remote PostgreSQL/Redis/MinIO'
    Config = (Join-Path $ProfileRoot 'remote-infra.env')
    Example = (Join-Path $ProfileRoot 'remote-infra.env.example')
    Script = (Join-Path $RepoRoot 'scripts\windows-local.ps1')
  }
  'android-agent' = @{
    Label = 'Windows Android Agent (local ADB, remote ATP services)'
    Config = (Join-Path $ProfileRoot 'android-agent.env')
    Example = (Join-Path $ProfileRoot 'android-agent.env.example')
    Script = (Join-Path $RepoRoot 'scripts\windows-android-worker.ps1')
  }
}

function Select-Profile {
  if (-not [string]::IsNullOrWhiteSpace($Profile)) {
    if (-not $ProfileDefinitions.ContainsKey($Profile)) {
      throw "Unknown startup profile '$Profile'. Available profiles: $($ProfileDefinitions.Keys -join ', ')"
    }
    return $Profile
  }

  Write-Host 'Select startup profile:'
  $index = 1
  $choices = @{}
  foreach ($key in @('local-all', 'remote-infra', 'android-agent')) {
    $choices[[string]$index] = $key
    Write-Host "  [$index] $($ProfileDefinitions[$key].Label)"
    $index++
  }

  $selected = Read-Host 'Enter number'
  if (-not $choices.ContainsKey($selected)) {
    throw "Invalid profile selection '$selected'."
  }
  return $choices[$selected]
}

function Resolve-ProfileConfig {
  param([string]$SelectedProfile)

  if (-not [string]::IsNullOrWhiteSpace($ConfigFile)) {
    $path = if ([System.IO.Path]::IsPathRooted($ConfigFile)) {
      $ConfigFile
    } else {
      Join-Path $RepoRoot $ConfigFile
    }
    if (-not (Test-Path $path)) {
      throw "Config file not found: $path"
    }
    return (Resolve-Path $path).Path
  }

  $definition = $ProfileDefinitions[$SelectedProfile]
  if (Test-Path $definition.Config) {
    return (Resolve-Path $definition.Config).Path
  }

  throw "Missing config file: $($definition.Config). Copy the template first: Copy-Item '$($definition.Example)' '$($definition.Config)'"
}

function Import-ProfileEnvironment {
  param([string]$Path)

  $previous = @{}
  foreach ($line in (Get-Content -Path $Path -Encoding UTF8)) {
    if ($line -notmatch '^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
      continue
    }

    $key = $Matches[1]
    $value = $Matches[2]
    if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
      $value = $value.Substring(1, $value.Length - 2)
    }

    if (-not $previous.ContainsKey($key)) {
      $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
    }
    [Environment]::SetEnvironmentVariable($key, $value, 'Process')
  }

  return $previous
}

function Restore-ProfileEnvironment {
  param([hashtable]$Previous)

  foreach ($entry in $Previous.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
  }
}

$selected = Select-Profile
$definition = $ProfileDefinitions[$selected]
$requiresConfig = $Action -in @('up', 'restart', 'doctor')
$profileConfig = $null
$previousEnvironment = @{}
$exitCode = 0

try {
  if ($requiresConfig) {
    $profileConfig = Resolve-ProfileConfig -SelectedProfile $selected
    $previousEnvironment = Import-ProfileEnvironment -Path $profileConfig
    if (-not $previousEnvironment.ContainsKey('ATP_STARTUP_PROFILE')) {
      $previousEnvironment['ATP_STARTUP_PROFILE'] = [Environment]::GetEnvironmentVariable('ATP_STARTUP_PROFILE', 'Process')
    }
    [Environment]::SetEnvironmentVariable('ATP_STARTUP_PROFILE', $selected, 'Process')
    Write-Host "Profile: $selected"
    Write-Host "Config:  $profileConfig"
  } elseif (-not [string]::IsNullOrWhiteSpace($ConfigFile) -or (Test-Path $definition.Config)) {
    $profileConfig = Resolve-ProfileConfig -SelectedProfile $selected
    $previousEnvironment = Import-ProfileEnvironment -Path $profileConfig
  }

  if (-not [string]::IsNullOrWhiteSpace($profileConfig)) {
    & $definition.Script -Action $Action -EnvFile $profileConfig
  } else {
    & $definition.Script -Action $Action
  }
  if ($null -ne $LASTEXITCODE) {
    $exitCode = [int]$LASTEXITCODE
  }
} finally {
  Restore-ProfileEnvironment -Previous $previousEnvironment
}

exit $exitCode
