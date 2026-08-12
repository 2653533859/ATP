"""Best-effort resource sampling for HTTP performance runs."""

from __future__ import annotations

from datetime import datetime, timezone
import ctypes
import pathlib
import socket
import sys
import time
from typing import Any

import redis
from sqlalchemy import text

from app.core.config import settings
from app.core import minio_client

try:
    import psutil
except ImportError:  # pragma: no cover - optional fallback for minimal local installs
    psutil = None

_last_proc_cpu: tuple[int, int] | None = None
_last_windows_cpu: tuple[int, int] | None = None


def _record_error(errors: list[str], component: str, exc: Exception) -> None:
    errors.append(f"{component}:{type(exc).__name__}")


def _collect_system_metrics(metrics: dict[str, float], errors: list[str]) -> None:
    if psutil is None:
        if sys.platform.startswith("win"):
            _collect_windows_system_metrics(metrics, errors)
        else:
            _collect_proc_system_metrics(metrics, errors)
        return
    try:
        metrics["cpu_percent"] = float(psutil.cpu_percent(interval=None))
        memory = psutil.virtual_memory()
        metrics["memory_percent"] = float(memory.percent)
        metrics["memory_used_bytes"] = float(memory.used)
        metrics["memory_available_bytes"] = float(memory.available)
    except Exception as exc:  # pragma: no cover - depends on host platform
        _record_error(errors, "system", exc)


def _collect_windows_system_metrics(metrics: dict[str, float], errors: list[str]) -> None:
    """Collect CPU and memory metrics without requiring psutil on Windows."""
    global _last_windows_cpu
    try:

        class _FileTime(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]

        idle = _FileTime()
        kernel = _FileTime()
        user = _FileTime()
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            raise OSError(ctypes.get_last_error(), "GetSystemTimes failed")

        def filetime_value(value: _FileTime) -> int:
            return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)

        idle_value = filetime_value(idle)
        total_value = filetime_value(kernel) + filetime_value(user)
        if _last_windows_cpu is not None:
            previous_total, previous_idle = _last_windows_cpu
            total_delta = total_value - previous_total
            idle_delta = idle_value - previous_idle
            if total_delta > 0:
                metrics["cpu_percent"] = max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100))
        _last_windows_cpu = (total_value, idle_value)

        class _MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_uint32),
                ("dwMemoryLoad", ctypes.c_uint32),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        memory = _MemoryStatusEx()
        memory.dwLength = ctypes.sizeof(memory)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            raise OSError(ctypes.get_last_error(), "GlobalMemoryStatusEx failed")
        metrics["memory_percent"] = float(memory.dwMemoryLoad)
        metrics["memory_used_bytes"] = float(memory.ullTotalPhys - memory.ullAvailPhys)
        metrics["memory_available_bytes"] = float(memory.ullAvailPhys)
    except Exception as exc:  # pragma: no cover - depends on Windows APIs
        _record_error(errors, "system", exc)


def _collect_proc_system_metrics(metrics: dict[str, float], errors: list[str]) -> None:
    """Linux fallback so resource data still works before optional psutil is installed."""
    global _last_proc_cpu
    try:
        cpu_line = pathlib.Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
        cpu_values = [int(value) for value in cpu_line.split()[1:]]
        total = sum(cpu_values)
        idle = cpu_values[3] + (cpu_values[4] if len(cpu_values) > 4 else 0)
        if _last_proc_cpu is not None:
            previous_total, previous_idle = _last_proc_cpu
            total_delta = total - previous_total
            idle_delta = idle - previous_idle
            if total_delta > 0:
                metrics["cpu_percent"] = max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100))
        _last_proc_cpu = (total, idle)

        memory: dict[str, int] = {}
        for line in pathlib.Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(":")
            if key in {"MemTotal", "MemAvailable"}:
                memory[key] = int(value.strip().split()[0]) * 1024
        total_bytes = memory.get("MemTotal")
        available_bytes = memory.get("MemAvailable")
        if total_bytes and available_bytes is not None:
            metrics["memory_percent"] = (1 - available_bytes / total_bytes) * 100
            metrics["memory_used_bytes"] = float(total_bytes - available_bytes)
            metrics["memory_available_bytes"] = float(available_bytes)
    except (OSError, IndexError, ValueError, ZeroDivisionError) as exc:
        _record_error(errors, "system", exc)


def _collect_postgres_metrics(metrics: dict[str, float], errors: list[str]) -> None:
    try:
        from app.core.database import sync_engine

        statement = text(
            """
            SELECT
              (SELECT count(*)::float FROM pg_stat_activity) AS connections,
              (SELECT setting::float FROM pg_settings WHERE name = 'max_connections') AS max_connections,
              COALESCE(
                (SELECT sum(blks_hit)::float / NULLIF(sum(blks_hit + blks_read), 0) * 100
                 FROM pg_stat_database),
                0
              ) AS cache_hit_percent
            """
        )
        with sync_engine.connect() as connection:
            row = connection.execute(statement).mappings().one()
        for key, value in (
            ("postgres_connections", row.get("connections")),
            ("postgres_max_connections", row.get("max_connections")),
            ("postgres_cache_hit_percent", row.get("cache_hit_percent")),
        ):
            if isinstance(value, (int, float)):
                metrics[key] = float(value)
    except Exception as exc:
        _record_error(errors, "postgres", exc)


def _redis_url() -> str:
    auth = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
    return f"redis://{auth}{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"


def _collect_redis_metrics(metrics: dict[str, float], errors: list[str]) -> None:
    client: redis.Redis | None = None
    try:
        client = redis.Redis.from_url(
            _redis_url(),
            decode_responses=True,
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
        )
        info = client.info()
        for key, metric_name in (
            ("connected_clients", "redis_connected_clients"),
            ("used_memory", "redis_used_memory_bytes"),
            ("used_memory_peak", "redis_used_memory_peak_bytes"),
            ("instantaneous_ops_per_sec", "redis_ops_per_second"),
            ("blocked_clients", "redis_blocked_clients"),
        ):
            value = info.get(key)
            if isinstance(value, (int, float)):
                metrics[metric_name] = float(value)
    except Exception as exc:
        _record_error(errors, "redis", exc)
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def _collect_minio_metrics(metrics: dict[str, float], errors: list[str], include_inventory: bool) -> None:
    started = time.perf_counter()
    try:
        client = minio_client.get_client()
        reachable = client.bucket_exists(settings.MINIO_BUCKET)
        metrics["minio_reachable"] = 1.0 if reachable else 0.0
        metrics["minio_probe_ms"] = (time.perf_counter() - started) * 1000
        if not reachable or not include_inventory:
            return

        objects = 0
        total_bytes = 0
        for item in client.list_objects(settings.MINIO_BUCKET, recursive=True):
            objects += 1
            total_bytes += int(getattr(item, "size", 0) or 0)
            if objects >= settings.STORAGE_ALERT_MAX_SCAN_OBJECTS:
                break
        metrics["minio_object_count"] = float(objects)
        metrics["minio_total_bytes"] = float(total_bytes)
    except Exception as exc:
        _record_error(errors, "minio", exc)
        metrics["minio_probe_ms"] = (time.perf_counter() - started) * 1000


class PerformanceResourceSampler:
    """Collect one timestamped sample without allowing dependency outages to stop k6."""

    def __init__(self) -> None:
        self.node_id = socket.gethostname()[:128] or "unknown"
        self._last_inventory_at = 0.0

    def sample(self) -> dict[str, Any]:
        metrics: dict[str, float] = {}
        errors: list[str] = []
        _collect_system_metrics(metrics, errors)
        _collect_postgres_metrics(metrics, errors)
        _collect_redis_metrics(metrics, errors)

        now = time.monotonic()
        include_inventory = now - self._last_inventory_at >= max(
            1, settings.PERFORMANCE_MINIO_INVENTORY_INTERVAL_SECONDS
        )
        _collect_minio_metrics(metrics, errors, include_inventory)
        if include_inventory:
            self._last_inventory_at = now

        try:
            from app.core.metrics import PERFORMANCE_RESOURCE

            for name, value in metrics.items():
                PERFORMANCE_RESOURCE.labels(node=self.node_id, metric=name).set(value)
        except Exception:
            pass

        return {
            "captured_at": datetime.now(timezone.utc),
            "node_id": self.node_id,
            "source": "performance-worker",
            "metrics": metrics,
            "errors": errors,
        }
