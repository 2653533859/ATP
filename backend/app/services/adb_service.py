"""
ADB 设备扫描服务

提供：
  - scan_devices()    扫描 ADB 已连接设备，返回解析后的设备信息列表
  - get_device_props() 获取单台设备的详细属性
"""
import asyncio
import logging
import re
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AdbDeviceInfo:
    serial: str
    status: str  # "device" / "offline" / "unauthorized"
    model: str | None = None
    brand: str | None = None
    os_version: str | None = None
    sdk_version: str | None = None
    resolution: str | None = None
    ip_address: str | None = None
    port: int | None = None


def _run_adb(*args: str, timeout: int = 10) -> str | None:
    """同步执行 adb 命令，返回 stdout"""
    cmd = ["adb", *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            logger.warning(
                "adb command failed (%s): %s",
                proc.returncode,
                (proc.stderr or "").strip(),
            )
            return None
        return proc.stdout.strip()
    except FileNotFoundError:
        logger.warning("adb command not found, is ADB installed?")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("adb command timed out: %s", " ".join(cmd))
        return None
    except Exception as e:
        logger.error("adb command error: %s", e)
        return None


def _parse_devices_output(output: str) -> list[dict[str, str]]:
    """解析 `adb devices -l` 输出"""
    devices = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        # 格式: serial  status  key:value key:value ...
        parts = line.split()
        if len(parts) < 2:
            continue
        serial = parts[0]
        status = parts[1]  # device / offline / unauthorized
        props = {}
        for part in parts[2:]:
            if ":" in part:
                k, v = part.split(":", 1)
                props[k] = v
        devices.append({"serial": serial, "status": status, **props})
    return devices


def _parse_serial_address(serial: str) -> tuple[str | None, int | None]:
    """从 serial 中解析 IP 和端口（TCP 连接格式为 ip:port）"""
    if ":" not in serial:
        return None, None
    parts = serial.split(":")
    ip_address = parts[0]
    try:
        port = int(parts[1])
    except (ValueError, IndexError):
        port = None
    return ip_address, port


def _get_prop(serial: str, prop: str) -> str:
    """获取设备单个 property"""
    return _run_adb("-s", serial, "shell", "getprop", prop, timeout=5) or ""


def _get_resolution(serial: str) -> str | None:
    """获取设备分辨率"""
    output = _run_adb("-s", serial, "shell", "wm", "size", timeout=5) or ""
    # "Physical size: 1080x1920"
    match = re.search(r"(\d+x\d+)", output)
    return match.group(1) if match else None


def get_device_props(serial: str) -> AdbDeviceInfo:
    """获取单台设备的详细信息（同步，在 executor 中调用）"""
    model = _get_prop(serial, "ro.product.model") or None
    brand = _get_prop(serial, "ro.product.brand") or None
    os_version = _get_prop(serial, "ro.build.version.release") or None
    sdk_version = _get_prop(serial, "ro.build.version.sdk") or None
    resolution = _get_resolution(serial)
    ip_address, port = _parse_serial_address(serial)

    return AdbDeviceInfo(
        serial=serial,
        status="device",
        model=model,
        brand=brand,
        os_version=os_version,
        sdk_version=sdk_version,
        resolution=resolution,
        ip_address=ip_address,
        port=port,
    )


def scan_devices() -> list[AdbDeviceInfo] | None:
    """扫描所有已连接的 ADB 设备（同步函数）"""
    output = _run_adb("devices", "-l")
    if output is None:
        return None
    if not output:
        return []

    raw_devices = _parse_devices_output(output)
    result: list[AdbDeviceInfo] = []

    for dev in raw_devices:
        serial = dev["serial"]
        status = dev["status"]

        if status == "device":
            info = get_device_props(serial)
            # adb devices -l 输出中也包含 model 信息，作为后备
            if not info.model and "model" in dev:
                info.model = dev["model"]
            result.append(info)
        else:
            # offline / unauthorized 设备只记录基础信息
            ip_address, port = _parse_serial_address(serial)
            result.append(AdbDeviceInfo(
                serial=serial,
                status=status,
                model=dev.get("model"),
                ip_address=ip_address,
                port=port,
            ))

    return result


async def async_scan_devices() -> list[AdbDeviceInfo] | None:
    """异步版本：在线程池中执行扫描"""
    return await asyncio.get_running_loop().run_in_executor(None, scan_devices)
