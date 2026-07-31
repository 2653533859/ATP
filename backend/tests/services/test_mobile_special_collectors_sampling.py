"""mobile_special collectors 采样会话/周期采样器单元测试（此前 0%）。

传输边界 run_adb_shell 与 parse_* 全部 fake：验证采样会话的 PID 解析、
parser 路由、空输出→None，以及 PeriodicSampler 的按类型产出、跳过 None、停止。
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.mobile_special import collectors  # noqa: E402


async def _async_noop(_seconds):
    return None


@pytest.fixture()
def parsers(monkeypatch):
    """fake 各 parser：返回带来源标记的 dict，验证 collector 路由到正确 parser。"""
    monkeypatch.setattr(collectors, "parse_pid", lambda raw: 4321)
    for name in ("parse_cpuinfo", "parse_meminfo", "parse_gfxinfo_framestats", "parse_batterystats"):
        monkeypatch.setattr(collectors, name, lambda raw, pkg, _n=name: {"metric": _n, "raw": raw, "pkg": pkg})


def _install_adb(monkeypatch, responder):
    monkeypatch.setattr(collectors, "run_adb_shell", responder)


def _run(coro):
    return asyncio.run(coro)


# ── SamplingSession ─────────────────────────────────────────


def test_session_resolves_pid_on_enter(monkeypatch, parsers):
    _install_adb(monkeypatch, lambda serial, cmd, timeout=None: "raw-pid")

    async def scenario():
        async with collectors.SamplingSession("emu-5554", "com.acme.app") as session:
            return session.pid

    assert _run(scenario()) == 4321


def test_session_keeps_explicit_pid_without_running_adb(monkeypatch, parsers):
    calls = []
    _install_adb(monkeypatch, lambda serial, cmd, timeout=None: calls.append(cmd) or "x")

    async def scenario():
        async with collectors.SamplingSession("emu-5554", "com.acme.app", pid=99) as session:
            return session.pid

    assert _run(scenario()) == 99
    assert calls == []  # 显式 pid 时不解析


def test_resolve_pid_returns_none_when_no_output(monkeypatch, parsers):
    _install_adb(monkeypatch, lambda serial, cmd, timeout=None: "")

    async def scenario():
        async with collectors.SamplingSession("emu-5554", "com.acme.app") as session:
            return session.pid

    assert _run(scenario()) is None


def test_each_sampler_routes_raw_to_its_parser(monkeypatch, parsers):
    _install_adb(monkeypatch, lambda serial, cmd, timeout=None: "RAW")
    session = collectors.SamplingSession("emu-5554", "com.acme.app", pid=1)

    assert _run(session.sample_cpu())["metric"] == "parse_cpuinfo"
    assert _run(session.sample_memory())["metric"] == "parse_meminfo"
    assert _run(session.sample_fps())["metric"] == "parse_gfxinfo_framestats"
    assert _run(session.sample_battery())["metric"] == "parse_batterystats"
    assert _run(session.sample_cpu())["pkg"] == "com.acme.app"


def test_samplers_return_none_on_empty_output(monkeypatch, parsers):
    _install_adb(monkeypatch, lambda serial, cmd, timeout=None: "")
    session = collectors.SamplingSession("emu-5554", "com.acme.app", pid=1)

    assert _run(session.sample_cpu()) is None
    assert _run(session.sample_memory()) is None
    assert _run(session.sample_fps()) is None
    assert _run(session.sample_battery()) is None


# ── PeriodicSampler ─────────────────────────────────────────


def test_periodic_sampler_yields_selected_metrics_then_stops(monkeypatch, parsers):
    monkeypatch.setattr(collectors.asyncio, "sleep", _async_noop)
    _install_adb(monkeypatch, lambda serial, cmd, timeout=None: "RAW")
    session = collectors.SamplingSession("emu-5554", "com.acme.app", pid=1)
    sampler = collectors.PeriodicSampler(session, interval_seconds=0.01, metric_types=["cpu", "fps"])

    async def collect():
        out = []
        async for sample in sampler.run():
            assert "sample_time" in sample
            out.append(sample["metric"])
            if len(out) >= 2:
                sampler.stop()
        return out

    assert _run(collect()) == ["parse_cpuinfo", "parse_gfxinfo_framestats"]


def test_periodic_sampler_defaults_to_cpu_and_memory():
    session = collectors.SamplingSession("emu-5554", "com.acme.app", pid=1)
    assert collectors.PeriodicSampler(session).metric_types == ["cpu", "memory"]


def test_periodic_sampler_skips_none_samples(monkeypatch, parsers):
    monkeypatch.setattr(collectors.asyncio, "sleep", _async_noop)
    # cpu 命令返回空 → None 跳过；memory 返回 RAW → 产出
    _install_adb(monkeypatch, lambda serial, cmd, timeout=None: "" if "cpuinfo" in " ".join(cmd) else "RAW")
    session = collectors.SamplingSession("emu-5554", "com.acme.app", pid=1)
    sampler = collectors.PeriodicSampler(session, interval_seconds=0.01, metric_types=["cpu", "memory"])

    async def collect():
        out = []
        async for sample in sampler.run():
            out.append(sample["metric"])
            sampler.stop()
        return out

    assert _run(collect()) == ["parse_meminfo"]


# ── validators ──────────────────────────────────────────────


def test_validate_device_ready(monkeypatch):
    _install_adb(monkeypatch, lambda s, c, timeout=None: "ok")
    assert collectors.validate_device_ready("emu-5554") is True
    _install_adb(monkeypatch, lambda s, c, timeout=None: "error: offline")
    assert collectors.validate_device_ready("emu-5554") is False


def test_validate_package_installed(monkeypatch):
    _install_adb(monkeypatch, lambda s, c, timeout=None: "package:com.acme.app")
    assert collectors.validate_package_installed("emu-5554", "com.acme.app") is True
    _install_adb(monkeypatch, lambda s, c, timeout=None: "package:com.other")
    assert collectors.validate_package_installed("emu-5554", "com.acme.app") is False
    _install_adb(monkeypatch, lambda s, c, timeout=None: None)
    assert collectors.validate_package_installed("emu-5554", "com.acme.app") is False
