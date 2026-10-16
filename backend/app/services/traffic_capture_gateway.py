"""微服务网关旁路流量捕获与 HTTP/gRPC 多协议解析过滤服务 (T1.1)。

负责在微服务网关或 Sidecar 代理层旁路拦截与镜像生产流量，
支持路径/方法正则过滤、动态采样率截流、协议标准化解析及安全抓取。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import random
import re
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class TrafficProtocol(str, Enum):
    HTTP = "HTTP"
    GRPC = "GRPC"
    WEBSOCKET = "WEBSOCKET"


@dataclass
class CapturedTrafficItem:
    traffic_id: str
    protocol: TrafficProtocol
    method: str
    path_or_endpoint: str
    headers: dict[str, str]
    query_params: dict[str, str]
    request_body: str
    response_status_code: int
    response_body: str
    duration_ms: float
    client_ip: str | None = None
    tags: dict[str, str] = field(default_factory=dict)
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "traffic_id": self.traffic_id,
            "protocol": self.protocol.value,
            "method": self.method,
            "path_or_endpoint": self.path_or_endpoint,
            "headers": self.headers,
            "query_params": self.query_params,
            "request_body": self.request_body,
            "response_status_code": self.response_status_code,
            "response_body": self.response_body,
            "duration_ms": round(self.duration_ms, 2),
            "client_ip": self.client_ip,
            "tags": self.tags,
            "captured_at": self.captured_at.isoformat(),
        }


@dataclass
class CaptureFilterConfig:
    include_paths: list[str] = field(default_factory=lambda: [r"^/.*"])
    exclude_paths: list[str] = field(default_factory=lambda: [r"^/health.*", r"^/metrics.*", r"^/ready.*"])
    allowed_methods: list[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "PATCH"])
    sampling_rate: float = 1.0  # 0.0 ~ 1.0 (1.0 = 100% 全量捕获)
    capture_request_body: bool = True
    capture_response_body: bool = True
    max_body_bytes: int = 1048576  # 1MB 截断阈值

    def to_dict(self) -> dict[str, Any]:
        return {
            "include_paths": self.include_paths,
            "exclude_paths": self.exclude_paths,
            "allowed_methods": self.allowed_methods,
            "sampling_rate": self.sampling_rate,
            "capture_request_body": self.capture_request_body,
            "capture_response_body": self.capture_response_body,
            "max_body_bytes": self.max_body_bytes,
        }


# 全局内存仓库与过滤配置
_CAPTURED_TRAFFIC_STORE: dict[str, CapturedTrafficItem] = {}
_ACTIVE_FILTER_CONFIG: CaptureFilterConfig = CaptureFilterConfig()
_METRICS = {
    "total_intercepted": 0,
    "total_captured": 0,
    "total_filtered_out": 0,
    "total_sampled_out": 0,
}


def configure_capture_filter(config: CaptureFilterConfig | dict[str, Any]) -> CaptureFilterConfig:
    """配置流量捕获网关过滤规则与采样率。"""
    global _ACTIVE_FILTER_CONFIG
    if isinstance(config, dict):
        _ACTIVE_FILTER_CONFIG = CaptureFilterConfig(
            include_paths=config.get("include_paths", _ACTIVE_FILTER_CONFIG.include_paths),
            exclude_paths=config.get("exclude_paths", _ACTIVE_FILTER_CONFIG.exclude_paths),
            allowed_methods=config.get("allowed_methods", _ACTIVE_FILTER_CONFIG.allowed_methods),
            sampling_rate=float(config.get("sampling_rate", _ACTIVE_FILTER_CONFIG.sampling_rate)),
            capture_request_body=bool(config.get("capture_request_body", _ACTIVE_FILTER_CONFIG.capture_request_body)),
            capture_response_body=bool(
                config.get("capture_response_body", _ACTIVE_FILTER_CONFIG.capture_response_body)
            ),
            max_body_bytes=int(config.get("max_body_bytes", _ACTIVE_FILTER_CONFIG.max_body_bytes)),
        )
    else:
        _ACTIVE_FILTER_CONFIG = config

    logger.info("流量捕获过滤配置已更新: %s", _ACTIVE_FILTER_CONFIG.to_dict())
    return _ACTIVE_FILTER_CONFIG


def get_capture_filter_config() -> CaptureFilterConfig:
    """获取当前生效的流量捕获配置。"""
    return _ACTIVE_FILTER_CONFIG


def _matches_any_pattern(path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        try:
            if re.search(pattern, path):
                return True
        except re.error:
            if pattern in path:
                return True
    return False


def capture_traffic_payload(
    protocol: str | TrafficProtocol,
    method: str,
    path_or_endpoint: str,
    headers: dict[str, str] | None = None,
    query_params: dict[str, str] | None = None,
    request_body: str = "",
    response_status_code: int = 200,
    response_body: str = "",
    duration_ms: float = 0.0,
    client_ip: str | None = None,
    tags: dict[str, str] | None = None,
) -> CapturedTrafficItem | None:
    """旁路捕获单条流量负载，若满足过滤与采样规则则标准化入库，否则丢弃并记入指标。"""
    _METRICS["total_intercepted"] += 1
    cfg = _ACTIVE_FILTER_CONFIG

    # 1. 协议标准化
    try:
        prot_enum = TrafficProtocol(protocol.upper()) if isinstance(protocol, str) else protocol
    except ValueError:
        prot_enum = TrafficProtocol.HTTP

    # 2. 方法过滤
    method_upper = method.upper()
    verb = method_upper.split()[0] if " " in method_upper else method_upper
    if prot_enum == TrafficProtocol.HTTP and cfg.allowed_methods:
        if verb not in [m.upper() for m in cfg.allowed_methods]:
            _METRICS["total_filtered_out"] += 1
            return None
    elif prot_enum == TrafficProtocol.GRPC and cfg.allowed_methods:
        allowed_upper = [m.upper() for m in cfg.allowed_methods]
        if verb not in allowed_upper and "POST" not in allowed_upper:
            _METRICS["total_filtered_out"] += 1
            return None

    # 3. 排除路径检查
    if cfg.exclude_paths and _matches_any_pattern(path_or_endpoint, cfg.exclude_paths):
        _METRICS["total_filtered_out"] += 1
        return None

    # 4. 包含路径检查
    if cfg.include_paths and not _matches_any_pattern(path_or_endpoint, cfg.include_paths):
        _METRICS["total_filtered_out"] += 1
        return None

    # 5. 采样率截流 (0.0 ~ 1.0)
    if cfg.sampling_rate < 1.0:
        if random.random() > cfg.sampling_rate:
            _METRICS["total_sampled_out"] += 1
            return None

    # 6. Payload 截断保护
    req_body_safe = ""
    if cfg.capture_request_body and request_body:
        req_body_safe = request_body[: cfg.max_body_bytes]

    resp_body_safe = ""
    if cfg.capture_response_body and response_body:
        resp_body_safe = response_body[: cfg.max_body_bytes]

    # 7. 构造捕获项
    traffic_id = f"trf_{uuid.uuid4().hex}"
    item = CapturedTrafficItem(
        traffic_id=traffic_id,
        protocol=prot_enum,
        method=method_upper,
        path_or_endpoint=path_or_endpoint,
        headers=headers or {},
        query_params=query_params or {},
        request_body=req_body_safe,
        response_status_code=response_status_code,
        response_body=resp_body_safe,
        duration_ms=max(0.0, duration_ms),
        client_ip=client_ip,
        tags=tags or {},
    )

    _CAPTURED_TRAFFIC_STORE[traffic_id] = item
    _METRICS["total_captured"] += 1
    return item


def list_captured_traffic(
    protocol: str | None = None,
    path_pattern: str | None = None,
    min_status: int | None = None,
    max_status: int | None = None,
    limit: int = 100,
) -> list[CapturedTrafficItem]:
    """多维条件检索已捕获的流量记录列表。"""
    items = list(_CAPTURED_TRAFFIC_STORE.values())

    if protocol:
        prot_str = protocol.upper()
        items = [i for i in items if i.protocol.value == prot_str]

    if path_pattern:
        try:
            reg = re.compile(path_pattern)
            items = [i for i in items if reg.search(i.path_or_endpoint)]
        except re.error:
            items = [i for i in items if path_pattern in i.path_or_endpoint]

    if min_status is not None:
        items = [i for i in items if i.response_status_code >= min_status]

    if max_status is not None:
        items = [i for i in items if i.response_status_code <= max_status]

    # 按捕获时间倒序排列
    items.sort(key=lambda x: x.captured_at, reverse=True)
    return items[:limit]


def get_captured_traffic_by_id(traffic_id: str) -> CapturedTrafficItem | None:
    """根据 ID 获取指定捕获流量详情。"""
    return _CAPTURED_TRAFFIC_STORE.get(traffic_id)


def clear_captured_traffic() -> int:
    """清空所有捕获流量记录并重置计数指标。"""
    count = len(_CAPTURED_TRAFFIC_STORE)
    _CAPTURED_TRAFFIC_STORE.clear()
    _METRICS["total_intercepted"] = 0
    _METRICS["total_captured"] = 0
    _METRICS["total_filtered_out"] = 0
    _METRICS["total_sampled_out"] = 0
    return count


def get_capture_metrics() -> dict[str, Any]:
    """获取流量捕获网关运行指标。"""
    protocol_counts: dict[str, int] = {}
    for item in _CAPTURED_TRAFFIC_STORE.values():
        protocol_counts[item.protocol.value] = protocol_counts.get(item.protocol.value, 0) + 1

    return {
        "metrics": _METRICS,
        "active_records_count": len(_CAPTURED_TRAFFIC_STORE),
        "protocol_breakdown": protocol_counts,
        "filter_config": _ACTIVE_FILTER_CONFIG.to_dict(),
    }
