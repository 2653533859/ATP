"""AdbKeeper - 维护本机 adb server 与远程设备隧道端口的连接状态。

职责：
- 隧道就绪（Agent 在线且设备已开监听）→ ``adb connect 127.0.0.1:<port>``（幂等）
- ``adb devices`` 中隧道设备状态为 offline → 先 disconnect 再 connect 修复
- 隧道不再存在（Agent 失联/设备拔出）→ ``adb disconnect`` 清理条目
- 周期兜底巡检 + Hub 事件触发即时同步

只管理本模块端口范围（28100-28199）内的 127.0.0.1 条目，不触碰其他设备。
"""

import asyncio
import logging
from typing import Callable, Dict, Optional, Set

from app.device_agents.protocol import parse_tunnel_serial, tunnel_serial

logger = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = 10
ADB_COMMAND_TIMEOUT_SECONDS = 10

_LEAVE_ALONE_STATES = {"unauthorized", "authorizing", "connecting"}


async def _run_adb_command(*args: str, timeout: int = ADB_COMMAND_TIMEOUT_SECONDS) -> str:
    """异步执行 adb 命令，返回 stdout 文本；失败抛 RuntimeError。"""
    cmd = ["adb"] + list(args)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        raise RuntimeError(f"adb command timed out: {' '.join(cmd)}")
    if proc.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"adb error (rc={proc.returncode}): {err_msg}")
    return stdout.decode("utf-8", errors="replace")


def parse_adb_devices_tunnel_states(output: str) -> Dict[int, str]:
    """从 ``adb devices`` 输出提取隧道端口范围内条目：port -> 状态。"""
    states: Dict[int, str] = {}
    for line in str(output or "").strip().splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        port = parse_tunnel_serial(parts[0])
        if port is not None:
            states[port] = parts[1]
    return states


class AdbKeeper:
    """后台协程：把 adb server 的隧道连接收敛到期望状态。"""

    def __init__(self):
        self._desired_provider: Optional[Callable[[], Set[int]]] = None
        self._wake: Optional[asyncio.Event] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def configure(self, desired_provider: Callable[[], Set[int]]) -> None:
        self._desired_provider = desired_provider

    def start_in_loop(self) -> None:
        """在当前事件循环中启动巡检任务。"""
        if self._running:
            return
        loop = asyncio.get_running_loop()
        self._running = True
        self._wake = asyncio.Event()
        self._wake.set()
        self._task = loop.create_task(self._loop(), name="device-agent-adb-keeper")
        logger.info("adb keeper 已启动")

    def stop(self) -> None:
        self._running = False
        if self._wake is not None:
            self._wake.set()
        if self._task is not None and not self._task.done():
            self._task.cancel()
            self._task = None

    def trigger(self) -> None:
        """隧道状态变更（新设备上线/下线/Agent 连接）时唤醒即时同步。"""
        if self._wake is not None:
            self._wake.set()

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.reconcile_once()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("adb keeper 单次收敛异常")

            if not self._running:
                break

            if self._wake is None:
                await asyncio.sleep(SYNC_INTERVAL_SECONDS)
                continue

            try:
                await asyncio.wait_for(self._wake.wait(), timeout=SYNC_INTERVAL_SECONDS)
                self._wake.clear()
            except asyncio.TimeoutError:
                pass

    async def reconcile_once(self) -> None:
        """执行单次收敛对齐。"""
        if self._desired_provider is None:
            return
        desired_ports = set(self._desired_provider() or set())
        try:
            output = await _run_adb_command("devices")
        except RuntimeError as exc:
            logger.debug("adb devices 执行失败（跳过本次收敛）: %s", exc)
            return

        current_states = parse_adb_devices_tunnel_states(output)

        # 1. 清理不再期望的条目（设备拔出/Agent 离线）
        to_disconnect = set(current_states.keys()) - desired_ports
        for port in to_disconnect:
            await self._adb_disconnect(tunnel_serial(port))

        # 2. 对期望保持连接的端口收敛状态
        for port in desired_ports:
            serial = tunnel_serial(port)
            state = current_states.get(port)
            if state is None:
                # 尚未连接：尝试 connect
                await self._adb_connect(serial)
            elif state in _LEAVE_ALONE_STATES:
                pass
            elif state == "device":
                pass
            else:
                # offline 或其他异常状态：先 disconnect 再 connect 重试
                logger.info("隧道设备 %s 状态为 %s，尝试重启连接", serial, state)
                await self._adb_disconnect(serial)
                await self._adb_connect(serial)

    async def _adb_connect(self, serial: str) -> None:
        try:
            out = await _run_adb_command("connect", serial)
            logger.debug("adb connect %s: %s", serial, out.strip())
        except RuntimeError as exc:
            logger.warning("adb connect %s 失败: %s", serial, exc)

    async def _adb_disconnect(self, serial: str) -> None:
        try:
            await _run_adb_command("disconnect", serial)
            logger.debug("adb disconnect %s 成功", serial)
        except RuntimeError as exc:
            logger.debug("adb disconnect %s 失败: %s", serial, exc)


adb_keeper = AdbKeeper()
