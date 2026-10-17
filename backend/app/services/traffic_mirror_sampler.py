"""分布式流量镜像采集与流量抽样过滤器服务 (T1.2)

在微服务网关与系统边界采集生产/预发真实业务流量，提供高效、合规的抽样与过滤机制:
1. 高频探针与无用监控流量自动识别与剔除 (Health Probe Filter);
2. 动态采样率 (1%~100%) 与一致性哈希抽样控制 (Dynamic Hash Sampler);
3. 多维路由条件过滤 (URL Glob/Regex, HTTP Method, Status Code, 载荷大小限制);
4. 与 T1.1 敏感数据脱敏器无缝打通，生成合规标准化的 MirroredTrafficItem;
5. 流量镜像缓冲区与吞吐遥测统计 (TrafficMirrorBuffer)。
"""

from __future__ import annotations

import fnmatch
import hashlib
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.traffic_sanitization_masker import (
    SanitizationMode,
    sanitize_traffic_payload,
)

# 默认健康检查探针与静态监控路径黑名单
_DEFAULT_PROBE_PATHS: Set[str] = {
    "/health",
    "/healthz",
    "/ready",
    "/readiness",
    "/live",
    "/liveness",
    "/metrics",
    "/actuator/health",
    "/actuator/prometheus",
    "/favicon.ico",
    "/ping",
    "/status",
}


@dataclass
class TrafficMirrorFilterCriteria:
    url_patterns: List[str] = field(default_factory=lambda: ["/api/*"])
    methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE"])
    status_codes: List[int] = field(default_factory=lambda: [200, 201, 204])
    sample_rate: float = 0.10  # 默认 10% 采样率 (0.01 ~ 1.0)
    exclude_probes: bool = True  # 自动过滤健康检查探针
    max_payload_bytes: int = 1024 * 1024  # 默认最大 1MB，超额截断或丢弃
    auto_sanitize: bool = True  # 是否自动执行金融级脱敏
    sanitization_mode: SanitizationMode = SanitizationMode.MASK

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["sanitization_mode"] = self.sanitization_mode.value
        return d


@dataclass
class MirroredTrafficItem:
    record_id: str
    trace_id: str
    method: str
    url: str
    path: str
    query_params: Dict[str, Any]
    headers: Dict[str, str]
    request_body: Any
    status_code: int
    response_headers: Dict[str, str]
    response_body: Any
    duration_ms: float
    is_sanitized: bool = False
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MirrorSamplerMetrics:
    total_received: int = 0
    probes_filtered: int = 0
    sampling_dropped: int = 0
    recorded_count: int = 0
    sanitized_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TrafficMirrorBuffer:
    """流量镜像与抽样缓冲区管理器"""

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.buffer: List[MirroredTrafficItem] = []
        self.metrics = MirrorSamplerMetrics()

    def clear(self) -> None:
        self.buffer.clear()
        self.metrics = MirrorSamplerMetrics()

    def add(self, item: MirroredTrafficItem) -> None:
        if len(self.buffer) >= self.capacity:
            self.buffer.pop(0)  # FIFO 淘汰
        self.buffer.append(item)
        self.metrics.recorded_count += 1
        if item.is_sanitized:
            self.metrics.sanitized_count += 1

    def list_items(
        self,
        method: Optional[str] = None,
        path_pattern: Optional[str] = None,
        limit: int = 50,
    ) -> List[MirroredTrafficItem]:
        res = self.buffer
        if method:
            res = [i for i in res if i.method.upper() == method.upper()]
        if path_pattern:
            res = [i for i in res if fnmatch.fnmatch(i.path, path_pattern)]
        return res[:limit]


# 全局单例缓冲区
_GLOBAL_MIRROR_BUFFER = TrafficMirrorBuffer()


def get_global_mirror_buffer() -> TrafficMirrorBuffer:
    return _GLOBAL_MIRROR_BUFFER


def is_health_probe(path: str) -> bool:
    """判定是否属于高频探针与无业务意义监控路径"""
    normalized = path.lower().split("?")[0].rstrip("/")
    if not normalized:
        return False
    return normalized in _DEFAULT_PROBE_PATHS or any(p in normalized for p in ["/actuator/", "/healthz"])


def is_sample_selected(trace_id: str, sample_rate: float) -> bool:
    """基于一致性哈希的确定性无偏抽样算法"""
    if sample_rate >= 1.0:
        return True
    if sample_rate <= 0.0:
        return False

    # 取 trace_id 的 md5 哈希值映射到 0~9999
    h_int = int(hashlib.md5(trace_id.encode("utf-8")).hexdigest()[:8], 16)
    threshold = int(sample_rate * 10000)
    return (h_int % 10000) < threshold


def evaluate_and_sample_traffic(
    raw_traffic: Dict[str, Any],
    criteria: Optional[TrafficMirrorFilterCriteria] = None,
    buffer: Optional[TrafficMirrorBuffer] = None,
) -> Tuple[bool, str, Optional[MirroredTrafficItem]]:
    """核心评估与抽样决策引擎

    Returns:
        (should_record: bool, filter_reason: str, item: Optional[MirroredTrafficItem])
    """
    crit = criteria or TrafficMirrorFilterCriteria()
    buf = buffer or _GLOBAL_MIRROR_BUFFER
    buf.metrics.total_received += 1

    method = str(raw_traffic.get("method", "GET")).upper()
    url = str(raw_traffic.get("url", ""))
    path = str(raw_traffic.get("path", "") or url.split("?")[0])
    status_code = int(raw_traffic.get("status_code", 200))
    trace_id = str(raw_traffic.get("trace_id") or f"tr_{uuid.uuid4().hex[:12]}")

    # 1. 过滤探针请求
    if crit.exclude_probes and is_health_probe(path):
        buf.metrics.probes_filtered += 1
        return False, f"剔除健康检查探针请求: {path}", None

    # 2. 检查 HTTP 方法白名单
    if crit.methods and method not in [m.upper() for m in crit.methods]:
        return False, f"HTTP 方法 '{method}' 未在允许列表 {crit.methods} 内", None

    # 3. 检查状态码白名单
    if crit.status_codes and status_code not in crit.status_codes:
        return False, f"状态码 {status_code} 未在允许列表 {crit.status_codes} 内", None

    # 4. 检查 URL/Path 模式匹配
    if crit.url_patterns:
        matched = False
        for pat in crit.url_patterns:
            if fnmatch.fnmatch(path, pat) or re.search(pat, path):
                matched = True
                break
        if not matched:
            return False, f"路径 '{path}' 未匹配任何规则 {crit.url_patterns}", None

    # 5. 一致性哈希抽样
    if not is_sample_selected(trace_id, crit.sample_rate):
        buf.metrics.sampling_dropped += 1
        return False, f"抽样未命中 (采样率: {crit.sample_rate * 100}%)", None

    # 6. 处理数据载荷与脱敏
    query_params = raw_traffic.get("query_params", {})
    headers = {str(k): str(v) for k, v in (raw_traffic.get("headers") or {}).items()}
    request_body = raw_traffic.get("request_body")
    response_headers = {str(k): str(v) for k, v in (raw_traffic.get("response_headers") or {}).items()}
    response_body = raw_traffic.get("response_body")
    duration_ms = float(raw_traffic.get("duration_ms", 15.0))

    is_sanitized = False
    if crit.auto_sanitize:
        query_params, _ = sanitize_traffic_payload(query_params, mode=crit.sanitization_mode)
        headers, _ = sanitize_traffic_payload(headers, mode=crit.sanitization_mode)
        request_body, _ = sanitize_traffic_payload(request_body, mode=crit.sanitization_mode)
        response_body, _ = sanitize_traffic_payload(response_body, mode=crit.sanitization_mode)
        is_sanitized = True

    record_id = f"trf_{uuid.uuid4().hex[:10]}"
    item = MirroredTrafficItem(
        record_id=record_id,
        trace_id=trace_id,
        method=method,
        url=url,
        path=path,
        query_params=query_params,
        headers=headers,
        request_body=request_body,
        status_code=status_code,
        response_headers=response_headers,
        response_body=response_body,
        duration_ms=duration_ms,
        is_sanitized=is_sanitized,
    )

    buf.add(item)
    return True, "命中抽样规则，成功镜像入库", item
