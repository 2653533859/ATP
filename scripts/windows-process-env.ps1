# Helpers for temporarily applying a selected .env file to a child process.
# The caller restores the returned snapshot immediately after Start-Process;
# the child has already inherited the selected values at that point.

function Add-AtpOptionalToolPath {
  <#
    Make per-user tools installed by the Windows runbook visible to this
    PowerShell process and all child Workers without modifying the machine PATH.
    ADB is resolved from ATP_ADB_HOME, Android SDK variables, and the common
    per-user SDK location so Android checks do not require a machine PATH edit.
  #>
  $candidateExecutables = @()
  $configuredK6Home = [Environment]::GetEnvironmentVariable('ATP_K6_HOME', 'Process')
  if ([string]::IsNullOrWhiteSpace($configuredK6Home)) {
    $configuredK6Home = [Environment]::GetEnvironmentVariable('ATP_K6_HOME', 'User')
  }
  if (-not [string]::IsNullOrWhiteSpace($configuredK6Home)) {
    $candidateExecutables += [pscustomobject]@{ Directory = $configuredK6Home; Name = 'k6.exe' }
  }

  $localApplicationData = [Environment]::GetFolderPath('LocalApplicationData')
  if (-not [string]::IsNullOrWhiteSpace($localApplicationData)) {
    $candidateExecutables += [pscustomobject]@{
      Directory = (Join-Path $localApplicationData 'ATP\tools\k6')
      Name = 'k6.exe'
    }
  }

  $configuredAdbHome = [Environment]::GetEnvironmentVariable('ATP_ADB_HOME', 'Process')
  if ([string]::IsNullOrWhiteSpace($configuredAdbHome)) {
    $configuredAdbHome = [Environment]::GetEnvironmentVariable('ATP_ADB_HOME', 'User')
  }
  if (-not [string]::IsNullOrWhiteSpace($configuredAdbHome)) {
    $candidateExecutables += [pscustomobject]@{ Directory = $configuredAdbHome; Name = 'adb.exe' }
    $candidateExecutables += [pscustomobject]@{
      Directory = (Join-Path $configuredAdbHome 'platform-tools')
      Name = 'adb.exe'
    }
  }

  foreach ($sdkVariable in @('ANDROID_HOME', 'ANDROID_SDK_ROOT')) {
    $sdkRoot = [Environment]::GetEnvironmentVariable($sdkVariable, 'Process')
    if ([string]::IsNullOrWhiteSpace($sdkRoot)) {
      $sdkRoot = [Environment]::GetEnvironmentVariable($sdkVariable, 'User')
    }
    if (-not [string]::IsNullOrWhiteSpace($sdkRoot)) {
      $candidateExecutables += [pscustomobject]@{
        Directory = (Join-Path $sdkRoot 'platform-tools')
        Name = 'adb.exe'
      }
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($localApplicationData)) {
    $candidateExecutables += [pscustomobject]@{
      Directory = (Join-Path $localApplicationData 'Android\Sdk\platform-tools')
      Name = 'adb.exe'
    }
    $candidateExecutables += [pscustomobject]@{
      Directory = (Join-Path $localApplicationData 'ATP\tools\platform-tools')
      Name = 'adb.exe'
    }
  }

  $pathEntries = @(
    if (-not [string]::IsNullOrWhiteSpace($env:Path)) { $env:Path -split ';' }
  )
  foreach ($candidate in $candidateExecutables) {
    $directory = [string]$candidate.Directory
    if ([string]::IsNullOrWhiteSpace($directory)) { continue }
    $executable = Join-Path $directory ([string]$candidate.Name)
    if (-not (Test-Path -LiteralPath $executable)) { continue }
    if ($pathEntries -notcontains $directory) {
      $pathEntries = @($directory) + $pathEntries
    }
  }

  $env:Path = ($pathEntries -join ';')
}

function Push-AtpProcessEnvironment {
  param([hashtable]$Values)

  $previous = @{}
  if ($null -eq $Values) {
    return $previous
  }

  foreach ($entry in $Values.GetEnumerator()) {
    $key = [string]$entry.Key
    if ([string]::IsNullOrWhiteSpace($key) -or $key -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
      continue
    }

    $exists = Test-Path -LiteralPath "Env:$key"
    $previous[$key] = [pscustomobject]@{
      Exists = $exists
      Value  = if ($exists) { [Environment]::GetEnvironmentVariable($key, 'Process') } else { $null }
    }
    [Environment]::SetEnvironmentVariable($key, [string]$entry.Value, 'Process')
  }

  return $previous
}

function Pop-AtpProcessEnvironment {
  param([hashtable]$Previous)

  if ($null -eq $Previous) {
    return
  }

  foreach ($entry in $Previous.GetEnumerator()) {
    $state = $entry.Value
    if ($state.Exists) {
      [Environment]::SetEnvironmentVariable($entry.Key, [string]$state.Value, 'Process')
    } else {
      [Environment]::SetEnvironmentVariable($entry.Key, $null, 'Process')
    }
  }
}
