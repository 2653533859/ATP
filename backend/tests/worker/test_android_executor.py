import sys
import types
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.modules["app.core.minio_client"] = types.SimpleNamespace(
    download_file=lambda *args, **kwargs: None,
    upload_file=lambda *args, **kwargs: None,
    presigned_url=lambda *args, **kwargs: "http://example.com/image.png",
)
sys.modules["app.core.redis_client"] = types.SimpleNamespace(
    publish_run_event=lambda *args, **kwargs: None,
    get_json_cache=lambda *args, **kwargs: None,
    set_json_cache=lambda *args, **kwargs: None,
    delete_json_cache=lambda *args, **kwargs: None,
    delete_json_cache_pattern=lambda *args, **kwargs: None,
)

from app.worker.executors import android_executor


def test_check_device_reachable_reports_offline(monkeypatch):
    class _Proc:
        returncode = 0
        stdout = "offline\n"
        stderr = ""

    monkeypatch.setattr(android_executor.subprocess, "run", lambda *args, **kwargs: _Proc())
    # 关闭重连以保持旧测试语义（旧测试只 mock 一次 subprocess.run）
    from app.core.config import settings

    monkeypatch.setattr(settings, "ADB_RECONNECT_ENABLED", False)
    monkeypatch.setattr(settings, "ADB_RECONNECT_MAX_ATTEMPTS", 1)

    ok, message = android_executor._check_device_reachable("192.168.0.10:5555")

    assert ok is False
    assert "offline" in message


def test_check_device_reachable_reports_unauthorized(monkeypatch):
    class _Proc:
        returncode = 0
        stdout = "unauthorized\n"
        stderr = ""

    monkeypatch.setattr(android_executor.subprocess, "run", lambda *args, **kwargs: _Proc())

    ok, message = android_executor._check_device_reachable("ABC123")

    assert ok is False
    assert "未授权" in message


def test_install_apk_retries_via_safe_run_adb(monkeypatch):
    """APK 安装首次失败、ensure_reachable 成功后第二次成功。"""
    call_log = {"n": 0}

    def _scripted_run(cmd, *args, **kwargs):
        call_log["n"] += 1
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        # 第 1 次 install 失败
        if call_log["n"] == 1:
            return types.SimpleNamespace(returncode=1, stdout="", stderr="connection broken")
        # ensure_reachable 的 get-state
        if "get-state" in cmd_str:
            return types.SimpleNamespace(returncode=0, stdout="device", stderr="")
        # 第 2 次 install 成功
        return types.SimpleNamespace(returncode=0, stdout="Success\n", stderr="")

    monkeypatch.setattr(android_executor.subprocess, "run", _scripted_run)
    # 走 disconnect/connect 路径需要 ADB_RECONNECT_ENABLED；这里不需要重连
    from app.core.config import settings

    monkeypatch.setattr(settings, "ADB_RECONNECT_ENABLED", True)
    # 不真正 sleep
    from app.services import adb_resilience

    monkeypatch.setattr(adb_resilience.time, "sleep", lambda *_: None)

    ok, msg = android_executor._install_apk("192.168.0.10:5555", "/tmp/app.apk")

    assert ok is True
    assert "成功" in msg


def test_check_device_reachable_recovers_via_reconnect(monkeypatch):
    """offline → 自动 disconnect/connect → 第二次 device，应判定恢复。"""
    sequence = iter(
        [
            types.SimpleNamespace(returncode=0, stdout="offline", stderr=""),
            types.SimpleNamespace(returncode=0, stdout="", stderr=""),  # disconnect
            types.SimpleNamespace(returncode=0, stdout="connected to 192.168.0.10:5555", stderr=""),  # connect
            types.SimpleNamespace(returncode=0, stdout="device", stderr=""),
        ]
    )
    monkeypatch.setattr(android_executor.subprocess, "run", lambda *a, **kw: next(sequence))
    from app.services import adb_resilience

    monkeypatch.setattr(adb_resilience.time, "sleep", lambda *_: None)
    from app.core.config import settings

    monkeypatch.setattr(settings, "ADB_RECONNECT_ENABLED", True)
    monkeypatch.setattr(settings, "ADB_RECONNECT_MAX_ATTEMPTS", 3)

    ok, message = android_executor._check_device_reachable("192.168.0.10:5555")

    assert ok is True
    assert "重连后恢复" in message


def test_install_apk_reports_timeout_via_sentinel(monkeypatch):
    """safe_run_adb 内部 TimeoutExpired 会返回带 ADB_TIMEOUT_SENTINEL 的占位 CompletedProcess；
    _install_apk 应通过 is_adb_timeout 识别并给出"安装超时"明确文案，而不是"安装失败"。
    """
    import subprocess as real_subprocess

    def _scripted_run(cmd, *args, **kwargs):
        raise real_subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 60))

    monkeypatch.setattr(android_executor.subprocess, "run", _scripted_run)
    from app.core.config import settings

    # 关闭 reconnect 以避免 ensure_reachable 在重试前再次调用
    monkeypatch.setattr(settings, "ADB_RECONNECT_ENABLED", False)
    from app.services import adb_resilience

    monkeypatch.setattr(adb_resilience.time, "sleep", lambda *_: None)

    ok, msg = android_executor._install_apk("192.168.0.10:5555", "/tmp/app.apk", timeout=15)

    assert ok is False
    assert "超时" in msg
    assert "15" in msg
