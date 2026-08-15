"""Static contracts for the Windows local development helpers."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_windows_local_script_exposes_doctor_and_windows_safe_repo_resolution():
    script = _read("scripts/windows-local.ps1")

    assert "'doctor'" in script
    assert "Get-DotEnvValues" in script
    assert "Test-TcpEndpoint" in script
    assert "PERFORMANCE_EXECUTORS" in script
    assert "PlaywrightPackage" in script
    assert "profile=$profile" in script
    assert "PostgreSQL=$($values['POSTGRES_HOST'])" in script
    assert "windows-local-runtime.json" in script
    assert "Write-RuntimeMetadata" in script
    assert "Remove-RuntimeMetadata" in script
    assert "Configure-WorkerQueues" in script
    assert "Get-ConfiguredWorkerQueues" in script
    assert "PERFORMANCE_NODE_QUEUE" in script
    assert "^[A-Za-z0-9_.-]+$" in script
    assert "Test-EnabledValue" in script
    assert "Configure-WebRecordingService" in script
    assert "WEB_RECORDER_MODE" in script
    assert "Get-WebRecordingMode" in script
    assert "Get-PlaywrightChromiumExecutable" in script
    assert "Python Playwright package" in script
    assert "Python Playwright Chromium browser" in script
    assert "WEB_RECORDER_WORKER_QUEUE_PREFIX" in script
    assert "WEB_RECORDER_WORKER_MAX_SESSIONS" in script
    assert "app.web_recording_worker" in script
    assert "Key = 'web-recorder'" in script
    assert "for ($index = $Services.Count - 1; $index -ge 0; $index--)" in script
    assert "'-Q'" in script
    assert "(?:\\s+-Q\\s+\\S+)?" in script
    assert "ExcludePattern = '--hostname\\s+(?:android-win-|performance-win-)'" in script
    assert "function Assert-AndroidWorkerQueueIsolation" in script
    assert "Stop the Android Worker or use an environment that excludes android,mobile_special" in script
    assert "F:\\csh\\MyProjectAutoTest" not in script


def test_windows_start_scripts_apply_selected_env_file_only_to_child_processes():
    helper = _read("scripts/windows-process-env.ps1")
    local_script = _read("scripts/windows-local.ps1")
    android_script = _read("scripts/windows-android-worker.ps1")

    assert "function Push-AtpProcessEnvironment" in helper
    assert "function Pop-AtpProcessEnvironment" in helper
    assert "function Add-AtpOptionalToolPath" in helper
    assert "ATP_K6_HOME" in helper
    assert "ATP_ADB_HOME" in helper
    assert "ANDROID_HOME" in helper
    assert "ANDROID_SDK_ROOT" in helper
    assert "Android\\Sdk\\platform-tools" in helper
    assert "ATP\\tools\\platform-tools" in helper
    assert "adb.exe" in helper
    assert "LocalApplicationData" in helper
    assert "ATP\\tools\\k6" in helper
    assert "Add-AtpOptionalToolPath" in local_script
    assert "Push-AtpProcessEnvironment -Values (Get-DotEnvValues)" in local_script
    assert "Pop-AtpProcessEnvironment -Previous $previousEnvironment" in local_script
    assert "Missing selected environment file" in local_script
    assert "Push-AtpProcessEnvironment -Values (Get-DotEnvValues)" in android_script
    assert "Pop-AtpProcessEnvironment -Previous $previousEnvironment" in android_script
    assert "Missing selected environment file" in android_script
    assert "windows-process-env.ps1" in local_script
    assert "windows-process-env.ps1" in android_script
    assert "Add-AtpOptionalToolPath" in android_script


def test_android_network_doctor_has_a_powershell_entrypoint_and_safe_modes():
    script = _read("scripts/android-network-doctor.ps1")

    assert "[switch]$SkipServerRestart" in script
    assert "[switch]$SkipConnect" in script
    assert "adb.exe" in script
    assert "adb devices" in script
    assert "shell echo" in script
    assert "windows-process-env.ps1" in script
    assert "Add-AtpOptionalToolPath" in script


def test_windows_android_worker_checks_runtime_dependencies_before_starting():
    script = _read("scripts/windows-android-worker.ps1")

    assert "function Test-PythonModule" in script
    assert "Celery and Redis Python dependencies" in script
    assert "Test-PythonModule -ModuleName 'celery'" in script
    assert "Test-PythonModule -ModuleName 'redis'" in script
    assert "function Test-WorkerConsumesAndroidQueue" in script
    assert "function Assert-NoLocalWorkerQueueConflict" in script
    assert "Stop local-all first, or use a local Worker environment that excludes android,mobile_special" in script


def test_android_worker_doctor_resolves_optional_adb_path_before_checks():
    script = _read("scripts/windows-android-worker.ps1")

    assert script.index("Add-AtpOptionalToolPath") < script.index("function Show-Doctor")
    assert script.index("Add-AtpOptionalToolPath") < script.index("Get-Command adb.exe")


def test_windows_performance_worker_has_dedicated_node_queue_and_doctor():
    script = _read("scripts/windows-performance-worker.ps1")

    assert "ValidateSet('up', 'down', 'restart', 'status', 'logs', 'doctor')" in script
    assert "PERFORMANCE_NODE_ENABLED" in script
    assert "PERFORMANCE_NODE_ID" in script
    assert "PERFORMANCE_NODE_QUEUE" in script
    assert "function Get-NodeConfig" in script
    assert "function Assert-NoWorkerQueueConflict" in script
    assert "function Test-WorkerConsumesQueue" in script
    assert "Performance node queue is not the shared queue" in script
    assert "Push-AtpProcessEnvironment -Values $values" in script
    assert "Pop-AtpProcessEnvironment -Previous $previousEnvironment" in script
    assert "--hostname', $hostname" in script
    assert "'-Q', $node.Queue" in script
    assert "performance-worker.pid" in script
    assert "windows-process-env.ps1" in script
    assert "Add-AtpOptionalToolPath" in script
    assert "PostgreSQL=$($values['POSTGRES_HOST'])" in script


def test_windows_prometheus_script_is_local_only_and_has_lifecycle_checks():
    script = _read("scripts/windows-prometheus.ps1")
    config = _read("config/prometheus/windows-local.yml")

    assert "ValidateSet('up', 'down', 'restart', 'status', 'logs', 'doctor')" in script
    assert "ATP\\tools\\prometheus" in script
    assert "127.0.0.1:$Port" in script
    assert "127.0.0.1:8000/metrics" in script
    assert "function Get-PrometheusProcess" in script
    assert "function Test-HttpReady" in script
    assert "function Show-Doctor" in script
    assert "prometheus.pid" in script
    assert "-WindowStyle Hidden" in script
    assert "job_name: atp-backend" in config
    assert "127.0.0.1:8000" in config


def test_windows_prometheus_evidence_is_sanitized_and_links_target_samples():
    evidence = _read("docs/evidence/performance-windows-local-prometheus-target-metrics-2026-08-12.json")

    assert '"status": "passed"' in evidence
    assert '"target_metric_source": "target-service-prometheus"' in evidence
    assert '"target_metric_errors": []' in evidence
    assert '"password"' not in evidence.lower()
    assert '"token"' not in evidence.lower()
    assert '"secret"' not in evidence.lower()


def test_windows_remote_infra_smoke_evidence_is_sanitized_and_has_cleanup():
    evidence = _read("docs/evidence/windows-local-smoke-remote-infra-web-seed-2026-08-12.json")

    assert '"status": "passed"' in evidence
    assert '"required_failures": 0' in evidence
    assert '"Playwright mock E2E suite (10 passed)"' in evidence
    assert '"Playwright browser matrix login page (Chromium, Firefox, WebKit)"' in evidence
    assert '"download_objects": 1' in evidence
    assert '"artifacts_deleted": 5' in evidence
    assert '"password"' not in evidence.lower()
    assert '"token"' not in evidence.lower()
    assert '"secret"' not in evidence.lower()


def test_startup_profiles_include_the_windows_performance_agent():
    startup = _read("scripts/startup.ps1")
    example = _read("config/startup-profiles/performance-agent.env.example")
    readme = _read("config/startup-profiles/README.md")

    assert "'performance-agent'" in startup
    assert "windows-performance-worker.ps1" in startup
    assert "PERFORMANCE_NODE_QUEUE=performance.worker-a" in example
    assert "performance-agent.env.example" in readme


def test_windows_local_smoke_covers_live_and_browser_paths_without_secrets():
    script = _read("scripts/windows-local-smoke.ps1")

    assert "[switch]$StartServices" in script
    assert "[string]$EnvFile = ''" in script
    assert "$ConfiguredEnvFile" in script
    assert "@('-EnvFile', $ConfiguredEnvFile)" in script
    assert "windows-local-runtime.json" in script
    assert "ConvertFrom-Json" in script
    assert "runtime.env_file" in script
    assert 'Write-Host "Env:  $ConfiguredEnvFile"' in script
    assert "[switch]$SkipLiveLogin" in script
    assert "[switch]$SkipFileTransfer" in script
    assert "[switch]$SkipReports" in script
    assert "[int]$AndroidCaseId = 0" in script
    assert "[switch]$RequireAndroidLowcode" in script
    assert "[switch]$RequireAndroidEvidence" in script
    assert "[int]$AndroidRunTimeoutSeconds = 180" in script
    assert "[int]$WebCaseId = 0" in script
    assert "[switch]$SeedWebDownloadCase" in script
    assert "[switch]$RequireWebLowcode" in script
    assert "[switch]$RequireWebDownload" in script
    assert "[int]$WebRunTimeoutSeconds = 120" in script
    assert "[int]$LiveRequestTimeoutSeconds = 30" in script
    assert "-TimeoutSec $LiveRequestTimeoutSeconds" in script
    assert "[switch]$StopServicesAfter" in script
    assert "IsPathRooted" in script
    assert "local-dev.cmd" in script
    assert "/health" in script
    assert "/api/v1/auth/login" in script
    assert "/auth/me" in script
    assert "atp_access_token" in script
    assert "WebRequestSession" in script
    assert "'/projects'" in script
    assert "/health/dependencies" in script
    assert "Invoke-LiveDependencyCheck" in script
    assert "Key = 'postgres'; Label = 'PostgreSQL'" in script
    assert "Key = 'redis'; Label = 'Redis'" in script
    assert "Key = 'minio'; Label = 'MinIO'" in script
    assert "Live dependency readiness" in script
    assert "/web-recordings/workers" in script
    assert "Invoke-WebRecordingWorkerCheck" in script
    assert "Web recording Worker status" in script
    assert "registered_count" in script
    assert "available_count" in script
    assert "/web-files" in script
    assert "/storage/cleanup-execute" in script
    assert "export/html" in script
    assert "/junit" in script
    assert "No historical run is available" in script
    assert "if ([string]::IsNullOrWhiteSpace($objectName))" in script
    assert "'run', 'e2e'" in script
    assert "e2e:browser-matrix" in script
    assert "HttpOnly cookie session established" in script
    assert "LiveMutationHeaders" in script
    assert "X-Requested-With" in script
    assert "request.Headers.Add('X-Requested-With', 'XMLHttpRequest')" in script
    assert "CookieContainer" in script
    assert "GetCookies($targetUri)" in script
    assert "/devices/workers" in script
    assert "Invoke-AndroidWorkerRegistryCheck" in script
    assert "/devices/scan" in script
    assert "Invoke-AndroidScanCheck" in script
    assert "Invoke-AndroidLowcodeCheck" in script
    assert "Android low-code case execution" in script
    assert "is not an Android low-code case with a device binding" in script
    assert "Android low-code case $caseId must be active and approved" in script
    assert "no screenshot or Android artifact evidence was returned" in script
    assert "$_.Name -notlike '*_error'" in script
    assert "Invoke-RestMethod -Method Get -Uri \"$LiveApiBaseUrl/runs/$runId\"" in script
    assert "Worker scan did not return a task ID" in script
    assert "Invoke-WebLowcodeCheck" in script
    assert "Invoke-SeedWebDownloadCase" in script
    assert "Invoke-CleanupSeededWebProject" in script
    assert "data:text/html" in script
    assert "ConvertFrom-Json -InputObject $moduleResponse.Content" in script
    assert "temporary project" in script
    assert "did not reach a terminal state" in script
    assert "/cases/$caseId/submit-review" in script
    assert "/cases/$caseId/approve" in script
    assert "approved for execution" in script
    assert "/cases/$caseId/run" in script
    assert '/cases/$caseId"' in script
    assert "is not a Web low-code case" in script
    assert "must be active and approved" in script
    assert "not configured for automated execution" in script
    assert "/environments?project_id=" in script
    assert "SeededWebObjectNames" in script
    assert "/storage/cleanup-execute" in script
    assert "deleted_count" in script
    assert "download object evidence" in script
    assert "download evidence is required" in script
    assert "$downloadRequired = $RequireWebDownload -or $SeedWebDownloadCase" in script
    assert "ADB_SCAN_MODE" in script
    assert "ConvertTo-Json" in script
    assert "F:\\csh\\MyProjectAutoTest" not in script
