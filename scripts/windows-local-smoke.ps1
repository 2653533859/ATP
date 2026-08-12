param(
  [switch]$StartServices,
  [string]$EnvFile = '',
  [switch]$SkipPlaywright,
  [switch]$SkipBrowserMatrix,
  [switch]$RequireAndroid,
  [string]$AndroidTarget = '',
  [switch]$SkipLiveLogin,
  [switch]$SkipFileTransfer,
  [switch]$SkipReports,
  [int]$WebCaseId = 0,
  [switch]$SeedWebDownloadCase,
  [switch]$RequireWebLowcode,
  [switch]$RequireWebDownload,
  [int]$WebRunTimeoutSeconds = 120,
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
$DefaultEnvFile = Join-Path $RepoRoot '.env'
$RuntimeMetadataPath = Join-Path $RepoRoot '.local-run\windows-local-runtime.json'
$ConfiguredEnvFile = $DefaultEnvFile
if (-not [string]::IsNullOrWhiteSpace($EnvFile)) {
  $ConfiguredEnvFile = if ([System.IO.Path]::IsPathRooted($EnvFile)) {
    $EnvFile
  } else {
    Join-Path $RepoRoot $EnvFile
  }
} elseif (Test-Path -LiteralPath $RuntimeMetadataPath) {
  try {
    $runtime = Get-Content -Raw -Encoding UTF8 -LiteralPath $RuntimeMetadataPath | ConvertFrom-Json
    $runtimeEnvFile = [string]$runtime.env_file
    if (-not [string]::IsNullOrWhiteSpace($runtimeEnvFile)) {
      $runtimeCandidates = if ([System.IO.Path]::IsPathRooted($runtimeEnvFile)) {
        @($runtimeEnvFile)
      } else {
        @(
          (Join-Path $RepoRoot $runtimeEnvFile),
          (Join-Path (Join-Path $RepoRoot 'config\startup-profiles') $runtimeEnvFile)
        )
      }
      $runtimeConfig = $runtimeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
      if ($runtimeConfig) {
        $ConfiguredEnvFile = (Resolve-Path -LiteralPath $runtimeConfig).Path
      }
    }
  } catch {
    # A stale or malformed runtime metadata file must not prevent the smoke script
    # from falling back to the documented root .env behavior.
  }
}
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
$script:LiveAccessToken = $null # compatibility marker; browser/API smoke uses the cookie session
$script:LiveWebSession = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$script:LiveCookieHeader = $null
$script:LiveProjectId = $null
$script:ResolvedWebCaseId = $WebCaseId
$script:LiveMutationHeaders = @{ 'X-Requested-With' = 'XMLHttpRequest' }
$script:SeededWebProjectId = $null
$script:SeededWebRunId = $null
$script:SeededWebRunFinished = $false
$script:SeededWebObjectNames = [System.Collections.Generic.List[string]]::new()

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
    $response = Invoke-RestMethod -Method Post -Uri $LiveLoginUrl -Headers @{ 'X-Requested-With' = 'XMLHttpRequest' } -ContentType 'application/json' -Body $payload -WebSession $script:LiveWebSession -TimeoutSec 10
    $sessionCookies = $script:LiveWebSession.Cookies.GetCookies([Uri]$LiveLoginUrl)
    $accessCookie = @($sessionCookies | Where-Object { $_.Name -eq 'atp_access_token' } | Select-Object -First 1)[0]
    $refreshCookie = @($sessionCookies | Where-Object { $_.Name -eq 'atp_refresh_token' } | Select-Object -First 1)[0]
    if ($accessCookie) {
      $script:LiveCookieHeader = "atp_access_token=$($accessCookie.Value)"
      if ($refreshCookie) { $script:LiveCookieHeader += "; atp_refresh_token=$($refreshCookie.Value)" }
    }
    $script:LiveAccessToken = if ($response.authenticated -and $accessCookie) { 'cookie-session' } else { $null }
    $passed = -not [string]::IsNullOrWhiteSpace($script:LiveAccessToken)
    Add-Result -Name 'Live API admin login' -Status $(if ($passed) { 'passed' } else { 'failed' }) -Required:$true -Details $(if ($passed) { 'HttpOnly cookie session established' } else { 'login response did not establish an access cookie' })
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

  $checks = @(
    @{ Name = 'Live API current user'; Path = '/auth/me'; Validator = { param($body) $null -ne $body.id -and -not [string]::IsNullOrWhiteSpace([string]$body.username) } },
    @{ Name = 'Live API project list'; Path = '/projects'; Validator = { param($body) $null -ne $body } }
  )

  foreach ($check in $checks) {
    try {
      $body = Invoke-RestMethod -Method Get -Uri ($LiveApiBaseUrl + $check.Path) -WebSession $script:LiveWebSession -TimeoutSec 10
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
  $handler = $null
  $multipart = $null
  $fileContent = $null
  $request = $null
  $response = $null
  $uploadPassed = $false
  try {
    Add-Type -AssemblyName System.Net.Http -ErrorAction Stop
    $uri = "$LiveApiBaseUrl/projects/$($script:LiveProjectId)/web-files"
    $targetUri = [Uri]$uri
    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.CookieContainer = [System.Net.CookieContainer]::new()
    foreach ($cookie in $script:LiveWebSession.Cookies.GetCookies($targetUri)) {
      $handler.CookieContainer.Add($targetUri, $cookie)
    }
    $client = [System.Net.Http.HttpClient]::new($handler)
    $multipart = [System.Net.Http.MultipartFormDataContent]::new()
    $payload = [System.Text.Encoding]::UTF8.GetBytes("ATP Windows smoke $([DateTime]::UtcNow.ToString('o'))`n")
    $fileContent = [System.Net.Http.ByteArrayContent]::new($payload)
    $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('text/plain')
    $multipart.Add($fileContent, 'file', 'atp-windows-smoke.txt')

    $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Post, $targetUri)
    $request.Headers.Add('X-Requested-With', 'XMLHttpRequest')
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
    if ($request) { $request.Dispose() }
    if ($multipart) { $multipart.Dispose() }
    if ($fileContent) { $fileContent.Dispose() }
    if ($client) { $client.Dispose() }
    if ($handler) { $handler.Dispose() }
  }

  if ([string]::IsNullOrWhiteSpace($objectName)) {
    return
  }

  try {
    $cleanupPayload = @{ object_names = @($objectName); repair_orphan_references = $false } | ConvertTo-Json -Compress
    $cleanup = Invoke-RestMethod -Method Post -Uri "$LiveApiBaseUrl/storage/cleanup-execute" -Headers $script:LiveMutationHeaders -WebSession $script:LiveWebSession -ContentType 'application/json' -Body $cleanupPayload -TimeoutSec 20
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
    $runs = Invoke-RestMethod -Method Get -Uri "$LiveApiBaseUrl/runs?page=1&page_size=20" -WebSession $script:LiveWebSession -TimeoutSec 20
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
      $download = Invoke-WebRequest -UseBasicParsing -Uri "$LiveApiBaseUrl/$($format.Path)" -WebSession $script:LiveWebSession -TimeoutSec 30
      [System.IO.File]::WriteAllText($artifactPath, [string]$download.Content, [System.Text.UTF8Encoding]::new($false))
      $size = (Get-Item -LiteralPath $artifactPath).Length
      $passed = [int]$download.StatusCode -eq 200 -and $size -gt 0
      Add-Result -Name "Run report $($format.Name)" -Status $(if ($passed) { 'passed' } else { 'failed' }) -Required:$true -Details $(if ($passed) { "run $runId, $size bytes" } else { "run $runId returned an empty artifact" })
    }
  } catch {
    Add-Result -Name 'Run report export' -Status 'failed' -Required:$true -Details $_.Exception.Message
  }
}

function Invoke-SeedWebDownloadCase {
  if (-not $SeedWebDownloadCase) {
    return
  }
  if ($WebCaseId -gt 0) {
    Add-Result -Name 'Seed Web download case' -Status 'failed' -Required:$true -Details 'Do not combine -SeedWebDownloadCase with -WebCaseId.'
    return
  }
  if ([string]::IsNullOrWhiteSpace($script:LiveAccessToken)) {
    Add-Result -Name 'Seed Web download case' -Status 'failed' -Required:$true -Details 'Cannot seed a temporary Web case without an authenticated session.'
    return
  }

  try {
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss')
    $projectPayload = @{
      name        = "ATP Windows smoke fixture $stamp"
      description = 'Temporary project created by the Windows Web download smoke check.'
      template    = 'web'
    } | ConvertTo-Json -Compress
    $project = Invoke-RestMethod -Method Post -Uri "$LiveApiBaseUrl/projects" -Headers $script:LiveMutationHeaders -WebSession $script:LiveWebSession -ContentType 'application/json' -Body $projectPayload -TimeoutSec 20
    $projectId = [int]$project.id
    if ($projectId -le 0) {
      throw 'Temporary Web smoke project did not return a valid project ID.'
    }
    $script:SeededWebProjectId = $projectId

    # Windows PowerShell can collapse a top-level JSON array into one object whose
    # properties are arrays. Parse the response body explicitly so module[0].id
    # remains a scalar module ID.
    $moduleResponse = Invoke-WebRequest -UseBasicParsing -Method Get -Uri "$LiveApiBaseUrl/projects/$projectId/modules" -WebSession $script:LiveWebSession -TimeoutSec 20
    $modules = ConvertFrom-Json -InputObject $moduleResponse.Content
    $module = @($modules | Where-Object { $null -ne $_.id } | Select-Object -First 1)
    if ($module.Count -eq 0) {
      throw "Temporary Web smoke project $projectId has no module."
    }
    $moduleId = [int]$module[0].id
    # The browser network guard intentionally blocks loopback/private HTTP URLs.
    # Use an inline data page for the self-seeded case; manual cases may still
    # use the repository HTTP fixture documented below.
    $fixtureUrl = 'data:text/html,<a id="atp-download-link" download="atp-windows-smoke.txt" href="data:text/plain,ATP%20Windows%20smoke%20fixture">Download</a>'
    $lowcodeSteps = @(
      @{
        action = 'goto'
        name   = 'Open Windows download fixture'
        params = @{ url = $fixtureUrl }
      },
      @{
        action = 'download'
        name   = 'Download Windows smoke file'
        params = @{ selector = '#atp-download-link' }
      }
    )
    $casePayload = @{
      name               = 'Windows smoke download fixture'
      description        = 'Temporary Web low-code case for the Windows download evidence check.'
      case_type          = 'web'
      module_id          = $moduleId
      priority           = 'P1'
      case_level         = 'smoke'
      automation_status  = 'auto'
      steps              = @(
        @{
          step_no         = 1
          action          = 'Open Windows download fixture'
          test_data       = $fixtureUrl
          expected_result = 'The local fixture page is displayed.'
          is_key_step     = $true
        },
        @{
          step_no         = 2
          action          = 'Download Windows smoke file'
          test_data       = '#atp-download-link'
          expected_result = 'A download object is returned.'
          is_key_step     = $true
        }
      )
      config             = @{
        browser  = 'chromium'
        headless = $true
        timeout  = 30
        steps    = $lowcodeSteps
      }
    } | ConvertTo-Json -Depth 10 -Compress
    $case = Invoke-RestMethod -Method Post -Uri "$LiveApiBaseUrl/cases" -Headers $script:LiveMutationHeaders -WebSession $script:LiveWebSession -ContentType 'application/json' -Body $casePayload -TimeoutSec 20
    $caseId = [int]$case.id
    if ($caseId -le 0) {
      throw 'Temporary Web smoke case did not return a valid case ID.'
    }
    $workflowBody = @{} | ConvertTo-Json -Compress
    Invoke-RestMethod -Method Post -Uri "$LiveApiBaseUrl/cases/$caseId/submit-review" -Headers $script:LiveMutationHeaders -WebSession $script:LiveWebSession -ContentType 'application/json' -Body $workflowBody -TimeoutSec 20 | Out-Null
    $approved = Invoke-RestMethod -Method Post -Uri "$LiveApiBaseUrl/cases/$caseId/approve" -Headers $script:LiveMutationHeaders -WebSession $script:LiveWebSession -ContentType 'application/json' -Body $workflowBody -TimeoutSec 20
    if ([string]$approved.status -ne 'active' -or [string]$approved.review_status -ne 'approved') {
      throw "Temporary Web smoke case $caseId was not approved for execution."
    }
    $script:ResolvedWebCaseId = $caseId
    Add-Result -Name 'Seed Web download case' -Status 'passed' -Required:$true -Details "temporary project $projectId, case $caseId approved for execution"
  } catch {
    Add-Result -Name 'Seed Web download case' -Status 'failed' -Required:$true -Details $_.Exception.Message
  }
}

function Invoke-WebLowcodeCheck {
  $caseId = [int]$script:ResolvedWebCaseId
  $required = $caseId -gt 0 -or $RequireWebLowcode -or $RequireWebDownload -or $SeedWebDownloadCase
  $downloadRequired = $RequireWebDownload -or $SeedWebDownloadCase
  if (-not $required) {
    Add-Result -Name 'Web low-code case execution' -Status 'skipped' -Required:$false -Details 'Skipped because -WebCaseId was not supplied.'
    return
  }
  if ($caseId -le 0) {
    Add-Result -Name 'Web low-code case execution' -Status 'failed' -Required:$true -Details 'RequireWebLowcode/RequireWebDownload/SeedWebDownloadCase requires a valid Web case ID.'
    return
  }
  if ([string]::IsNullOrWhiteSpace($script:LiveAccessToken)) {
    Add-Result -Name 'Web low-code case execution' -Status 'failed' -Required:$true -Details 'Cannot execute the Web low-code case without an authenticated session.'
    return
  }

  $timeoutSeconds = [Math]::Max(1, $WebRunTimeoutSeconds)
  try {
    $case = Invoke-RestMethod -Method Get -Uri "$LiveApiBaseUrl/cases/$caseId" -WebSession $script:LiveWebSession -TimeoutSec 20
    $caseType = [string]$case.case_type
    $hasLowcodeSteps = $null -ne $case.config -and @($case.config.PSObject.Properties.Name) -contains 'steps'
    if ($caseType -ne 'web' -or -not $hasLowcodeSteps) {
      throw "Case $caseId is not a Web low-code case."
    }
    if ([string]$case.status -ne 'active' -or [string]$case.review_status -ne 'approved') {
      throw "Web low-code case $caseId must be active and approved before the smoke run."
    }
    if ([string]$case.automation_status -notin @('auto', 'semi_auto')) {
      throw "Web low-code case $caseId is not configured for automated execution."
    }

    $triggerBody = @{} | ConvertTo-Json -Compress
    $started = Invoke-RestMethod -Method Post -Uri "$LiveApiBaseUrl/cases/$caseId/run" -Headers $script:LiveMutationHeaders -WebSession $script:LiveWebSession -ContentType 'application/json' -Body $triggerBody -TimeoutSec 20
    $runId = [int]$started.id
    if ($runId -le 0) {
      throw 'Web low-code run did not return a valid run ID.'
    }
    if ($SeedWebDownloadCase) {
      $script:SeededWebRunId = $runId
    }

    $final = $null
    $finished = $false
    for ($attempt = 0; $attempt -lt $timeoutSeconds; $attempt++) {
      Start-Sleep -Seconds 1
      $final = Invoke-RestMethod -Method Get -Uri "$LiveApiBaseUrl/runs/$runId" -WebSession $script:LiveWebSession -TimeoutSec 20
      if ([string]$final.status -in @('passed', 'failed', 'error', 'cancelled')) {
        $finished = $true
        break
      }
    }
    if ($SeedWebDownloadCase) {
      $script:SeededWebRunFinished = $finished
    }

    $finalStatus = [string]$final.status
    $downloadEvidence = @($final.steps | Where-Object {
        [string]$_.request_data.action -eq 'download' -and
        -not [string]::IsNullOrWhiteSpace([string]$_.response_data.object_name)
      })
    $passed = $finalStatus -eq 'passed'
    $evidenceDetails = if ($downloadEvidence.Count -gt 0) {
      "run $runId passed with $($downloadEvidence.Count) download object(s)"
    } else {
      "run $runId status=$finalStatus; no download object evidence was returned"
    }
    if ($finalStatus -notin @('passed', 'failed', 'error', 'cancelled')) {
      $passed = $false
      $evidenceDetails = "run $runId did not finish within ${timeoutSeconds}s"
    }
    if ($downloadRequired -and $downloadEvidence.Count -eq 0) {
      $passed = $false
      $evidenceDetails = "$evidenceDetails; download evidence is required"
    }
    if ($SeedWebDownloadCase) {
      foreach ($step in $final.steps) {
        foreach ($candidate in @(
            [string]$step.response_data.object_name,
            [string]$step.screenshot_url
          )) {
          if (-not [string]::IsNullOrWhiteSpace($candidate) -and -not $script:SeededWebObjectNames.Contains($candidate)) {
            [void]$script:SeededWebObjectNames.Add($candidate)
          }
        }
      }
      foreach ($candidate in @(
          [string]$final.result_summary.video_url,
          [string]$final.result_summary.trace_url
        )) {
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and -not $script:SeededWebObjectNames.Contains($candidate)) {
          [void]$script:SeededWebObjectNames.Add($candidate)
        }
      }
    }
    Add-Result -Name 'Web low-code case execution' -Status $(if ($passed) { 'passed' } else { 'failed' }) -Required:$true -Details $evidenceDetails
  } catch {
    Add-Result -Name 'Web low-code case execution' -Status 'failed' -Required:$true -Details $_.Exception.Message
  }
}

function Invoke-CleanupSeededWebProject {
  if ($null -eq $script:SeededWebProjectId) {
    return
  }
  if ($null -ne $script:SeededWebRunId -and -not $script:SeededWebRunFinished) {
    Add-Result -Name 'Clean up seeded Web project' -Status 'failed' -Required:$true -Details "Run $($script:SeededWebRunId) did not reach a terminal state; temporary project $($script:SeededWebProjectId) was retained for manual cleanup."
    return
  }
  try {
    $environmentResponse = Invoke-WebRequest -UseBasicParsing -Method Get -Uri "$LiveApiBaseUrl/environments?project_id=$($script:SeededWebProjectId)" -WebSession $script:LiveWebSession -TimeoutSec 20
    $environments = ConvertFrom-Json -InputObject $environmentResponse.Content
    foreach ($environment in @($environments)) {
      Invoke-RestMethod -Method Delete -Uri "$LiveApiBaseUrl/environments/$($environment.id)" -Headers $script:LiveMutationHeaders -WebSession $script:LiveWebSession -TimeoutSec 20 | Out-Null
    }
    Invoke-RestMethod -Method Delete -Uri "$LiveApiBaseUrl/projects/$($script:SeededWebProjectId)" -Headers $script:LiveMutationHeaders -WebSession $script:LiveWebSession -TimeoutSec 20 | Out-Null
    $objectNames = @($script:SeededWebObjectNames.ToArray())
    $deletedObjectCount = 0
    $missingObjectCount = 0
    if ($objectNames.Count -gt 0) {
      $cleanupPayload = @{ object_names = $objectNames; repair_orphan_references = $false } | ConvertTo-Json -Compress
      $cleanup = Invoke-RestMethod -Method Post -Uri "$LiveApiBaseUrl/storage/cleanup-execute" -Headers $script:LiveMutationHeaders -WebSession $script:LiveWebSession -ContentType 'application/json' -Body $cleanupPayload -TimeoutSec 30
      $deletedObjectCount = [int]$cleanup.deleted_count
      $missingObjectCount = [int]$cleanup.missing_count
      $cleanedObjectCount = $deletedObjectCount + $missingObjectCount
      if ($cleanedObjectCount -ne $objectNames.Count -or [int]$cleanup.skipped_referenced_count -gt 0) {
        throw "Temporary Web project was deleted, but $($objectNames.Count - $cleanedObjectCount) artifact object(s) were not cleaned."
      }
    }
    Add-Result -Name 'Clean up seeded Web project' -Status 'passed' -Required:$true -Details "temporary project $($script:SeededWebProjectId) deleted with $($environments.Count) environment(s); artifacts deleted=$deletedObjectCount missing=$missingObjectCount"
  } catch {
    Add-Result -Name 'Clean up seeded Web project' -Status 'failed' -Required:$true -Details "Could not delete temporary project $($script:SeededWebProjectId): $($_.Exception.Message)"
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

function Invoke-AndroidWorkerRegistryCheck {
  param([hashtable]$Values)

  $scanMode = if ($Values.ContainsKey('ADB_SCAN_MODE')) { [string]$Values['ADB_SCAN_MODE'] } else { '' }
  $configuredWorkerId = if ($Values.ContainsKey('ANDROID_WORKER_ID')) { [string]$Values['ANDROID_WORKER_ID'] } else { '' }
  $required = $RequireAndroid -or $scanMode.Trim().ToLowerInvariant() -eq 'worker' -or -not [string]::IsNullOrWhiteSpace($configuredWorkerId)

  if (-not $required -and [string]::IsNullOrWhiteSpace($script:LiveAccessToken)) {
    Add-Result -Name 'Android Worker registry' -Status 'skipped' -Required:$false -Details 'Skipped because Android Worker mode is not enabled and live login was skipped.'
    return
  }
  if ([string]::IsNullOrWhiteSpace($script:LiveAccessToken)) {
    Add-Result -Name 'Android Worker registry' -Status $(if ($required) { 'failed' } else { 'skipped' }) -Required:$required -Details $(if ($required) { 'Cannot verify the required Android Worker registry without an authenticated session.' } else { 'Skipped because live login did not establish an authenticated session.' })
    return
  }
  if (-not $required) {
    Add-Result -Name 'Android Worker registry' -Status 'skipped' -Required:$false -Details 'Skipped because ADB_SCAN_MODE is not worker and no Android Worker ID is configured.'
    return
  }

  try {
    $workers = @(Invoke-RestMethod -Method Get -Uri "$LiveApiBaseUrl/devices/workers" -WebSession $script:LiveWebSession -TimeoutSec 10)
    $workerIds = @($workers | ForEach-Object { [string]$_.worker_id } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $passed = $workerIds.Count -gt 0
    Add-Result -Name 'Android Worker registry' -Status $(if ($passed) { 'passed' } else { 'failed' }) -Required:$required -Details $(if ($passed) { "online Worker(s): $($workerIds -join ', ')" } else { 'No online Android Worker was returned by /devices/workers.' })
  } catch {
    Add-Result -Name 'Android Worker registry' -Status 'failed' -Required:$required -Details $_.Exception.Message
  }
}

function Invoke-AndroidScanCheck {
  param([hashtable]$Values)

  $scanMode = if ($Values.ContainsKey('ADB_SCAN_MODE')) { [string]$Values['ADB_SCAN_MODE'] } else { '' }
  $required = $RequireAndroid -or $scanMode.Trim().ToLowerInvariant() -eq 'worker'
  if (-not $required) {
    Add-Result -Name 'Android device scan callback' -Status 'skipped' -Required:$false -Details 'Skipped because ADB_SCAN_MODE is not worker and -RequireAndroid was not supplied.'
    return
  }
  if ([string]::IsNullOrWhiteSpace($script:LiveAccessToken)) {
    Add-Result -Name 'Android device scan callback' -Status 'failed' -Required:$true -Details 'Cannot verify the Android scan callback without an authenticated session.'
    return
  }

  try {
    $scan = Invoke-RestMethod -Method Post -Uri "$LiveApiBaseUrl/devices/scan" -Headers $script:LiveMutationHeaders -WebSession $script:LiveWebSession -TimeoutSec 20
    $scanStatus = [string]$scan.status
    if ($scanStatus -eq 'completed') {
      Add-Result -Name 'Android device scan callback' -Status 'passed' -Required:$required -Details "Synchronous scan completed with $(@($scan.devices).Count) device(s)."
      return
    }
    if ($scanStatus -eq 'failed') {
      Add-Result -Name 'Android device scan callback' -Status 'failed' -Required:$required -Details ([string]$scan.error)
      return
    }

    $scanId = [string]$scan.scan_id
    if ([string]::IsNullOrWhiteSpace($scanId)) {
      throw 'Worker scan did not return a task ID.'
    }
    $final = $null
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
      Start-Sleep -Milliseconds 500
      $final = Invoke-RestMethod -Method Get -Uri "$LiveApiBaseUrl/devices/scan/$scanId" -WebSession $script:LiveWebSession -TimeoutSec 10
      if ([string]$final.status -in @('completed', 'failed')) {
        break
      }
    }
    $finalStatus = [string]$final.status
    $passed = $finalStatus -eq 'completed'
    $finalDetails = if ($passed) { "Worker scan completed with $(@($final.devices).Count) device(s)." } else { [string]$final.error }
    if (-not $passed -and [string]::IsNullOrWhiteSpace($finalDetails)) {
      $finalDetails = 'Worker scan did not complete within 10 seconds.'
    }
    Add-Result -Name 'Android device scan callback' -Status $(if ($passed) { 'passed' } else { 'failed' }) -Required:$required -Details $finalDetails
  } catch {
    Add-Result -Name 'Android device scan callback' -Status 'failed' -Required:$required -Details $_.Exception.Message
  }
}

Write-Host '=== ATP Windows Local Smoke ==='
Write-Host "Repo: $RepoRoot"
Write-Host "Env:  $ConfiguredEnvFile"
Write-Host ''

$serviceArguments = @()
if ($ConfiguredEnvFile -ne $DefaultEnvFile) {
  $serviceArguments = @('-EnvFile', $ConfiguredEnvFile)
}

if ($StartServices) {
  $start = Invoke-NativeCapture -FilePath $LocalDev -Arguments (@('up') + $serviceArguments) -WorkingDirectory $RepoRoot
  if ($start.ExitCode -ne 0) {
    Add-Result -Name 'Windows local services start' -Status 'failed' -Required:$true -Details $start.Output
  } else {
    Add-Result -Name 'Windows local services start' -Status 'passed' -Required:$true -Details 'local-dev.cmd up completed.'
  }
}

$doctor = Invoke-NativeCapture -FilePath $LocalDev -Arguments (@('doctor') + $serviceArguments) -WorkingDirectory $RepoRoot
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
Invoke-SeedWebDownloadCase
Invoke-WebLowcodeCheck
Invoke-CleanupSeededWebProject
Invoke-AndroidCheck
Invoke-AndroidWorkerRegistryCheck -Values $values
Invoke-AndroidScanCheck -Values $values

if ($StopServicesAfter) {
  $stop = Invoke-NativeCapture -FilePath $LocalDev -Arguments (@('down') + $serviceArguments) -WorkingDirectory $RepoRoot
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
