"""Scrcpy 设备视频流与控制管理器。

负责：
1. 检测并部署 scrcpy-server.jar 到设备；
2. 为设备启动 scrcpy server 并建立 video socket 与 control socket；
3. 后台线程解析 H.264 码流并广播给所有 WebSocket 客户端；
4. 接收前端触控、按键、文本事件并通过 control socket 直接注入设备，实现零延迟实时交互。
"""

import logging
import os
import queue
import socket
import struct
import subprocess
import threading
import time
from typing import Dict, Generator, List, Optional, Set

import adbutils

from app.core.package_paths import bundled_resource

logger = logging.getLogger("ScrcpyManager")

SCRCPY_SERVER_PATH = bundled_resource("backend/assets/scrcpy-server.jar")
DEVICE_JAR_PATH = "/data/local/tmp/scrcpy-server.jar"

PORT_RANGE_START = 27183
PORT_RANGE_END = 27283

SCRCPY_SERVER_VERSION = "3.3.4"
DEFAULT_SCRCPY_MAX_SIZE = 1280
DEFAULT_SCRCPY_BITRATE = 6_000_000
DEFAULT_SCRCPY_MAX_FPS = 60
SCRCPY_CONTROL_MSG_TYPE_INJECT_KEYCODE = 0
SCRCPY_CONTROL_MSG_TYPE_INJECT_TEXT = 1
SCRCPY_CONTROL_MSG_TYPE_INJECT_TOUCH_EVENT = 2

SCRCPY_POINTER_ID_GENERIC_FINGER = -2
ANDROID_KEYEVENT_ACTION_DOWN = 0
ANDROID_KEYEVENT_ACTION_UP = 1
ANDROID_MOTION_EVENT_ACTION_DOWN = 0
ANDROID_MOTION_EVENT_ACTION_UP = 1
ANDROID_MOTION_EVENT_ACTION_MOVE = 2

SYNC_NAL_TYPES = frozenset({5, 7, 8})
CLIENT_QUEUE_MAXSIZE = 120


class DeviceInfo:
    """单个连接的设备运行状态。"""

    def __init__(self, serial: str, local_port: int):
        self.serial = serial
        self.local_port = local_port
        self.scrcpy_process: Optional[subprocess.Popen] = None
        self.video_socket: Optional[socket.socket] = None
        self.control_socket: Optional[socket.socket] = None
        self.control_lock = threading.Lock()
        self.stream_lock = threading.Lock()
        self.device_name: str = ""
        self.screen_width: int = 0
        self.screen_height: int = 0
        self.ready: bool = False
        self.running: bool = False
        self.error: Optional[str] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.input_queues: List["ClientStreamQueue"] = []
        self.sps_pps_packets: List[bytes] = []
        self.last_keyframe_packet: Optional[bytes] = None


def _collect_h264_nal_types(data: bytes) -> Set[int]:
    nal_types: Set[int] = set()
    length = len(data)
    i = 0
    while i < length - 3:
        if data[i : i + 4] == b"\x00\x00\x00\x01":
            start_code_len = 4
        elif data[i : i + 3] == b"\x00\x00\x01":
            start_code_len = 3
        else:
            i += 1
            continue
        nal_index = i + start_code_len
        if nal_index < length:
            nal_types.add(data[nal_index] & 0x1F)
        i = nal_index + 1
    if not nal_types and data:
        nal_types.add(data[0] & 0x1F)
    return nal_types


def _update_h264_init_cache(dev_info: DeviceInfo, data: bytes) -> Set[int]:
    nal_types = _collect_h264_nal_types(data)
    if 7 in nal_types:
        dev_info.sps_pps_packets = []
        dev_info.last_keyframe_packet = None
    if 7 in nal_types or 8 in nal_types:
        if data not in dev_info.sps_pps_packets:
            dev_info.sps_pps_packets.append(data)
    if 5 in nal_types:
        dev_info.last_keyframe_packet = data
    return nal_types


def _get_h264_init_packets(dev_info: DeviceInfo) -> List[bytes]:
    packets: List[bytes] = []
    seen: Set[bytes] = set()
    for packet in dev_info.sps_pps_packets:
        if packet and packet not in seen:
            packets.append(packet)
            seen.add(packet)
    if dev_info.last_keyframe_packet and dev_info.last_keyframe_packet not in seen:
        packets.append(dev_info.last_keyframe_packet)
    return packets


class ClientStreamQueue:
    def __init__(self, maxsize: int = CLIENT_QUEUE_MAXSIZE):
        self.queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self.awaiting_keyframe: bool = False
        self.active: bool = True

    def offer(self, data: bytes, nal_types: Set[int], init_packets: Optional[List[bytes]] = None) -> bool:
        if not self.active:
            return False
        is_sync = bool(nal_types & SYNC_NAL_TYPES)
        if self.awaiting_keyframe:
            if not is_sync:
                return False
            self.awaiting_keyframe = False
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break
            if init_packets:
                for init_pkt in init_packets:
                    # 避免在 init_packets 与当前 data 重复入队
                    if init_pkt == data:
                        continue
                    try:
                        self.queue.put_nowait(init_pkt)
                    except queue.Full:
                        break
        try:
            self.queue.put_nowait(data)
            return True
        except queue.Full:
            self.awaiting_keyframe = True
            return False

    def get(self, timeout: float = 1.0) -> Optional[bytes]:
        return self.queue.get(timeout=timeout)

    def close(self) -> None:
        self.active = False
        try:
            self.queue.put_nowait(None)
        except Exception:
            pass

    def qsize(self) -> int:
        return self.queue.qsize()


class ClientStream:
    """管理 WebSocket 客户端对 Scrcpy 视频流的消费与优雅退出。"""

    def __init__(self, dev_info: DeviceInfo, client_queue: ClientStreamQueue):
        self.dev_info = dev_info
        self.client_queue = client_queue

    def get_chunk(self, timeout: float = 1.0) -> Optional[bytes]:
        if not self.client_queue.active or not self.dev_info.running:
            return None
        try:
            return self.client_queue.get(timeout=timeout)
        except queue.Empty:
            return b""  # 心跳/空滴答

    def close(self) -> None:
        self.client_queue.close()
        with self.dev_info.stream_lock:
            if self.client_queue in self.dev_info.input_queues:
                self.dev_info.input_queues.remove(self.client_queue)


def _broadcast_video_packet(dev_info: DeviceInfo, data: bytes) -> None:
    if not data:
        return
    with dev_info.stream_lock:
        nal_types = _update_h264_init_cache(dev_info, data)
        is_sync = bool(nal_types & SYNC_NAL_TYPES)
        init_packets = _get_h264_init_packets(dev_info) if is_sync else None
        for client_queue in list(dev_info.input_queues):
            client_queue.offer(data, nal_types, init_packets=init_packets)


def _build_touch_control_packet(
    action: int,
    x: int,
    y: int,
    screen_width: int,
    screen_height: int,
    *,
    pointer_id: int = SCRCPY_POINTER_ID_GENERIC_FINGER,
    pressure: float = 1.0,
    action_button: int = 0,
    buttons: int = 0,
) -> bytes:
    safe_pressure = max(0.0, min(1.0, float(pressure)))
    pressure_u16 = int(round(safe_pressure * 0xFFFF))
    return b"".join(
        [
            struct.pack(">B", SCRCPY_CONTROL_MSG_TYPE_INJECT_TOUCH_EVENT),
            struct.pack(">B", int(action)),
            struct.pack(">q", int(pointer_id)),
            struct.pack(">I", max(0, int(x))),
            struct.pack(">I", max(0, int(y))),
            struct.pack(">H", max(0, int(screen_width))),
            struct.pack(">H", max(0, int(screen_height))),
            struct.pack(">H", pressure_u16),
            struct.pack(">I", int(action_button)),
            struct.pack(">I", int(buttons)),
        ]
    )


def _build_keycode_control_packet(
    action: int,
    keycode: int,
    repeat: int = 0,
    meta_state: int = 0,
) -> bytes:
    return struct.pack(
        ">BBiii",
        SCRCPY_CONTROL_MSG_TYPE_INJECT_KEYCODE,
        int(action),
        int(keycode),
        int(repeat),
        int(meta_state),
    )


def _build_text_control_packet(text: str) -> bytes:
    raw = text.encode("utf-8")
    return struct.pack(">BI", SCRCPY_CONTROL_MSG_TYPE_INJECT_TEXT, len(raw)) + raw


def _sanitize_adb_input_text(text: str) -> str:
    """对 adb shell input text 参数进行安全转义与空格转换，防范 Shell 命令注入。"""
    cleaned = "".join(ch for ch in text if ch.isprintable() or ch == "\t")
    escaped: List[str] = []
    for ch in cleaned:
        if ch == " ":
            escaped.append("%s")
        elif ch in "\\'\"$&;|<>()`~*?[]{}!^":
            escaped.append(f"\\{ch}")
        else:
            escaped.append(ch)
    return "".join(escaped)


class ScrcpyDeviceManager:
    def __init__(self):
        self._devices: Dict[str, DeviceInfo] = {}
        self._connecting: Set[str] = set()
        self._used_ports: Set[int] = set()
        self._lock = threading.Lock()
        self._running = True

    def _allocate_port(self) -> Optional[int]:
        with self._lock:
            for port in range(PORT_RANGE_START, PORT_RANGE_END):
                if port not in self._used_ports:
                    self._used_ports.add(port)
                    return port
        return None

    def _release_port(self, port: int):
        self._used_ports.discard(port)

    def _deploy_scrcpy_server(self, device) -> bool:
        if not SCRCPY_SERVER_PATH.exists():
            logger.error("scrcpy-server.jar 不存在: %s", SCRCPY_SERVER_PATH)
            return False
        try:
            remote_size = device.shell(f"wc -c < {DEVICE_JAR_PATH} 2>/dev/null || echo 0").strip()
            local_size = str(os.path.getsize(SCRCPY_SERVER_PATH))
            if remote_size != local_size:
                logger.info("部署 scrcpy-server.jar 至设备: %s", device.serial)
                device.sync.push(str(SCRCPY_SERVER_PATH), DEVICE_JAR_PATH)
            return True
        except Exception as e:
            logger.error("部署 scrcpy-server 失败: %s", e)
            return False

    def _recv_exactly(self, sock: socket.socket, n: int) -> bytes:
        data = bytearray()
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Socket 连接已断开")
            data.extend(chunk)
        return bytes(data)

    def ensure_device_stream(self, serial: str, timeout: float = 12.0) -> DeviceInfo:
        with self._lock:
            dev = self._devices.get(serial)
            if dev and dev.ready and dev.running:
                return dev
            if serial not in self._connecting:
                self._connecting.add(serial)
                threading.Thread(target=self._connect_device_sync, args=(serial,), daemon=True).start()

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                dev = self._devices.get(serial)
                if dev and dev.ready and dev.running:
                    return dev
                if serial not in self._connecting and dev and dev.error:
                    raise RuntimeError(f"Scrcpy 启动失败: {dev.error}")
            time.sleep(0.05)

        raise TimeoutError(f"等待设备 {serial} 视频流就绪超时")

    def _connect_device_sync(self, serial: str):
        local_port = self._allocate_port()
        if not local_port:
            logger.error("无可用端口启动 scrcpy: %s", serial)
            with self._lock:
                self._connecting.discard(serial)
            return

        dev_info = DeviceInfo(serial, local_port)
        proc = None
        video_sock = None
        ctrl_sock = None

        try:
            adb = adbutils.AdbClient()
            device = adb.device(serial=serial)
            if not self._deploy_scrcpy_server(device):
                dev_info.error = "推送 scrcpy-server.jar 失败"
                self._release_port(local_port)
                with self._lock:
                    self._devices[serial] = dev_info
                    self._connecting.discard(serial)
                return

            try:
                device.shell("pkill -f scrcpy 2>/dev/null || true")
                time.sleep(0.2)
            except Exception:
                pass

            device.forward(f"tcp:{local_port}", "localabstract:scrcpy")

            cmd = [
                "adb",
                "-s",
                serial,
                "shell",
                f"CLASSPATH={DEVICE_JAR_PATH}",
                "app_process",
                "/",
                "com.genymobile.scrcpy.Server",
                SCRCPY_SERVER_VERSION,
                "log_level=info",
                "tunnel_forward=true",
                "video=true",
                "audio=false",
                "control=true",
                "cleanup=false",
                f"max_size={DEFAULT_SCRCPY_MAX_SIZE}",
                f"video_bit_rate={DEFAULT_SCRCPY_BITRATE}",
                f"max_fps={DEFAULT_SCRCPY_MAX_FPS}",
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            dev_info.scrcpy_process = proc

            for _ in range(12):
                time.sleep(0.3)
                if proc.poll() is not None:
                    err = proc.stderr.read().decode(errors="ignore") if proc.stderr else ""
                    dev_info.error = f"scrcpy 进程已退出: {err[:200]}"
                    self._release_port(local_port)
                    with self._lock:
                        self._devices[serial] = dev_info
                        self._connecting.discard(serial)
                    return
                try:
                    video_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    video_sock.settimeout(2)
                    video_sock.connect(("127.0.0.1", local_port))
                    # 验证是否真正打通（读取 1 字节 dummy byte）
                    dummy = self._recv_exactly(video_sock, 1)
                    if dummy:
                        break
                except Exception:
                    if video_sock:
                        try:
                            video_sock.close()
                        except Exception:
                            pass
                    video_sock = None

            if not video_sock:
                dev_info.error = "Video socket 连接超时"
                if proc:
                    proc.terminate()
                self._release_port(local_port)
                with self._lock:
                    self._devices[serial] = dev_info
                    self._connecting.discard(serial)
                return

            ctrl_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ctrl_sock.settimeout(3)
            ctrl_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            ctrl_sock.connect(("127.0.0.1", local_port))
            dev_info.control_socket = ctrl_sock

            name_bytes = self._recv_exactly(video_sock, 64)
            dev_info.device_name = name_bytes.rstrip(b"\x00").decode("utf-8", errors="ignore")
            dev_info.video_socket = video_sock

            # 读取 12 字节 Codec Header: 4B codec ("h264") + 4B width + 4B height
            codec_hdr = self._recv_exactly(video_sock, 12)
            if codec_hdr[:4] == b"h264":
                w, h = struct.unpack(">II", codec_hdr[4:12])
                dev_info.screen_width = int(w)
                dev_info.screen_height = int(h)
            else:
                logger.warning("未识别的 Codec Header: %s", codec_hdr.hex())
                dev_info.screen_width = 600
                dev_info.screen_height = 960

            dev_info.running = True
            dev_info.ready = True
            self._start_video_reader(dev_info)

            with self._lock:
                self._devices[serial] = dev_info
                self._connecting.discard(serial)
            logger.info(
                "Scrcpy 视频流已启动就绪: %s (%dx%d)",
                serial,
                dev_info.screen_width,
                dev_info.screen_height,
            )

        except Exception as exc:
            logger.exception("Scrcpy 启动异常: serial=%s", serial)
            dev_info.error = str(exc)
            dev_info.ready = False
            dev_info.running = False
            for s in (video_sock, ctrl_sock):
                if s:
                    try:
                        s.close()
                    except Exception:
                        pass
            if proc:
                try:
                    proc.terminate()
                except Exception:
                    pass
            if local_port:
                self._release_port(local_port)
            with self._lock:
                self._devices[serial] = dev_info
                self._connecting.discard(serial)

    def _start_video_reader(self, dev_info: DeviceInfo):
        def _reader_loop():
            sock = dev_info.video_socket
            if not sock:
                self._cleanup_device(dev_info.serial)
                return
            sock.settimeout(5)

            try:
                use_raw_mode = False
                try:
                    first_12 = self._recv_exactly(sock, 12)
                    if first_12.startswith(b"\x00\x00\x00\x01"):
                        use_raw_mode = True
                except Exception:
                    return

                if use_raw_mode:
                    buf = bytearray(first_12)
                    start_code = b"\x00\x00\x00\x01"
                    while dev_info.running and self._running:
                        try:
                            chunk = sock.recv(65536)
                            if not chunk:
                                break
                            buf.extend(chunk)
                            while True:
                                pos = buf.find(start_code, 4)
                                if pos == -1:
                                    break
                                nal = bytes(buf[:pos])
                                _broadcast_video_packet(dev_info, nal)
                                buf = buf[pos:]
                        except socket.timeout:
                            continue
                        except Exception:
                            break
                else:
                    pending_hdr = first_12
                    while dev_info.running and self._running:
                        try:
                            if pending_hdr:
                                hdr = pending_hdr
                                pending_hdr = None
                            else:
                                hdr = self._recv_exactly(sock, 12)
                                if not hdr:
                                    break
                            pkt_len = struct.unpack(">I", hdr[8:12])[0]
                            if pkt_len == 0 or pkt_len > 5 * 1024 * 1024:
                                continue
                            h264_data = self._recv_exactly(sock, pkt_len)
                            if not h264_data:
                                continue
                            _broadcast_video_packet(dev_info, h264_data)
                        except socket.timeout:
                            continue
                        except Exception:
                            break
            finally:
                dev_info.ready = False
                dev_info.running = False
                self._cleanup_device(dev_info.serial)

        t = threading.Thread(target=_reader_loop, daemon=True, name=f"ScrcpyReader-{dev_info.serial}")
        dev_info.reader_thread = t
        t.start()

    def create_client_stream(self, serial: str) -> ClientStream:
        """为客户端创建安全的流式通道，支持显式关闭与非阻塞退出。"""
        dev_info = self.ensure_device_stream(serial)
        client_queue = ClientStreamQueue()
        with dev_info.stream_lock:
            init_pkts = _get_h264_init_packets(dev_info)
            for pkt in init_pkts:
                client_queue.offer(pkt, _collect_h264_nal_types(pkt))
            dev_info.input_queues.append(client_queue)
        return ClientStream(dev_info, client_queue)

    def get_video_generator(self, serial: str) -> Generator[bytes, None, None]:
        dev_info = self.ensure_device_stream(serial)
        client_queue = ClientStreamQueue()
        with dev_info.stream_lock:
            init_pkts = _get_h264_init_packets(dev_info)
            for pkt in init_pkts:
                client_queue.offer(pkt, _collect_h264_nal_types(pkt))
            dev_info.input_queues.append(client_queue)

        try:
            while dev_info.running and self._running and client_queue.active:
                try:
                    data = client_queue.get(timeout=1.0)
                    if data is None:
                        break
                    yield data
                except queue.Empty:
                    if not dev_info.ready or not dev_info.running:
                        break
                    continue
        finally:
            with dev_info.stream_lock:
                if client_queue in dev_info.input_queues:
                    dev_info.input_queues.remove(client_queue)

    def send_touch_event(
        self,
        serial: str,
        action: int,
        x: int,
        y: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> None:
        dev_info = self._devices.get(serial)
        if not dev_info or not dev_info.ready or not dev_info.control_socket:
            raise ValueError(f"设备 {serial} scrcpy control socket 未就绪")

        w = max(1, int(width or dev_info.screen_width or 1080))
        h = max(1, int(height or dev_info.screen_height or 1920))
        clamped_x = min(w - 1, max(0, int(x)))
        clamped_y = min(h - 1, max(0, int(y)))
        pressure = 0.0 if int(action) == ANDROID_MOTION_EVENT_ACTION_UP else 1.0

        packet = _build_touch_control_packet(
            action=int(action),
            x=clamped_x,
            y=clamped_y,
            screen_width=w,
            screen_height=h,
            pressure=pressure,
        )
        with dev_info.control_lock:
            dev_info.control_socket.sendall(packet)

    def send_key_event(self, serial: str, keycode: int) -> None:
        dev_info = self._devices.get(serial)
        if dev_info and dev_info.ready and dev_info.control_socket:
            down_pkt = _build_keycode_control_packet(ANDROID_KEYEVENT_ACTION_DOWN, int(keycode))
            up_pkt = _build_keycode_control_packet(ANDROID_KEYEVENT_ACTION_UP, int(keycode))
            with dev_info.control_lock:
                dev_info.control_socket.sendall(down_pkt + up_pkt)
            return
        # Fallback to adb shell input keyevent
        subprocess.run(
            ["adb", "-s", serial, "shell", "input", "keyevent", str(int(keycode))],
            capture_output=True,
            timeout=5,
        )

    def send_text_event(self, serial: str, text: str) -> None:
        if not text:
            return
        dev_info = self._devices.get(serial)
        if dev_info and dev_info.ready and dev_info.control_socket:
            pkt = _build_text_control_packet(text)
            with dev_info.control_lock:
                dev_info.control_socket.sendall(pkt)
            return
        # 安全转义 fallback，防止 Shell 元字符注入并正确传递空格
        safe_text = _sanitize_adb_input_text(text)
        if safe_text:
            subprocess.run(
                ["adb", "-s", serial, "shell", "input", "text", safe_text],
                capture_output=True,
                timeout=5,
            )

    def _cleanup_device(self, serial: str) -> None:
        """彻底清理单个设备的所有 Scrcpy 资源并释放端口池。"""
        with self._lock:
            dev_info = self._devices.pop(serial, None)
            self._connecting.discard(serial)
        if not dev_info:
            return

        dev_info.running = False
        dev_info.ready = False
        for s in (dev_info.video_socket, dev_info.control_socket):
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        dev_info.video_socket = None
        dev_info.control_socket = None

        if dev_info.scrcpy_process:
            try:
                dev_info.scrcpy_process.terminate()
            except Exception:
                pass
            dev_info.scrcpy_process = None

        if dev_info.local_port:
            self._release_port(dev_info.local_port)
            try:
                adb = adbutils.AdbClient()
                device = adb.device(serial=serial)
                device.forward_remove(f"tcp:{dev_info.local_port}")
            except Exception:
                pass

    def cleanup_all(self):
        self._running = False
        with self._lock:
            serials = list(self._devices.keys())
        for serial in serials:
            self._cleanup_device(serial)


scrcpy_manager = ScrcpyDeviceManager()
