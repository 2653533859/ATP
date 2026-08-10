param(
  [switch]$StartServices,
  [switch]$SkipPlaywright,
  [switch]$SkipBrowserMatrix,
  [switch]$RequireAndroid,
  [string]$AndroidTarget = '',
  [switch]$SkipLiveLogin,
  [switch]$SkipFileTransfer,
  [switch]$SkipReports,
  [switch]$StopServicesAfter,
  [string]$ReportPath = ''
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendHealthUrl = 'http://127.0.0.1:8000/health'
$FrontendLoginUrl = 'http://127.0.0.1:5173/login'
$LiveLoginUrl = 'http://127.0.0.1:8000/api/v1/auth/login'
$LiveApiBaseUrl = 'http://127.0.0.1:8000/api/v1'
$LocalDev = Join-Path $RepoRoot 'local-dev.cmd'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$NpmCommand = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if ([string]::IsNullOrWhiteSpace($NpmCommand)) {
  $NpmCommand = 'npm'
}

if ([string]::IsNullOrWhiteSpace($ReportPath)) {
  $ReportPath = Join-Path (Join-Path $RepoRoot '.local-run') ("windows-smoke-{0}.json" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
} elseif (-not [System.IO.Path]::IsPathRooted($ReportPath)) {
  $ReportPath = Join-Path $RepoRoot $ReportPath
}
$ReportDirectory = Split-Path -Parent $ReportPath

$results = [System.Collections.Generic.List[object]]::new()
$script:LiveAccessToken = $null
$script:LiveProjectId = $null

function Redact-Output {
  param([string]$Text)

  if ([string]::IsNullOrWhiteSpace($Text)) {
    return ''
  }

  return $Text -replace '(?i)(password|passwd|token|secret|api[_-]?key|authorization|cookie)\s*[:=]\s*[^\s,;]+', '$1=<redacted>'
}

function Add-Result {
  param(
    [string]$Name,
    [ValidateSet('passed', 'failed', 'warning', 'skipped')]
    [string]$Status,
    [bool]$Required,
    [string]$Details = ''
  )

  $safeDetails = Redact-Output -Text $Details
  $results.Add([pscustomobject]@{
      name      = $Name
      status    = $Status
      required  = $Required
      details   = $safeDetails
      timestamp = (Get-Date).ToUniversalTime().ToString('o')
    })

  $prefix = switch ($Status) {
    'passed' { '[ok]   ' }
    'failed' { '[fail] ' }
    'warning' { '[warn] ' }
    default { '[skip] ' }
  }
  Write-Host "$prefix$Name"
  if (-not [string]::IsNullOrWhiteSpace($safeDetails)) {
    Write-Host "       $safeDetails"
  }
}

function Invoke-NativeCapture {
  param(
    [string]$FilePath,
    [string[]]$Arguments,
    [string]$WorkingDirectory
  )

  $previousPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    Push-Location $WorkingDirectory
    try {
      $output = (& $FilePath @Arguments 2>&1 | Out-String).Trim()
      return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output   = $output
      }
    } finally {
      Pop-Location
    }
  } finally {
    $ErrorActionPreference = $previousPreference
  }
}

function Get-DotEnvValues {
  $values = @{}
  $envPath = Join-Path $RepoRoot '.env'
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

function Invoke-HttpCheck {
  param(
    [string]$Name,
    [string]$Uri,
    [int[]]$ExpectedStatusCodes = @(200)
  )

  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 10
    $passed = $ExpectedStatusCodes -contains [int]$response.StatusCode
    $status = if ($passed) { 'passed' } else { 'failed' }
    Add-Result -Name $Name -Status $status -Required:$true -Details "HTTP $($response.StatusCode)"
    return $passed
  } catch {
    Add-Result -Name $Name -Status 'failed' -Required:$true -Details $_.Exception.Message
    return $false
  }
}

function Invoke-LiveLogin {
  param([hashtable]$Values)

  $username = if (-not [string]::IsNullOrWhiteSpace($env:ATP_USERNAME)) { $env:ATP_USERNAME } elseif ($Values.ContainsKey('FIRST_ADMIN_USERNAME')) { [string]$Values['FIRST_ADMIN_USERNAME'] } else { '' }
  $password = if (-not [string]::IsNullOrWhiteSpace($env:ATP_PASSWORD)) { $env:ATP_PASSWORD } elseif ($Values.ContainsKey('FIRST_ADMIN_PASSWORD')) { [string]$Values['FIRST_ADMIN_PASSWORD'] } else { '' }
  if ([string]::IsNullOrWhiteSpace($username) -or [string]::IsNullOrWhiteSpace($password)) {
    Add-Result -Name 'Live API admin login' -Status 'failed' -Required:$true -Details 'FIRST_ADMIN_USERNAME/FIRST_ADMIN_PASSWORD or ATP_USERNAME/ATP_PASSWORD is missing.'
    return $false
  }

  try {
    $payload = @{ username = $username; password = $password } | ConvertTo-Json -Compress
    $response = Invoke-RestMethod -Method Post -Uri $LiveLoginUrl -ContentType 'application/json' -Body $payload -TimeoutSec 10
    $script:LiveAccessToken = [string]$response.access_token
    $passed = -not [string]::IsNullOrWhiteSpace($script:LiveAccessToken)
    Add-Result -Name 'Live API admin login' -Status $(if ($passed) { 'passed' } else { 'failed' }) -Required:$true -Details $(if ($passed) { 'access token returned; value hidden' } else { 'response did not contain access_token' })
    return $passed
  } catch {
    Add-Result -Name 'Live API admin login' -Status 'failed' -Required:$true -Details $_.Exception.Message
    return $false
  }
}

function Invoke-LiveApiChecks {
  if ([string]::IsNullOrWhiteSpace($script:LiveAccessToken)) {
    Add-Result -Name 'Live API authenticated read checks' -Status 'skipped' -Required:$false -Details 'Skipped because live login did not return an access token.'
    return
  }

  $headers = @{ Authorization = "Bearer $script:LiveAccessToken" }
  $checks = @(
    @{ Name = 'Live API current user'; Path = '/auth/me'; Validator = { param($body) $null -ne $body.id -and -not [string]::IsNullOrWhiteSpace([string]$body.username) } },
    @{ Name = 'Live API project list'; Path = '/projects'; Validator = { param($body) $null -ne $body } }
  )

  foreach ($check in $checks) {
    try {
      $body = Invoke-RestMethod -Method Get -Uri ($LiveApiBaseUrl + $check.Path) -Headers $headers -TimeoutSec 10
      $passed = & $check.Validator $body
      if ($check.Path -eq '/projects' -and $passed) {
        $project = @($body | Where-Object { $null -ne $_.id } | Select-Object -First 1)
        if ($project.Count -gt 0) {
          $script:LiveProjectId = [int]$project[0].id
        }
      }
      Add-Result -Name $check.Name -Status $(if ($passed) { 'passed' } else { 'failed' }) -Required:$true -Details $(if ($passed) { 'authenticated read response valid' } else { 'authenticated response shape invalid' })
    } catch {
      Add-Result -Name $check.Name -Status 'failed' -Required:$true -Details $_.Exception.Message
    }
  }
}

function Invoke-FileTransferCheck {
  if ($SkipFileTransfer) {
    Add-Result -Name 'Web file upload and cleanup' -Status 'skipped' -Required:$false -Details 'Skipped by -SkipFileTransfer.'
    return
  }
  if ([string]::IsNullOrWhiteSpace($script:LiveAccessToken) -or $null -eq $script:LiveProjectId) {
    Add-Result -Name 'Web file upload and cleanup' -Status 'skipped' -Required:$false -Details 'Skipped because an authenticated project is unavailable.'
    return
  }

  $objectName = $null
  $client = $null
  $multipart = $null
  $fileContent = $null
  $response = $null
  $uploadPassed = $false
  try {
    Add-Type -AssemblyName System.Net.Http -ErrorAction Stop
    $client = [System.Net.Http.HttpClient]::new()
    $multipart = [System.Net.Http.MultipartFormDataContent]::new()
    $payload = [System.Text.Encoding]::UTF8.GetBytes("ATP Windows smoke $([DateTime]::UtcNow.ToString('o'))`n")
    $fileContent = [System.Net.Http.ByteArrayContent]::new($payload)
    $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('text/plain')
    $multipart.Add($fileContent, 'file', 'atp-windows-smoke.txt')

    $uri = "$LiveApiBaseUrl/projects/$($script:LiveProjectId)/web-files"
    $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Post, $uri)
    $request.Headers.Authorization = [System.Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $script:LiveAccessToken)
    $request.Content = $multipart
    $response = $client.SendAsync($request).GetAwaiter().GetResult()
    $responseBody = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    if (-not $response.IsSuccessStatusCode) {
      throw "upload returned HTTP $([int]$response.StatusCode)"
    }
    $upload = $responseBody | ConvertFrom-Json
    $objectName = [string]$upload.object_name
    $uploadPassed = -not [string]::IsNullOrWhiteSpace($objectName) -and [int]$upload.size -gt 0
    Add-Result -Name 'Web file upload' -Status $(if ($uploadPassed) { 'passed' } else { 'failed' }) -Required:$true -Details $(if ($uploadPassed) { "uploaded $([int]$upload.size) bytes" } else { 'upload response is incomplete' })
  } catch {
    Add-Result -Name 'Web file upload' -Status 'failed' -Required:$true -Details $_.Exception.Message
  } finally {
    if ($response) { $response.Dispose() }
    if ($multipart) { $multipart.Dispose() }
    if ($fileContent) { $fileContent.Dispose() }
    if ($client) { $client.Dispose() }
  }

  if ([string]::IsNullOrWhiteSpace($objectName)) {
    return
  }

  try {
    $headers = @{ Authorization = "Bearer $script:LiveAccessToken" }
    $cleanupPayload = @{ object_names = @($objectName); repair_orphan_references = $false } | ConvertTo-Json -Compress
    $cleanup = Invoke-RestMethod -Method Post -Uri "$LiveApiBaseUrl/storage/cleanup-execute" -Headers $headers -ContentType 'application/json' -Body $cleanupPayload -TimeoutSec 20
    $deleted = @($cleanup.deleted_objects) -contains $objectName
    Add-Result -Name 'Web file cleanup' -Status $(if ($deleted) { 'passed' } else { 'failed' }) -Required:$true -Details $(if ($deleted) { 'temporary smoke object deleted' } else { 'temporary smoke object was not deleted' })
  } catch {
    Add-Result -Name 'Web file cleanup' -Status 'failed' -Required:$true -Details $_.Exception.Message
  }
}

function Invoke-ReportChecks {
  if ($SkipReports) {
    Add-Result -Name 'Run report export' -Status 'skipped' -Required:$false -Details 'Skipped by -SkipReports.'
    return
  }
  if ([string]::IsNullOrWhiteSpace($script:LiveAccessToken)) {
    Add-Result -Name 'Run report export' -Status 'skipped' -Required:$false -Details 'Skipped because live login did not return an access token.'
    return
  }

  try {
    $headers = @{ Authorization = "Bearer $script:LiveAccessToken" }
    $runs = Invoke-RestMethod -Method Get -Uri "$LiveApiBaseUrl/runs?page=1&page_size=20" -Headers $headers -TimeoutSec 20
    $run = @($runs.items | Where-Object { $null -ne $_.id } | Select-Object -First 1)
    if ($run.Count -eq 0) {
      Add-Result -Name 'Run report export' -Status 'failed' -Required:$true -Details 'No historical run is available; report export was not exercised.'
      return
    }

    if (-not (Test-Path $ReportDirectory)) {
      New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null
    }
    $runId = [int]$run[0].id
    $formats = @(
      @{ Name = 'HTML'; Path = "runs/$runId/export/html"; File = "run-$runId-report.html" },
      @{ Name = 'JUnit XML'; Path = "runs/$runId/junit"; File = "run-$runId-junit.xml" }
    )
    foreach ($format in $formats) {
      $artifactPath = Join-Path $ReportDirectory $format.File
      $download = Invoke-WebRequest -UseBasicParsing -Uri "$LiveApiBaseUrl/$($format.Path)" -Headers $headers -TimeoutSec 30
      [System.IO.File]::WriteAllText($artifactPath, [string]$download.Content, [System.Text.UTF8Encoding]::new($false))
      $size = (Get-Item -LiteralPath $artifactPath).Length
      $passed = [int]$download.StatusCode -eq 200 -and $size -gt 0
      Add-Result -Name "Run report $($format.Name)" -Status $(if ($passed) { 'passed' } else { 'failed' }) -Required:$true -Details $(if ($passed) { "run $runId, $size bytes" } else { "run $runId returned an empty artifact" })
    }
  } catch {
    Add-Result -Name 'Run report export' -Status 'failed' -Required:$true -Details $_.Exception.Message
  }
}

function Invoke-PlaywrightChecks {
  if ($SkipPlaywright) {
    Add-Result -Name 'Playwright mock E2E suite' -Status 'skipped' -Required:$false -Details 'Skipped by -SkipPlaywright.'
    return
  }

  $result = Invoke-NativeCapture -FilePath $NpmCommand -Arguments @('run', 'e2e', '--', '--reporter=line') -WorkingDirectory $FrontendDir
  $status = if ($result.ExitCode -eq 0) { 'passed' } else { 'failed' }
  Add-Result -Name 'Playwright mock E2E suite' -Status $status -Required:$true -Details (Redact-Output -Text (($result.Output -split "`r?`n" | Select-Object -Last 12) -join "`n"))
}

function Invoke-BrowserMatrixCheck {
  if ($SkipBrowserMatrix) {
    Add-Result -Name 'Playwright browser matrix login page' -Status 'skipped' -Required:$false -Details 'Skipped by -SkipBrowserMatrix.'
    return
  }

  $result = Invoke-NativeCapture -FilePath $NpmCommand -Arguments @('run', 'e2e:browser-matrix') -WorkingDirectory $FrontendDir
  $status = if ($result.ExitCode -eq 0) { 'passed' } else { 'failed' }
  Add-Result -Name 'Playwright browser matrix login page' -Status $status -Required:$true -Details (Redact-Output -Text (($result.Output -split "`r?`n" | Select-Object -Last 16) -join "`n"))
}

function Invoke-AndroidCheck {
  if ([string]::IsNullOrWhiteSpace($AndroidTarget) -and -not $RequireAndroid) {
    Add-Result -Name 'Android network doctor' -Status 'skipped' -Required:$false -Details 'Android is optional for Windows API/Web smoke.'
    return
  }

  $target = if ([string]::IsNullOrWhiteSpace($AndroidTarget)) { '127.0.0.1:5555' } else { $AndroidTarget }
  $androidScript = Join-Path $PSScriptRoot 'android-network-doctor.ps1'
  $result = Invoke-NativeCapture -FilePath 'powershell.exe' -Arguments @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $androidScript, '-Target', $target, '-SkipServerRestart') -WorkingDirectory $RepoRoot
  $status = if ($result.ExitCode -eq 0) { 'passed' } else { 'failed' }
  Add-Result -Name 'Android network doctor' -Status $status -Required:$RequireAndroid -Details (Redact-Output -Text (($result.Output -split "`r?`n" | Select-Object -Last 12) -join "`n"))
}

Write-Host '=== ATP Windows Local Smoke ==='
Write-Host "Repo: $RepoRoot"
Write-Host ''

if ($StartServices) {
  $start = Invoke-NativeCapture -FilePath $LocalDev -Arguments @('up') -WorkingDirectory $RepoRoot
  if ($start.ExitCode -ne 0) {
    Add-Result -Name 'Windows local services start' -Status 'failed' -Required:$true -Details $start.Output
  } else {
    Add-Result -Name 'Windows local services start' -Status 'passed' -Required:$true -Details 'local-dev.cmd up completed.'
  }
}

$doctor = Invoke-NativeCapture -FilePath $LocalDev -Arguments @('doctor') -WorkingDirectory $RepoRoot
$doctorStatus = if ($doctor.ExitCode -eq 0) { 'passed' } else { 'failed' }
Add-Result -Name 'Windows local doctor' -Status $doctorStatus -Required:$true -Details (($doctor.Output -split "`r?`n" | Select-Object -Last 20) -join "`n")

$values = Get-DotEnvValues
$healthReady = Invoke-HttpCheck -Name 'Backend health' -Uri $BackendHealthUrl
$frontendReady = Invoke-HttpCheck -Name 'Frontend login page' -Uri $FrontendLoginUrl

if ($SkipLiveLogin) {
  Add-Result -Name 'Live API admin login' -Status 'skipped' -Required:$false -Details 'Skipped by -SkipLiveLogin.'
  Add-Result -Name 'Live API authenticated read checks' -Status 'skipped' -Required:$false -Details 'Skipped because live login was disabled.'
} else {
  $loginPassed = Invoke-LiveLogin -Values $values
  if ($loginPassed) {
    Invoke-LiveApiChecks
  } else {
    Add-Result -Name 'Live API authenticated read checks' -Status 'skipped' -Required:$false -Details 'Skipped because live login failed.'
  }
}

if ($healthReady -and $frontendReady) {
  Invoke-PlaywrightChecks
  Invoke-BrowserMatrixCheck
} else {
  Add-Result -Name 'Playwright mock E2E suite' -Status 'skipped' -Required:$false -Details 'Skipped because backend/frontend health checks failed.'
  Add-Result -Name 'Playwright browser matrix login page' -Status 'skipped' -Required:$false -Details 'Skipped because backend/frontend health checks failed.'
}

Invoke-FileTransferCheck
Invoke-ReportChecks
Invoke-AndroidCheck

if ($StopServicesAfter) {
  $stop = Invoke-NativeCapture -FilePath $LocalDev -Arguments @('down') -WorkingDirectory $RepoRoot
  if ($stop.ExitCode -ne 0) {
    Add-Result -Name 'Windows local services stop' -Status 'failed' -Required:$true -Details $stop.Output
  } else {
    Add-Result -Name 'Windows local services stop' -Status 'passed' -Required:$true -Details 'local-dev.cmd down completed.'
  }
}

if (-not (Test-Path $ReportDirectory)) {
  New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null
}

$requiredFailures = @($results | Where-Object { $_.required -and $_.status -eq 'failed' }).Count
$report = [pscustomobject]@{
  generated_at = (Get-Date).ToUniversalTime().ToString('o')
  repo_root    = $RepoRoot
  required_failures = $requiredFailures
  results      = @($results)
}
$report | ConvertTo-Json -Depth 6 | Set-Content -Path $ReportPath -Encoding UTF8
Write-Host "Report: $ReportPath"

if ($requiredFailures -gt 0) {
  Write-Host "Smoke failed: $requiredFailures required check(s) failed."
  exit 1
}

Write-Host 'Smoke passed; optional checks may still be skipped or warning-only.'
exit 0
