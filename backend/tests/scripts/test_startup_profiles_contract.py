import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_startup_selector_exposes_profiles_and_does_not_overwrite_root_env():
    script = (ROOT / "scripts" / "startup.ps1").read_text(encoding="utf-8")

    assert "local-all" in script
    assert "remote-infra" in script
    assert "android-agent" in script
    assert "Import-ProfileEnvironment" in script
    assert "Restore-ProfileEnvironment" in script
    assert "Copy the template first" in script
    assert "Set-Content" not in script


def test_startup_profile_templates_cover_local_remote_and_android_modes():
    profile_root = ROOT / "config" / "startup-profiles"
    for profile in ("local-all", "remote-infra", "android-agent"):
        content = (profile_root / f"{profile}.env.example").read_text(encoding="utf-8")
        assert "POSTGRES_HOST=" in content
        assert "REDIS_HOST=" in content
        assert "MINIO_HOST=" in content
        assert "CELERY_QUEUES=" in content
        assert "APP_SECRET_KEY=" in content

    assert "ADB_SCAN_MODE=local" in (profile_root / "android-agent.env.example").read_text(encoding="utf-8")
    assert "CELERY_QUEUES=android,mobile_special" in (profile_root / "android-agent.env.example").read_text(
        encoding="utf-8"
    )


def test_android_worker_backend_deployment_profile_separates_server_and_agent_modes():
    profile = ROOT / "config" / "deployment-profiles" / "android-worker-backend.env.example"
    readme = (ROOT / "config" / "deployment-profiles" / "README.md").read_text(encoding="utf-8")
    content = profile.read_text(encoding="utf-8")

    assert "ADB_SCAN_MODE=worker" in content
    assert "CELERY_QUEUES=default,ios,ai,maintenance,performance" in content
    assert "android,mobile_special" not in content.split("CELERY_QUEUES=", 1)[1].splitlines()[0]
    assert "ANDROID_WORKER_QUEUE=mobile_special" in content
    assert "config/startup-profiles/android-agent.env" in readme
    assert "不要把此文件直接作为 Windows Android Agent 配置" in content
    assert "change_me" in content
    assert "172.31.27.133" not in content


def test_startup_config_ui_covers_every_env_template_key():
    env_keys = {
        match.group(1)
        for match in re.finditer(
            r"^([A-Z][A-Z0-9_]*)=", (ROOT / ".env.example").read_text(encoding="utf-8"), re.MULTILINE
        )
    }
    ui = (ROOT / "frontend/src/views/system/StartupConfigView.vue").read_text(encoding="utf-8")
    interface = re.search(r"interface StartupConfig \{(.*?)\n\}", ui, re.DOTALL)
    assert interface is not None
    ui_keys = set(re.findall(r"^\s*([A-Z][A-Z0-9_]*):", interface.group(1), re.MULTILINE))

    assert env_keys <= ui_keys
