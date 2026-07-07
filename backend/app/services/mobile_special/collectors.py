"""Collectors for periodic metric sampling during mobile special runs.

Collectors wrap ADB commands and parsers into coherent sampling sessions.
Each collector class is responsible for one metric category (CPU, memory, etc.)
and can be run in a loop by the executor.
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Optional

from app.models.mobile_special import MetricType
from app.services.mobile_special.adb_client import (
    run_adb_shell,
    build_meminfo_cmd,
    build_gfxinfo_cmd,
    build_cpuinfo_cmd,
    build_batterystats_cmd,
    build_pidof_cmd,
)
from app.services.mobile_special.parsers import (
    parse_meminfo,
    parse_gfxinfo_framestats,
    parse_cpuinfo,
    parse_batterystats,
    parse_pid,
)

logger = logging.getLogger(__name__)


class SamplingSession:
    """Context manager for a sampling session on a device.

    Usage:
        async with SamplingSession("emulator-5554", "com.example.app") as session:
            sample = await session.sample_cpu()
    """

    def __init__(
        self,
        device_serial: str,
        package: str,
        pid: Optional[int] = None,
    ):
        self.device_serial = device_serial
        self.package = package
        self.pid = pid
        self._pid_resolved = False

    async def __aenter__(self):
        if self.pid is None and not self._pid_resolved:
            self.pid = await self._resolve_pid()
            self._pid_resolved = True
        return self

    async def __aexit__(self, *args):
        return None

    async def _resolve_pid(self) -> Optional[int]:
        """Resolve the package name to a PID."""
        cmd = build_pidof_cmd(self.device_serial, self.package)
        raw = await asyncio.get_event_loop().run_in_executor(None, run_adb_shell, self.device_serial, cmd, 5)
        if raw:
            return parse_pid(raw)
        return None

    async def sample_cpu(self) -> Optional[dict]:
        """Sample CPU usage percentage."""
        cmd = build_cpuinfo_cmd(self.device_serial, self.package)
        raw = await asyncio.get_event_loop().run_in_executor(None, run_adb_shell, self.device_serial, cmd, 10)
        if raw:
            return parse_cpuinfo(raw, self.package)
        return None

    async def sample_memory(self) -> Optional[dict]:
        """Sample memory usage in MB."""
        cmd = build_meminfo_cmd(self.device_serial, self.package)
        raw = await asyncio.get_event_loop().run_in_executor(None, run_adb_shell, self.device_serial, cmd, 10)
        if raw:
            return parse_meminfo(raw, self.package)
        return None

    async def sample_fps(self) -> Optional[dict]:
        """Sample FPS and jank metrics."""
        cmd = build_gfxinfo_cmd(self.device_serial, self.package)
        raw = await asyncio.get_event_loop().run_in_executor(None, run_adb_shell, self.device_serial, cmd, 10)
        if raw:
            return parse_gfxinfo_framestats(raw, self.package)
        return None

    async def sample_battery(self) -> Optional[dict]:
        """Sample battery percentage."""
        cmd = build_batterystats_cmd(self.device_serial, self.package)
        raw = await asyncio.get_event_loop().run_in_executor(None, run_adb_shell, self.device_serial, cmd, 10)
        if raw:
            return parse_batterystats(raw, self.package)
        return None


class PeriodicSampler:
    """Runs sampling at fixed intervals until stopped.

    Usage:
        sampler = PeriodicSampler(
            session=session,
            interval_seconds=5.0,
            metric_types=["cpu", "memory"],
        )
        async for sample in sampler.run():
            await store_sample(sample)
    """

    def __init__(
        self,
        session: SamplingSession,
        interval_seconds: float = 5.0,
        metric_types: Optional[list[str]] = None,
    ):
        self.session = session
        self.interval_seconds = interval_seconds
        self.metric_types = metric_types or ["cpu", "memory"]
        self._stop = False

    def stop(self):
        """Signal the sampler to stop."""
        self._stop = True

    async def run(self):
        """Async generator yielding metric samples."""
        while not self._stop:
            sample_time = datetime.now()

            if "cpu" in self.metric_types:
                sample = await self.session.sample_cpu()
                if sample:
                    yield {**sample, "sample_time": sample_time}

            if "memory" in self.metric_types:
                sample = await self.session.sample_memory()
                if sample:
                    yield {**sample, "sample_time": sample_time}

            if "fps" in self.metric_types:
                sample = await self.session.sample_fps()
                if sample:
                    yield {**sample, "sample_time": sample_time}

            if "battery" in self.metric_types:
                sample = await self.session.sample_battery()
                if sample:
                    yield {**sample, "sample_time": sample_time}

            await asyncio.sleep(self.interval_seconds)


def validate_device_ready(serial: str) -> bool:
    """Check if device is online and accessible for testing."""
    return run_adb_shell(serial, ["echo", "ok"], timeout=5) == "ok"


def validate_package_installed(serial: str, package: str) -> bool:
    """Check if the app package is installed on the device."""
    cmd = ["pm", "list", "packages", package]
    raw = run_adb_shell(serial, cmd, timeout=10)
    return raw is not None and package in raw
