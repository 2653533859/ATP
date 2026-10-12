"""远程设备接入协议常量与帧编解码。

Agent（B 机脚本）与后端通过一条 WebSocket 通信：
- 控制消息走 JSON text 帧（register / devices / open / open_result / close / ping / pong / error）
- 隧道数据走 binary 帧：4 字节大端 conn_id + 原始 TCP payload
"""

import struct
from typing import Optional, Tuple

AGENT_PROTOCOL_VERSION = 1

# 每台远程设备在后端 127.0.0.1 上的隧道监听端口范围（含端点）
TUNNEL_PORT_RANGE_START = 28100
TUNNEL_PORT_RANGE_END = 28199

TUNNEL_HOST = "127.0.0.1"

DATA_FRAME_HEADER_SIZE = 4
MAX_DATA_PAYLOAD = 1024 * 1024

REMOTE_USB_CONNECTION_TYPE = "remote_usb"


def encode_data_frame(conn_id: int, payload: bytes) -> bytes:
    """编码隧道数据帧：4 字节大端 conn_id + payload。"""
    return struct.pack(">I", int(conn_id)) + payload


def decode_data_frame(frame: bytes) -> Tuple[int, bytes]:
    """解码隧道数据帧，返回 (conn_id, payload)；帧过短时抛 ValueError。"""
    if len(frame) < DATA_FRAME_HEADER_SIZE:
        raise ValueError(f"data frame too short: {len(frame)} bytes")
    conn_id = struct.unpack(">I", frame[:DATA_FRAME_HEADER_SIZE])[0]
    return conn_id, frame[DATA_FRAME_HEADER_SIZE:]


def tunnel_serial(port: int) -> str:
    """隧道端口对应的 adb serial（adb connect 后的设备形态）。"""
    return f"{TUNNEL_HOST}:{int(port)}"


def parse_tunnel_serial(serial: str) -> Optional[int]:
    """解析 serial 是否为本机隧道形态（127.0.0.1:<范围内端口>），返回端口或 None。"""
    text = str(serial or "").strip()
    prefix = f"{TUNNEL_HOST}:"
    if not text.startswith(prefix):
        return None
    try:
        port = int(text[len(prefix) :])
    except ValueError:
        return None
    if TUNNEL_PORT_RANGE_START <= port <= TUNNEL_PORT_RANGE_END:
        return port
    return None
