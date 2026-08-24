from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_windows_android_worker_script_has_safe_queue_and_adb_contract():
    content = (ROOT / "scripts" / "windows-android-worker.ps1").read_text(encoding="utf-8")

    assert "ValidateSet('up', 'down', 'restart', 'status', 'logs', 'doctor')" in content
    assert "[string]$BackendEnvFile = ''" in content
    assert "validate-android-worker-config.py" in content
    assert "Backend/Agent configuration pair" in content
    assert "$QueueList = 'android,mobile_special'" in content
    assert "'--pool=solo'" in content
    assert "'--concurrency=1'" in content
    assert "Get-Command adb.exe" in content
    assert "POSTGRES_HOST" in content
    assert "REDIS_HOST" in content
    assert "MINIO_HOST" in content
    assert "ANDROID_WORKER_ID" in content
    assert "windows-process-env.ps1" in content
    assert "Add-AtpOptionalToolPath" in content
    assert "Push-AtpProcessEnvironment" in content
    assert "Pop-AtpProcessEnvironment" in content
    assert "Windows Android Worker prerequisites failed" in content
    assert "if ((Show-Doctor) -ne 0)" in content


def test_windows_android_worker_documentation_covers_result_callback_and_queue_split():
    content = (ROOT / "docs" / "android-windows-worker.md").read_text(encoding="utf-8")

    assert "android,mobile_special" in content
    assert "PostgreSQL/MinIO" in content
    assert "普通 Worker 需要排除" in content
    assert "整个 ATP 部署只保留一个 Beat" in content or "整个部署只运行一个 Beat" in content
