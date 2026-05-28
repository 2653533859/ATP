"""ADB 自愈抽象层

为 Android 真机 / Mobile Special 执行器提供：
  - ensure_reachable: 探测设备可达性，失败时自动 disconnect + connect + 退避重试
  - safe_run_adb: 包装 subprocess.run，非零或 TimeoutExpired 时调用 ensure_reachable 后重试
  - HeartbeatMonitor: 异步上下文，周期探测设备状态；连续失败触发 on_lost 回调

设计原则：
  - 任何一步都不主动 kill 调用方进程；HeartbeatMonitor 只通知，回收交给调用方
  - 所有外部行为可被 ADB_* 配置开关一键关闭，确保向后兼容
  - serial 形如 "ip:port" 才会尝试 disconnect/connect；USB serial 仅做探活
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, Sequence

from app.core.config import settings
from app.core.metrics import (
    ADB_ENSURE_REACHABLE_DURATION,
    ADB_HEARTBEAT_LOST_TOTAL,
    ADB_RECONNECT_TOTAL,
)

logger = logging.getLogger(__name__)

# safe_run_adb 在 subprocess.TimeoutExpired 时返回的占位 CompletedProcess 使用这两个哨兵。
# 调用方应通过这些常量识别"adb 命令超时"语义，而不是依赖魔法字符串。
ADB_TIMEOUT_RETURNCODE = -1
ADB_TIMEOUT_SENTINEL = "__adb_timeout__"


def is_adb_timeout(proc: subprocess.CompletedProcess | None) -> bool:
    """判断 CompletedProcess 是否为 safe_run_adb 的超时占位结果。"""
    return (
        proc is not None
        and proc.returncode == ADB_TIMEOUT_RETURNCODE
        and (proc.stderr or "") == ADB_TIMEOUT_SENTINEL
    )


def _is_tcp_serial(serial: str) -> bool:
    """判断 serial 是否为 ip:port 形式"""
    if not serial or ":" not in serial:
        return False
    host, _, port = serial.rpartition(":")
    if not host or not port:
        return False
    return port.isdigit()


def _parse_backoff_ms(raw: str) -> list[int]:
    """解析逗号分隔的退避毫秒列表，非法值时回退默认"""
    try:
        result = [int(x.strip()) for x in raw.split(",") if x.strip()]
        return result or [200, 800, 2000]
    except ValueError:
        return [200, 800, 2000]


def _run_adb_raw(args: Sequence[str], timeout: int) -> tuple[int | None, str, str]:
    """同步执行 adb 命令，返回 (returncode, stdout, stderr)；FileNotFoundError 时 returncode=None"""
    cmd = ["adb", *args]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except FileNotFoundError:
        return None, "", "adb_not_found"
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"


def _try_reconnect(serial: str, timeout: int = 5) -> tuple[bool, str]:
    """对 TCP serial 执行 disconnect + connect；返回 (ok, detail)"""
    if not _is_tcp_serial(serial):
        return False, "not_tcp_serial"
    _run_adb_raw(["disconnect", serial], timeout=timeout)
    rc, stdout, stderr = _run_adb_raw(["connect", serial], timeout=timeout)
    combined = (stdout + " " + stderr).lower()
    if rc == 0 and ("connected" in combined or "already connected" in combined):
        return True, "reconnected"
    if rc is None:
        return False, "adb_not_found"
    return False, (stdout or stderr or "unknown")[:200]


def _classify_state(rc: int | None, stdout: str, stderr: str, serial: str) -> tuple[bool, str]:
    """根据 adb get-state 输出判定设备状态"""
    if rc is None:
        return False, "adb 命令未找到，请确认 worker 镜像或本地环境已安装 adb"
    if rc == -1:
        return False, f"检查设备 {serial} 状态超时"
    if rc == 0 and stdout == "device":
        return True, "设备在线"
    if stdout == "offline":
        return False, f"设备 {serial} 当前处于 offline"
    if stdout == "unauthorized":
        return False, f"设备 {serial} 未授权，请在手机上确认 USB 调试授权"
    return False, f"设备 {serial} 不可用：{stderr or stdout or '未知状态'}"


def ensure_reachable(
    serial: str,
    *,
    max_attempts: int | None = None,
    reconnect: bool | None = None,
    timeout: int = 10,
) -> tuple[bool, str]:
    """探测设备可达；失败时（仅当 TCP serial 且 reconnect 开启）自动 disconnect/connect 重试。

    Args:
        serial: 设备 serial
        max_attempts: 总尝试次数；None 时取 settings.ADB_RECONNECT_MAX_ATTEMPTS
        reconnect: 是否启用自动重连；None 时取 settings.ADB_RECONNECT_ENABLED
        timeout: 单次 get-state 超时（秒）

    Returns:
        (ok, message)
    """
    if max_attempts is None:
        max_attempts = max(1, settings.ADB_RECONNECT_MAX_ATTEMPTS)
    if reconnect is None:
        reconnect = settings.ADB_RECONNECT_ENABLED

    backoff_ms = _parse_backoff_ms(settings.ADB_RECONNECT_BACKOFF_MS)
    last_message = "未尝试"
    attempts_history: list[str] = []
    start_ts = time.monotonic()
    result_label = "failure"

    try:
        for attempt in range(max_attempts):
            rc, stdout, stderr = _run_adb_raw(["-s", serial, "get-state"], timeout=timeout)
            ok, message = _classify_state(rc, stdout, stderr, serial)
            if ok:
                result_label = "success"
                if attempt == 0:
                    return True, message
                return True, f"{message}（重连后恢复，尝试 {attempt + 1} 次）"

            last_message = message
            attempts_history.append(f"#{attempt + 1}: {message}")
            # adb 不存在或未授权不重试
            if "adb 命令未找到" in message:
                result_label = "adb_not_found"
                break
            if "未授权" in message:
                # 未授权不可自动恢复，归类为 failure
                break
            if attempt >= max_attempts - 1:
                break
            if reconnect and _is_tcp_serial(serial):
                reconnected, detail = _try_reconnect(serial)
                attempts_history.append(f"reconnect: {detail}")
                if not reconnected and detail == "adb_not_found":
                    result_label = "adb_not_found"
                    break
            elif not _is_tcp_serial(serial):
                # USB serial 无法自动重连，标记为 not_tcp_serial（区分于普通 failure）
                result_label = "not_tcp_serial"
            # 退避
            backoff_index = min(attempt, len(backoff_ms) - 1)
            time.sleep(backoff_ms[backoff_index] / 1000)

        return False, f"{last_message}（共尝试 {max_attempts} 次）"
    finally:
        try:
            ADB_RECONNECT_TOTAL.labels(result=result_label).inc()
            ADB_ENSURE_REACHABLE_DURATION.observe(time.monotonic() - start_ts)
        except Exception:
            # 指标埋点失败不应影响主流程
            logger.debug("ensure_reachable metric emit failed", exc_info=True)


def safe_run_adb(
    serial: str | None,
    args: Sequence[str],
    *,
    timeout: int = 15,
    retries: int = 1,
    reconnect: bool | None = None,
) -> subprocess.CompletedProcess | None:
    """带重试的 adb 命令执行。

    Args:
        serial: 目标设备 serial；为 None 时不做 ensure_reachable，仅执行
        args: 不含 "adb" 前缀的参数列表（例如 ["shell", "getprop", "ro.product.model"]）
        timeout: 单次执行超时
        retries: 额外重试次数（0 表示只执行 1 次）
        reconnect: 重试前是否调用 ensure_reachable 自愈

    Returns:
        CompletedProcess（成功或最后一次失败），adb 不存在时返回 None
    """
    cmd = ["adb", "-s", serial, *args] if serial else ["adb", *args]
    last_proc: subprocess.CompletedProcess | None = None
    attempts = max(1, retries + 1)

    for attempt in range(attempts):
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            last_proc = proc
            if proc.returncode == 0:
                return proc
        except FileNotFoundError:
            logger.warning("adb binary not found on PATH")
            return None
        except subprocess.TimeoutExpired:
            last_proc = subprocess.CompletedProcess(
                cmd, returncode=ADB_TIMEOUT_RETURNCODE, stdout="", stderr=ADB_TIMEOUT_SENTINEL,
            )

        if attempt >= attempts - 1:
            break
        if serial and (reconnect if reconnect is not None else settings.ADB_RECONNECT_ENABLED):
            ok, message = ensure_reachable(serial)
            if not ok:
                logger.warning(
                    "safe_run_adb retry skipped: device %s still unreachable: %s",
                    serial, message,
                )
                break

    return last_proc


class HeartbeatMonitor:
    """异步设备心跳监控。

    用法：
        async with HeartbeatMonitor(serial, on_lost=callback) as hb:
            await long_running_work()
            if hb.lost:
                ...  # 调用方自行回收

    回调 on_lost 在心跳判定设备失联时触发一次（同一上下文内不会重复触发）。
    回调可为同步或异步函数；异步函数会被 await。
    回调中抛出的异常会被吞掉并记入 logger，不影响业务执行。
    """

    def __init__(
        self,
        serial: str | None,
        *,
        on_lost: Callable[[str], None | Awaitable[None]] | None = None,
        interval_sec: int | None = None,
        failure_threshold: int | None = None,
        enabled: bool | None = None,
        executor_label: str = "unknown",
    ) -> None:
        self.serial = serial
        self.on_lost = on_lost
        self.interval_sec = (
            interval_sec
            if interval_sec is not None
            else settings.ADB_HEARTBEAT_INTERVAL_SEC
        )
        self.failure_threshold = max(
            1,
            failure_threshold
            if failure_threshold is not None
            else settings.ADB_HEARTBEAT_FAILURE_THRESHOLD,
        )
        self._enabled = (
            enabled
            if enabled is not None
            else (settings.ADB_HEARTBEAT_ENABLED and bool(serial))
        )
        self._executor_label = executor_label
        self.lost: bool = False
        self.lost_reason: str | None = None
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event = asyncio.Event()
        self._failure_count: int = 0
        self._triggered: bool = False

    async def __aenter__(self) -> "HeartbeatMonitor":
        if self._enabled and self.serial:
            self._task = asyncio.create_task(self._run())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._stop_event.set()
        task = self._task
        if task is None:
            return
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                logger.debug("HeartbeatMonitor task cancelled on exit", exc_info=True)
        except asyncio.CancelledError:
            # 任务已被外部取消
            pass
        except Exception:
            logger.debug("HeartbeatMonitor task error on exit", exc_info=True)

    async def _run(self) -> None:
        loop = asyncio.get_event_loop()
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.interval_sec
                )
                break  # 收到停止信号
            except asyncio.TimeoutError:
                pass

            if self._stop_event.is_set():
                break

            try:
                ok, message = await loop.run_in_executor(
                    None, lambda: ensure_reachable(self.serial, max_attempts=1, reconnect=False)
                )
            except Exception as e:
                logger.debug("heartbeat probe error: %s", e)
                ok, message = False, "probe_exception"

            if ok:
                self._failure_count = 0
                continue

            self._failure_count += 1
            logger.warning(
                "HeartbeatMonitor: %s probe failure %d/%d (%s)",
                self.serial, self._failure_count, self.failure_threshold, message,
            )
            if self._failure_count >= self.failure_threshold and not self._triggered:
                self._triggered = True
                self.lost = True
                self.lost_reason = message
                try:
                    ADB_HEARTBEAT_LOST_TOTAL.labels(executor=self._executor_label).inc()
                except Exception:
                    logger.debug("HeartbeatMonitor metric emit failed", exc_info=True)
                if self.on_lost is not None:
                    try:
                        result = self.on_lost(message)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        logger.exception("HeartbeatMonitor on_lost callback error")
                # 触发后停止心跳；调用方负责回收
                break


__all__ = [
    "ensure_reachable",
    "safe_run_adb",
    "HeartbeatMonitor",
    "ADB_TIMEOUT_RETURNCODE",
    "ADB_TIMEOUT_SENTINEL",
    "is_adb_timeout",
]
