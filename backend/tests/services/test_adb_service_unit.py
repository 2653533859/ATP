"""adb_service 单元测试（Q13 延伸覆盖：此前 23%，扫描/解析/降级路径零覆盖）。

伪造 subprocess.run（针对 _run_adb 自身分支）与 _run_adb（针对解析/扫描逻辑）
两级边界，运行真实解析逻辑：devices -l 输出解析、serial ip:port 解析、
wm size 正则、getprop 空值回退、scan_devices 三态（None/[]/混合状态）与
devices -l model 后备。模块纯 stdlib 依赖，无需 sys.modules 防御。
"""

import asyncio
import subprocess
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services import adb_service as adb  # noqa: E402

_DEVICES_OUTPUT = """List of devices attached
* daemon started successfully
emu1 device usb:1-1 product:panther model:Pixel_7 device:panther
serialX offline
192.168.1.5:5555 unauthorized
"""


# ── _run_adb：五个分支 ──────────────────────────────────────


def test_run_adb_success_strips_stdout(monkeypatch):
    monkeypatch.setattr(
        adb.subprocess, "run", lambda *a, **kw: types.SimpleNamespace(returncode=0, stdout="  out \n", stderr="")
    )
    assert adb._run_adb("devices") == "out"


def test_run_adb_nonzero_returncode_returns_none(monkeypatch):
    monkeypatch.setattr(
        adb.subprocess, "run", lambda *a, **kw: types.SimpleNamespace(returncode=1, stdout="", stderr="boom")
    )
    assert adb._run_adb("devices") is None


def test_run_adb_missing_binary_returns_none(monkeypatch):
    def raise_fnf(*_a, **_kw):
        raise FileNotFoundError("adb")

    monkeypatch.setattr(adb.subprocess, "run", raise_fnf)
    assert adb._run_adb("devices") is None


def test_run_adb_timeout_returns_none(monkeypatch):
    def raise_timeout(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="adb devices", timeout=10)

    monkeypatch.setattr(adb.subprocess, "run", raise_timeout)
    assert adb._run_adb("devices") is None


def test_run_adb_generic_error_returns_none(monkeypatch):
    def raise_generic(*_a, **_kw):
        raise OSError("fd exhausted")

    monkeypatch.setattr(adb.subprocess, "run", raise_generic)
    assert adb._run_adb("devices") is None


# ── 解析器 ──────────────────────────────────────────────────


def test_parse_devices_output_skips_noise_and_extracts_props():
    parsed = adb._parse_devices_output(_DEVICES_OUTPUT)

    assert [d["serial"] for d in parsed] == ["emu1", "serialX", "192.168.1.5:5555"]
    assert parsed[0]["status"] == "device" and parsed[0]["model"] == "Pixel_7"
    assert parsed[1] == {"serial": "serialX", "status": "offline"}
    assert parsed[2]["status"] == "unauthorized"


def test_parse_serial_address_variants():
    assert adb._parse_serial_address("192.168.1.5:5555") == ("192.168.1.5", 5555)
    assert adb._parse_serial_address("usbSerial01") == (None, None)
    assert adb._parse_serial_address("192.168.1.5:oops") == ("192.168.1.5", None)


def test_get_resolution_regex(monkeypatch):
    monkeypatch.setattr(adb, "_run_adb", lambda *a, **kw: "Physical size: 1080x1920")
    assert adb._get_resolution("emu1") == "1080x1920"

    monkeypatch.setattr(adb, "_run_adb", lambda *a, **kw: "error: no display")
    assert adb._get_resolution("emu1") is None


# ── get_device_props：getprop 空值回退 ──────────────────────


def _fake_run_adb(props: dict[str, str], devices_output: str = _DEVICES_OUTPUT, wm_size: str = ""):
    def fake(*args, timeout=10):
        if args[:2] == ("devices", "-l"):
            return devices_output
        if "getprop" in args:
            return props.get(args[-1], "")
        if args[-2:] == ("wm", "size"):
            return wm_size
        return ""

    return fake


def test_get_device_props_full(monkeypatch):
    monkeypatch.setattr(
        adb,
        "_run_adb",
        _fake_run_adb(
            {
                "ro.product.model": "Pixel 7",
                "ro.product.brand": "google",
                "ro.build.version.release": "14",
                "ro.build.version.sdk": "34",
            },
            wm_size="Physical size: 1080x2400",
        ),
    )

    info = adb.get_device_props("192.168.1.5:5555")

    assert info.model == "Pixel 7" and info.brand == "google"
    assert info.os_version == "14" and info.sdk_version == "34"
    assert info.resolution == "1080x2400"
    assert info.ip_address == "192.168.1.5" and info.port == 5555


def test_get_device_props_empty_props_fall_back_to_none(monkeypatch):
    monkeypatch.setattr(adb, "_run_adb", _fake_run_adb({}))

    info = adb.get_device_props("usbSerial01")

    assert info.model is None and info.brand is None
    assert info.os_version is None and info.sdk_version is None
    assert info.resolution is None and info.ip_address is None


# ── scan_devices：三态 + model 后备 ─────────────────────────


def test_scan_devices_returns_none_when_adb_unavailable(monkeypatch):
    monkeypatch.setattr(adb, "_run_adb", lambda *a, **kw: None)
    assert adb.scan_devices() is None


def test_scan_devices_empty_output_returns_empty_list(monkeypatch):
    monkeypatch.setattr(adb, "_run_adb", lambda *a, **kw: "")
    assert adb.scan_devices() == []


def test_scan_devices_mixed_statuses_with_model_fallback(monkeypatch):
    # getprop 全空 → device 行的 model 从 devices -l 属性后备
    monkeypatch.setattr(adb, "_run_adb", _fake_run_adb({}))

    result = adb.scan_devices()

    assert [d.serial for d in result] == ["emu1", "serialX", "192.168.1.5:5555"]
    online = result[0]
    assert online.status == "device" and online.model == "Pixel_7"  # devices -l 后备
    assert result[1].status == "offline" and result[1].model is None
    unauthorized = result[2]
    assert unauthorized.status == "unauthorized"
    assert unauthorized.ip_address == "192.168.1.5" and unauthorized.port == 5555


def test_async_scan_devices_runs_in_executor(monkeypatch):
    monkeypatch.setattr(adb, "_run_adb", _fake_run_adb({}))
    result = asyncio.run(adb.async_scan_devices())
    assert len(result) == 3 and result[0].serial == "emu1"
