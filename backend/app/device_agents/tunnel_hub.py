"""TunnelHub - 远程设备接入点（Agent）会话与反向隧道管理。

拓扑（B→A 单向可达）：

    A 的 adb server ⇄ 127.0.0.1:<tunnel_port>（本模块 asyncio TCP 中继）
      ⇄ WebSocket（Agent 从 B 主动外连 A）
      ⇄ B 上 Agent ⇄ 127.0.0.1:<forward端口>（B 的 adb forward）⇄ USB ⇄ 手机 adbd

每个 Agent 一条 WebSocket：控制消息走 JSON text 帧，隧道数据走 binary 帧
（4 字节大端 conn_id + payload）。设备的隧道端口按 (agent, usb_serial)
持久化在 RemoteAgentDevice 表，保证 adb serial（127.0.0.1:<port>）跨重启稳定。
"""

import asyncio
import json
import logging
import socket
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.core.database import sync_engine as engine
from app.models.device import Device, DeviceStatus
from app.models.device_agent import RemoteAgent, RemoteAgentDevice
from app.device_agents.protocol import (
    AGENT_PROTOCOL_VERSION,
    MAX_DATA_PAYLOAD,
    TUNNEL_HOST,
    TUNNEL_PORT_RANGE_END,
    TUNNEL_PORT_RANGE_START,
    decode_data_frame,
    encode_data_frame,
    parse_tunnel_serial,
    tunnel_serial,
)

logger = logging.getLogger(__name__)

SESSION_IDLE_TIMEOUT_SECONDS = 45
REGISTER_TIMEOUT_SECONDS = 15
LAST_SEEN_WRITE_INTERVAL_SECONDS = 30
TCP_READ_CHUNK = 64 * 1024
TUNNEL_SEND_CHUNK_BYTES = 8 * 1024
TUNNEL_CONNECTION_MAX_PENDING_BYTES = 256 * 1024
TUNNEL_CONNECTION_MAX_INBOUND_CHUNKS = 32

BANDWIDTH_PROBE_DEFAULT_BYTES = 1_000_000
BANDWIDTH_PROBE_TIMEOUT_SECONDS = 20.0


class _LinkRateWindow:
    """滚动窗口字节速率统计（按秒分桶）。"""

    def __init__(self, window_seconds: int = 10):
        self._window = window_seconds
        self._buckets: Deque[Tuple[int, int]] = deque()

    def record(self, nbytes: int) -> None:
        now_s = int(time.time())
        cutoff = now_s - self._window
        while self._buckets and self._buckets[0][0] <= cutoff:
            self._buckets.popleft()
        if self._buckets and self._buckets[-1][0] == now_s:
            second, value = self._buckets[-1]
            self._buckets[-1] = (second, value + nbytes)
        else:
            self._buckets.append((now_s, nbytes))

    def rate_bps(self) -> int:
        cutoff = int(time.time()) - self._window
        window_bytes = sum(value for second, value in list(self._buckets) if second > cutoff)
        return int(window_bytes * 8 / self._window)


class TunnelConnection:
    """一条经隧道中继的 TCP 连接（A 的 adb server → 本机监听端口）。"""

    def __init__(self, conn_id: int, usb_serial: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.conn_id = conn_id
        self.usb_serial = usb_serial
        self.reader = reader
        self.writer = writer
        self.pump_task: Optional[asyncio.Task] = None
        self.writer_task: Optional[asyncio.Task] = None
        self.write_queue: "asyncio.Queue[bytes]" = asyncio.Queue(maxsize=TUNNEL_CONNECTION_MAX_INBOUND_CHUNKS)
        self.closed = False


class RemoteDeviceRuntime:
    """一台远程设备在平台进程内的运行时状态。"""

    def __init__(self, usb_serial: str, tunnel_port: int, meta: Dict[str, Any]):
        self.usb_serial = usb_serial
        self.tunnel_port = tunnel_port
        self.meta = dict(meta)
        self.listener: Optional[asyncio.Server] = None
        self.error: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self.listener is not None and self.error is None


class AgentSession:
    """一个在线 Agent（一条 WebSocket）的运行时状态。"""

    def __init__(self, hub: "TunnelHub", websocket: WebSocket, name: str, agent_id: int):
        self.hub = hub
        self.websocket = websocket
        self.name = name
        self.agent_id = agent_id
        self.devices: Dict[str, RemoteDeviceRuntime] = {}
        self.conns: Dict[int, TunnelConnection] = {}
        self._next_conn_id = 1
        self.closed = False

        self.inbound_rate = _LinkRateWindow()
        self.outbound_rate = _LinkRateWindow()
        self.link_rtt_ms: Optional[float] = None
        self.link_rtt_samples: Deque[float] = deque(maxlen=10)
        self.bandwidth_probe: Optional[Dict[str, Any]] = None
        self._next_probe_id = 1
        self._probe_futures: Dict[int, asyncio.Future] = {}
        self._last_seen_written: float = time.monotonic()

        self._send_condition = asyncio.Condition()
        self._control_queue: Deque[Tuple[str, asyncio.Future]] = deque()
        self._data_queues: Dict[int, Deque[bytes]] = {}
        self._data_pending_bytes: Dict[int, int] = {}
        self._round_robin_connections: Deque[int] = deque()
        self._closed_connections: Set[int] = set()
        self._sender_task: Optional[asyncio.Task] = None

    def allocate_conn_id(self) -> int:
        cid = self._next_conn_id
        self._next_conn_id = (self._next_conn_id + 1) & 0x7FFFFFFF or 1
        return cid

    async def send_control(self, payload: Dict[str, Any]) -> None:
        future = asyncio.get_running_loop().create_future()
        text_payload = json.dumps(payload, ensure_ascii=False)
        async with self._send_condition:
            if self.closed:
                raise ConnectionError("Agent 会话已关闭")
            self._control_queue.append((text_payload, future))
            self._ensure_sender_locked()
            self._send_condition.notify_all()
        await future

    async def send_data(self, conn_id: int, chunk: bytes) -> None:
        async with self._send_condition:
            if self.closed:
                raise ConnectionError("Agent 会话已关闭")
            if conn_id in self._closed_connections:
                return

            pending = self._data_pending_bytes.get(conn_id, 0)
            while (
                not self.closed
                and conn_id not in self._closed_connections
                and pending >= TUNNEL_CONNECTION_MAX_PENDING_BYTES
            ):
                await self._send_condition.wait()
                pending = self._data_pending_bytes.get(conn_id, 0)

            if self.closed or conn_id in self._closed_connections:
                return

            queue_for_connection = self._data_queues.setdefault(conn_id, deque())
            if not queue_for_connection:
                self._round_robin_connections.append(conn_id)
            queue_for_connection.append(chunk)
            self._data_pending_bytes[conn_id] = pending + len(chunk)
            self._ensure_sender_locked()
            self._send_condition.notify_all()

    async def discard_connection_data(self, conn_id: int) -> None:
        async with self._send_condition:
            self._closed_connections.add(conn_id)
            self._data_queues.pop(conn_id, None)
            self._data_pending_bytes.pop(conn_id, None)
            self._send_condition.notify_all()

    async def shutdown_sender(self) -> None:
        async with self._send_condition:
            self.closed = True
            error = ConnectionError("Agent 会话已关闭")
            while self._control_queue:
                _, future = self._control_queue.popleft()
                if not future.done():
                    future.set_exception(error)
            self._data_queues.clear()
            self._data_pending_bytes.clear()
            self._round_robin_connections.clear()
            self._send_condition.notify_all()
            sender_task = self._sender_task
            self._sender_task = None
        if sender_task is not None and sender_task is not asyncio.current_task():
            sender_task.cancel()
            try:
                await sender_task
            except asyncio.CancelledError:
                pass

    def _ensure_sender_locked(self) -> None:
        if self._sender_task is None or self._sender_task.done():
            self._sender_task = asyncio.create_task(self._sender_loop(), name=f"AgentTunnelSender-{self.name}")

    async def _sender_loop(self) -> None:
        try:
            while True:
                control_future: Optional[asyncio.Future] = None
                text_payload: Optional[str] = None
                binary_payload: Optional[bytes] = None
                async with self._send_condition:
                    while not self.closed and not self._control_queue and not self._round_robin_connections:
                        await self._send_condition.wait()
                    if self.closed:
                        return

                    if self._control_queue:
                        text_payload, control_future = self._control_queue.popleft()
                    else:
                        conn_id = self._round_robin_connections.popleft()
                        queue_for_connection = self._data_queues.get(conn_id)
                        if not queue_for_connection:
                            continue
                        pending = queue_for_connection.popleft()
                        chunk = pending[:TUNNEL_SEND_CHUNK_BYTES]
                        remainder = pending[TUNNEL_SEND_CHUNK_BYTES:]
                        if remainder:
                            queue_for_connection.appendleft(remainder)
                        if queue_for_connection:
                            self._round_robin_connections.append(conn_id)
                        else:
                            self._data_queues.pop(conn_id, None)
                        self._data_pending_bytes[conn_id] = max(
                            0, self._data_pending_bytes.get(conn_id, 0) - len(chunk)
                        )
                        if self._data_pending_bytes.get(conn_id) == 0:
                            self._data_pending_bytes.pop(conn_id, None)
                        self._send_condition.notify_all()
                        binary_payload = encode_data_frame(conn_id, chunk)

                try:
                    if text_payload is not None:
                        await self.websocket.send_text(text_payload)
                        self.outbound_rate.record(len(text_payload))
                    elif binary_payload is not None:
                        await self.websocket.send_bytes(binary_payload)
                        self.outbound_rate.record(len(binary_payload))
                    if control_future is not None and not control_future.done():
                        control_future.set_result(None)
                except Exception as exc:
                    if control_future is not None and not control_future.done():
                        control_future.set_exception(exc)
                    logger.info("Agent 隧道发送失败: name=%s error=%s", self.name, exc)
                    await self.shutdown_sender()
                    try:
                        await self.websocket.close()
                    except Exception:
                        pass
                    return
        except asyncio.CancelledError:
            raise


class TunnelHub:
    """Agent 会话与隧道监听的全局管理器（单例 ``tunnel_hub``）。"""

    def __init__(self):
        self._sessions: Dict[str, AgentSession] = {}
        self._lock = asyncio.Lock()
        self._keeper = None

    def set_keeper(self, keeper) -> None:
        self._keeper = keeper

    def startup_reset(self) -> None:
        """进程启动时把库里所有接入点标记为 OFFLINE。"""
        try:
            with Session(engine) as session:
                agents = session.scalars(select(RemoteAgent)).all()
                now = datetime.now(timezone.utc)
                for agent in agents:
                    if agent.status != "OFFLINE":
                        agent.status = "OFFLINE"
                        agent.updated_at = now
                        session.add(agent)
                remote_devs = session.scalars(select(Device).where(Device.ip_address == "127.0.0.1")).all()
                for dev in remote_devs:
                    if parse_tunnel_serial(dev.serial) is not None:
                        dev.status = DeviceStatus.offline
                        dev.last_seen_at = now
                        session.add(dev)
                session.commit()
        except Exception:
            logger.exception("重置远程接入点状态失败")

    async def shutdown(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
        for agent_session in sessions:
            await self._teardown_session(agent_session, reason="server shutdown")

    def desired_ports(self) -> Set[int]:
        """当前应保持 adb connect 的隧道端口集合。"""
        ports: Set[int] = set()
        for agent_session in self._sessions.values():
            for device in agent_session.devices.values():
                if device.ready:
                    ports.add(device.tunnel_port)
        return ports

    def list_agents(self) -> List[Dict[str, Any]]:
        """接入点列表（数据库记录 + 在线会话叠加），供 REST 展示。"""
        result: List[Dict[str, Any]] = []
        try:
            with Session(engine) as session:
                agents = session.scalars(select(RemoteAgent)).all()
                for agent in agents:
                    live = self._sessions.get(agent.name)
                    devices: List[Dict[str, Any]] = []
                    mappings = session.scalars(
                        select(RemoteAgentDevice).where(RemoteAgentDevice.agent_id == agent.id)
                    ).all()
                    live_serials = set(live.devices.keys()) if live else set()
                    for mapping in mappings:
                        runtime = live.devices.get(mapping.usb_serial) if live else None
                        devices.append(
                            {
                                "usb_serial": mapping.usb_serial,
                                "tunnel_port": mapping.tunnel_port,
                                "serial": tunnel_serial(mapping.tunnel_port),
                                "model": mapping.model,
                                "brand": mapping.brand,
                                "os_version": mapping.os_version,
                                "online": bool(runtime and runtime.ready),
                                "error": runtime.error if runtime else None,
                                "last_seen_at": mapping.last_seen_at.isoformat() if mapping.last_seen_at else None,
                            }
                        )
                    if live:
                        known = {d["usb_serial"] for d in devices}
                        for usb_serial in live_serials - known:
                            runtime = live.devices[usb_serial]
                            devices.append(
                                {
                                    "usb_serial": usb_serial,
                                    "tunnel_port": runtime.tunnel_port,
                                    "serial": tunnel_serial(runtime.tunnel_port),
                                    "model": runtime.meta.get("model"),
                                    "brand": runtime.meta.get("brand"),
                                    "os_version": runtime.meta.get("os_version"),
                                    "online": runtime.ready,
                                    "error": runtime.error,
                                    "last_seen_at": None,
                                }
                            )
                    result.append(
                        {
                            "id": agent.id,
                            "name": agent.name,
                            "status": "ONLINE" if live else "OFFLINE",
                            "agent_version": agent.agent_version,
                            "os_info": agent.os_info,
                            "last_seen_at": agent.last_seen_at.isoformat() if agent.last_seen_at else None,
                            "created_at": agent.created_at.isoformat() if agent.created_at else None,
                            "device_count": len(devices),
                            "online_device_count": sum(1 for d in devices if d["online"]),
                            "devices": devices,
                            "link_quality": self._link_quality_snapshot(live),
                        }
                    )
        except Exception:
            logger.exception("获取接入点列表失败")
        return result

    def is_agent_online(self, name: str) -> bool:
        return name in self._sessions

    async def probe_agent_bandwidth(
        self,
        agent_id: int,
        size_bytes: int = BANDWIDTH_PROBE_DEFAULT_BYTES,
        timeout: float = BANDWIDTH_PROBE_TIMEOUT_SECONDS,
    ) -> Dict[str, Any]:
        """主动测量 B→A 上行吞吐。"""
        async with self._lock:
            agent_session = next((s for s in self._sessions.values() if s.agent_id == agent_id), None)
        if agent_session is None or agent_session.closed:
            raise ValueError("接入点不在线，无法探测")

        probe_id = agent_session._next_probe_id
        agent_session._next_probe_id += 1
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        agent_session._probe_futures[probe_id] = future
        started = time.monotonic()
        await agent_session.send_control({"type": "bandwidth_probe", "probe_id": probe_id, "size": int(size_bytes)})
        try:
            payload_bytes = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            agent_session._probe_futures.pop(probe_id, None)
            raise TimeoutError("Agent 未在时限内回传探测数据")
        elapsed = max(time.monotonic() - started, 1e-6)
        rtt_seconds = (agent_session.link_rtt_ms or 0.0) / 1000.0
        transfer_seconds = max(elapsed - rtt_seconds, 1e-6)
        result = {
            "bps": int(payload_bytes * 8 / transfer_seconds),
            "bytes": int(payload_bytes),
            "elapsed_ms": int(elapsed * 1000),
            "rtt_ms_at_probe": agent_session.link_rtt_ms,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        agent_session.bandwidth_probe = result
        return result

    @staticmethod
    def _link_quality_snapshot(agent_session: Optional["AgentSession"]) -> Optional[Dict[str, Any]]:
        if agent_session is None or agent_session.closed:
            return None
        samples = list(agent_session.link_rtt_samples)
        return {
            "rtt_ms": agent_session.link_rtt_ms,
            "rtt_avg_ms": round(sum(samples) / len(samples), 1) if samples else None,
            "up_bps": agent_session.inbound_rate.rate_bps(),
            "down_bps": agent_session.outbound_rate.rate_bps(),
            "bandwidth_probe": agent_session.bandwidth_probe,
        }

    async def handle_session(self, websocket: WebSocket, token_user: str) -> None:
        """处理一条已通过鉴权的 Agent WebSocket，直到断开。"""
        register = await self._wait_register(websocket)
        if register is None:
            return

        agent_info = register.get("agent") or {}
        name = str(agent_info.get("name") or "").strip()
        if not name or len(name) > 64:
            await self._reject(websocket, "register.agent.name 缺失或过长（≤64 字符）")
            return

        protocol = int(register.get("protocol") or 0)
        if protocol != AGENT_PROTOCOL_VERSION:
            await self._reject(
                websocket,
                f"协议版本不匹配：Agent={protocol} 服务端={AGENT_PROTOCOL_VERSION}，请重新下载 Agent 脚本",
            )
            return

        async with self._lock:
            stale = self._sessions.get(name)
        if stale is not None:
            logger.info("接入点 %s 重复注册，替换旧会话", name)
            await self._teardown_session(stale, reason="replaced by new session")

        agent_id = self._persist_agent_online(name, agent_info, token_user)
        agent_session = AgentSession(self, websocket, name, agent_id)
        async with self._lock:
            self._sessions[name] = agent_session

        logger.info(
            "远程接入点上线: name=%s version=%s os=%s user=%s",
            name,
            agent_info.get("version"),
            agent_info.get("os"),
            token_user,
        )

        try:
            accepted, rejected = await self._apply_device_list(agent_session, register.get("devices") or [])
            await agent_session.send_control(
                {
                    "type": "registered",
                    "protocol": AGENT_PROTOCOL_VERSION,
                    "devices": accepted,
                    "rejected": rejected,
                }
            )
            self._notify_keeper()
            await self._receive_loop(agent_session)
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("接入点 %s 会话异常", name)
        finally:
            await self._teardown_session(agent_session, reason="session ended")

    async def _wait_register(self, websocket: WebSocket) -> Optional[Dict[str, Any]]:
        try:
            message = await asyncio.wait_for(websocket.receive(), timeout=REGISTER_TIMEOUT_SECONDS)
        except (asyncio.TimeoutError, WebSocketDisconnect):
            return None

        if message.get("type") == "websocket.disconnect":
            return None
        text = message.get("text")
        if not text:
            await self._reject(websocket, "首条消息必须是 JSON register")
            return None
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            await self._reject(websocket, "register 消息不是合法 JSON")
            return None
        if payload.get("type") != "register":
            await self._reject(websocket, "首条消息必须是 register")
            return None
        return payload

    async def _reject(self, websocket: WebSocket, reason: str) -> None:
        logger.warning("拒绝 Agent 连接: %s", reason)
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": reason}, ensure_ascii=False))
        except Exception:
            pass
        try:
            await websocket.close(code=4400)
        except Exception:
            pass

    async def _receive_loop(self, agent_session: AgentSession) -> None:
        websocket = agent_session.websocket
        while not agent_session.closed:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=SESSION_IDLE_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                logger.warning("接入点 %s 超时无消息，判定失联", agent_session.name)
                return

            if message.get("type") == "websocket.disconnect":
                return

            data = message.get("bytes")
            if data is not None:
                await self._on_data_frame(agent_session, data)
                continue

            text = message.get("text")
            if text is None:
                continue
            try:
                control = json.loads(text)
            except json.JSONDecodeError:
                logger.warning("接入点 %s 发来非法控制消息，忽略", agent_session.name)
                continue
            await self._on_control(agent_session, control)

    async def _on_control(self, agent_session: AgentSession, control: Dict[str, Any]) -> None:
        msg_type = str(control.get("type") or "")
        if msg_type == "ping":
            self._touch_last_seen(agent_session)
            rtt_raw = control.get("rtt_ms")
            if isinstance(rtt_raw, (int, float)) and 0 <= float(rtt_raw) < 60_000:
                agent_session.link_rtt_ms = float(rtt_raw)
                agent_session.link_rtt_samples.append(float(rtt_raw))
            try:
                await agent_session.send_control({"type": "pong"})
            except Exception:
                pass
        elif msg_type == "bandwidth_probe_result":
            probe_id = int(control.get("probe_id") or 0)
            future = agent_session._probe_futures.pop(probe_id, None)
            if future is not None and not future.done():
                future.set_result(len(str(control.get("payload") or "")))
        elif msg_type == "devices":
            accepted, rejected = await self._apply_device_list(agent_session, control.get("devices") or [])
            try:
                await agent_session.send_control(
                    {
                        "type": "registered",
                        "protocol": AGENT_PROTOCOL_VERSION,
                        "devices": accepted,
                        "rejected": rejected,
                    }
                )
            except Exception:
                pass
            self._notify_keeper()
        elif msg_type == "open_result":
            conn_id = int(control.get("conn_id") or 0)
            if not control.get("ok"):
                await self._close_conn(agent_session, conn_id, notify_agent=False)
        elif msg_type == "close":
            conn_id = int(control.get("conn_id") or 0)
            await self._close_conn(agent_session, conn_id, notify_agent=False)

    async def _on_data_frame(self, agent_session: AgentSession, frame: bytes) -> None:
        agent_session.inbound_rate.record(len(frame))
        try:
            conn_id, payload = decode_data_frame(frame)
        except ValueError:
            return
        if len(payload) > MAX_DATA_PAYLOAD:
            await self._close_conn(agent_session, conn_id, notify_agent=True)
            return
        conn = agent_session.conns.get(conn_id)
        if conn is None or conn.closed:
            try:
                await agent_session.send_control({"type": "close", "conn_id": conn_id})
            except Exception:
                pass
            return
        try:
            conn.write_queue.put_nowait(payload)
        except asyncio.QueueFull:
            await self._close_conn(agent_session, conn_id, notify_agent=True)

    async def _apply_device_list(self, agent_session: AgentSession, raw_devices: List[Dict[str, Any]]):
        reported: Dict[str, Dict[str, Any]] = {}
        for item in raw_devices:
            usb_serial = str((item or {}).get("usb_serial") or "").strip()
            if usb_serial:
                reported[usb_serial] = dict(item)

        accepted: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []

        async with self._lock:
            port_map, alloc_errors = self._persist_device_mappings(agent_session.agent_id, reported)

        for usb_serial, error in alloc_errors.items():
            rejected.append({"usb_serial": usb_serial, "error": error})

        for usb_serial in list(agent_session.devices.keys()):
            if usb_serial not in port_map:
                await self._remove_device_runtime(agent_session, usb_serial)

        for usb_serial, port in port_map.items():
            meta = reported.get(usb_serial) or {}
            runtime = agent_session.devices.get(usb_serial)
            if runtime is None:
                runtime = RemoteDeviceRuntime(usb_serial, port, meta)
                agent_session.devices[usb_serial] = runtime
                await self._start_listener(agent_session, runtime)
            else:
                runtime.meta = dict(meta)
            entry = {"usb_serial": usb_serial, "tunnel_port": port, "serial": tunnel_serial(port)}
            if runtime.error:
                entry["error"] = runtime.error
            accepted.append(entry)

        return accepted, rejected

    async def _start_listener(self, agent_session: AgentSession, runtime: RemoteDeviceRuntime) -> None:
        port = runtime.tunnel_port

        async def _on_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            await self._handle_tunnel_client(agent_session, runtime, reader, writer)

        try:
            server = await asyncio.start_server(_on_client, TUNNEL_HOST, port)
        except OSError as exc:
            runtime.error = f"隧道端口 {port} 监听失败: {exc}"
            logger.error("%s（agent=%s usb_serial=%s）", runtime.error, agent_session.name, runtime.usb_serial)
            return
        runtime.listener = server
        runtime.error = None
        logger.info(
            "隧道监听已就绪: agent=%s usb_serial=%s -> %s",
            agent_session.name,
            runtime.usb_serial,
            tunnel_serial(port),
        )

    async def _remove_device_runtime(self, agent_session: AgentSession, usb_serial: str) -> None:
        runtime = agent_session.devices.pop(usb_serial, None)
        if runtime is None:
            return
        if runtime.listener is not None:
            runtime.listener.close()
            try:
                await runtime.listener.wait_closed()
            except Exception:
                pass
            runtime.listener = None
        for conn_id, conn in list(agent_session.conns.items()):
            if conn.usb_serial == usb_serial:
                await self._close_conn(agent_session, conn_id, notify_agent=True)

    async def _handle_tunnel_client(
        self,
        agent_session: AgentSession,
        runtime: RemoteDeviceRuntime,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        if agent_session.closed:
            writer.close()
            return
        try:
            sock = writer.get_extra_info("socket")
            if sock is not None:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        conn_id = agent_session.allocate_conn_id()
        conn = TunnelConnection(conn_id, runtime.usb_serial, reader, writer)
        agent_session.conns[conn_id] = conn
        conn.writer_task = asyncio.create_task(
            self._drain_tunnel_connection(agent_session, conn),
            name=f"AgentTunnelInbound-{agent_session.name}-{conn_id}",
        )
        try:
            await agent_session.send_control({"type": "open", "conn_id": conn_id, "usb_serial": runtime.usb_serial})
        except Exception:
            await self._close_conn(agent_session, conn_id, notify_agent=False)
            return

        conn.pump_task = asyncio.current_task()
        try:
            while not conn.closed:
                data = await reader.read(TCP_READ_CHUNK)
                if not data:
                    break
                await agent_session.send_data(conn_id, data)
        except Exception as exc:
            logger.debug("隧道连接读取结束: agent=%s conn_id=%s error=%s", agent_session.name, conn_id, exc)
        finally:
            if not conn.closed:
                await self._close_conn(agent_session, conn_id, notify_agent=True, cancel_pump=False)

    async def _drain_tunnel_connection(
        self,
        agent_session: AgentSession,
        conn: TunnelConnection,
    ) -> None:
        try:
            while not conn.closed:
                payload = await conn.write_queue.get()
                conn.writer.write(payload)
                await conn.writer.drain()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not conn.closed:
                await self._close_conn(agent_session, conn.conn_id, notify_agent=True)

    async def _close_conn(
        self,
        agent_session: AgentSession,
        conn_id: int,
        *,
        notify_agent: bool,
        cancel_pump: bool = True,
    ) -> None:
        conn = agent_session.conns.pop(conn_id, None)
        if conn is None or conn.closed:
            return
        conn.closed = True
        await agent_session.discard_connection_data(conn_id)
        try:
            conn.writer.close()
        except Exception:
            pass
        if cancel_pump and conn.pump_task is not None and conn.pump_task is not asyncio.current_task():
            conn.pump_task.cancel()
        if conn.writer_task is not None and conn.writer_task is not asyncio.current_task():
            conn.writer_task.cancel()
        if notify_agent and not agent_session.closed:
            try:
                await agent_session.send_control({"type": "close", "conn_id": conn_id})
            except Exception:
                pass

    async def _teardown_session(self, agent_session: AgentSession, *, reason: str) -> None:
        if agent_session.closed:
            return
        agent_session.closed = True
        async with self._lock:
            if self._sessions.get(agent_session.name) is agent_session:
                self._sessions.pop(agent_session.name, None)

        for usb_serial in list(agent_session.devices.keys()):
            await self._remove_device_runtime(agent_session, usb_serial)
        for conn_id in list(agent_session.conns.keys()):
            await self._close_conn(agent_session, conn_id, notify_agent=False)

        for future in agent_session._probe_futures.values():
            if not future.done():
                future.set_exception(ConnectionError("Agent 会话已关闭"))
        agent_session._probe_futures.clear()

        self._persist_agent_offline(agent_session.agent_id)
        await agent_session.shutdown_sender()

        try:
            await agent_session.websocket.close()
        except Exception:
            pass

        self._notify_keeper()
        logger.info("远程接入点下线: name=%s reason=%s", agent_session.name, reason)

    def _persist_agent_online(self, name: str, agent_info: Dict[str, Any], token_user: str) -> int:
        with Session(engine) as session:
            agent = session.scalars(select(RemoteAgent).where(RemoteAgent.name == name)).first()
            now = datetime.now(timezone.utc)
            if agent is None:
                agent = RemoteAgent(name=name)
            agent.status = "ONLINE"
            agent.agent_version = str(agent_info.get("version") or "") or None
            os_info = str(agent_info.get("os") or "") or None
            if os_info:
                agent.os_info = os_info[:120]
            agent.last_seen_at = now
            agent.updated_at = now
            session.add(agent)
            session.commit()
            session.refresh(agent)
            return int(agent.id)

    def _persist_agent_offline(self, agent_id: int) -> None:
        try:
            with Session(engine) as session:
                agent = session.scalar(select(RemoteAgent).where(RemoteAgent.id == agent_id))
                if agent is None:
                    return
                now = datetime.now(timezone.utc)
                agent.status = "OFFLINE"
                agent.last_seen_at = now
                agent.updated_at = now
                session.add(agent)
                mappings = session.scalars(
                    select(RemoteAgentDevice).where(RemoteAgentDevice.agent_id == agent_id)
                ).all()
                serials = [tunnel_serial(m.tunnel_port) for m in mappings]
                if serials:
                    for dev in session.scalars(select(Device).where(Device.serial.in_(serials))).all():
                        dev.status = DeviceStatus.offline
                        dev.last_seen_at = now
                        session.add(dev)
                session.commit()
        except Exception:
            logger.exception("更新接入点离线状态失败: agent_id=%s", agent_id)

    def _persist_device_mappings(self, agent_id: int, reported: Dict[str, Dict[str, Any]]):
        port_map: Dict[str, int] = {}
        errors: Dict[str, str] = {}
        with Session(engine) as session:
            used_ports = {int(row.tunnel_port) for row in session.scalars(select(RemoteAgentDevice)).all()}
            now = datetime.now(timezone.utc)
            for usb_serial, meta in reported.items():
                mapping = session.scalars(
                    select(RemoteAgentDevice).where(
                        RemoteAgentDevice.agent_id == agent_id,
                        RemoteAgentDevice.usb_serial == usb_serial,
                    )
                ).first()
                if mapping is None:
                    port = self._pick_free_port(used_ports)
                    if port is None:
                        errors[usb_serial] = f"隧道端口耗尽（{TUNNEL_PORT_RANGE_START}-{TUNNEL_PORT_RANGE_END}）"
                        continue
                    used_ports.add(port)
                    mapping = RemoteAgentDevice(
                        agent_id=agent_id,
                        usb_serial=usb_serial,
                        tunnel_port=port,
                        model=meta.get("model"),
                        brand=meta.get("brand"),
                        os_version=meta.get("os_version"),
                        last_seen_at=now,
                    )
                    session.add(mapping)
                else:
                    mapping.model = meta.get("model")
                    mapping.brand = meta.get("brand")
                    mapping.os_version = meta.get("os_version")
                    mapping.last_seen_at = now
                    session.add(mapping)
                serial_str = tunnel_serial(mapping.tunnel_port)
                dev = session.scalar(select(Device).where(Device.serial == serial_str))
                dev_name = f"{meta.get('brand') or 'Remote'} {meta.get('model') or 'Android'} ({usb_serial[:6]})"
                if dev is None:
                    dev = Device(
                        serial=serial_str,
                        name=dev_name,
                        model=meta.get("model"),
                        brand=meta.get("brand"),
                        os_version=meta.get("os_version"),
                        ip_address="127.0.0.1",
                        status=DeviceStatus.online,
                        last_seen_at=now,
                    )
                    session.add(dev)
                else:
                    dev.name = dev.name or dev_name
                    dev.model = meta.get("model") or dev.model
                    dev.brand = meta.get("brand") or dev.brand
                    dev.os_version = meta.get("os_version") or dev.os_version
                    dev.status = DeviceStatus.online
                    dev.last_seen_at = now
                    session.add(dev)
                port_map[usb_serial] = int(mapping.tunnel_port)
            session.commit()
        return port_map, errors

    @staticmethod
    def _pick_free_port(used_ports: Set[int]) -> Optional[int]:
        for port in range(TUNNEL_PORT_RANGE_START, TUNNEL_PORT_RANGE_END + 1):
            if port not in used_ports:
                return port
        return None

    def _touch_last_seen(self, agent_session: AgentSession) -> None:
        now_monotonic = time.monotonic()
        if now_monotonic - agent_session._last_seen_written < LAST_SEEN_WRITE_INTERVAL_SECONDS:
            return
        agent_session._last_seen_written = now_monotonic
        try:
            with Session(engine) as session:
                agent = session.scalar(select(RemoteAgent).where(RemoteAgent.id == agent_session.agent_id))
                if agent is None:
                    return
                agent.last_seen_at = datetime.now(timezone.utc)
                session.add(agent)
                session.commit()
        except Exception:
            logger.exception("更新接入点心跳失败: agent=%s", agent_session.name)

    def _notify_keeper(self) -> None:
        if self._keeper is not None:
            try:
                self._keeper.trigger()
            except Exception:
                logger.exception("通知 adb keeper 失败")


tunnel_hub = TunnelHub()
