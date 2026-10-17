"""测试步骤与服务端调用链跨网络时钟对齐器服务 (T2.1)

基于 Cristian's 算法与分布式追踪因果单调性原理（Causal Monotonicity）：
解决自动化测试节点与被测微服务集群跨网络、跨机房产生的时钟偏移 (Clock Skew)。
强制保证：T_client_send <= T_server_start <= T_server_end <= T_client_receive
消除因果倒置与时序重叠伪异常。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class ClockSkewCompensation:
    span_id: str
    service_name: str
    client_send_time_ms: float
    client_receive_time_ms: float
    raw_server_start_ms: float
    raw_server_end_ms: float
    skew_offset_ms: float
    estimated_rtt_ms: float
    calibrated_server_start_ms: float
    calibrated_server_end_ms: float
    is_skew_detected: bool
    causality_preserved: bool
    calibrated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "service_name": self.service_name,
            "client_send_time_ms": self.client_send_time_ms,
            "client_receive_time_ms": self.client_receive_time_ms,
            "raw_server_start_ms": self.raw_server_start_ms,
            "raw_server_end_ms": self.raw_server_end_ms,
            "skew_offset_ms": round(self.skew_offset_ms, 3),
            "estimated_rtt_ms": round(self.estimated_rtt_ms, 3),
            "calibrated_server_start_ms": round(self.calibrated_server_start_ms, 3),
            "calibrated_server_end_ms": round(self.calibrated_server_end_ms, 3),
            "is_skew_detected": self.is_skew_detected,
            "causality_preserved": self.causality_preserved,
            "calibrated_at": self.calibrated_at,
        }


# 全局轻量级时钟校准审计记录
_CLOCK_SKEW_HISTORY: List[ClockSkewCompensation] = []


def clear_clock_skew_history() -> None:
    _CLOCK_SKEW_HISTORY.clear()


def list_clock_skew_history(limit: int = 50) -> List[Dict[str, Any]]:
    return [c.to_dict() for c in reversed(_CLOCK_SKEW_HISTORY[-limit:])]


def calculate_clock_skew(
    client_send_time_ms: float,
    client_receive_time_ms: float,
    raw_server_start_ms: float,
    raw_server_end_ms: float,
    span_id: str = "span_root",
    service_name: str = "backend-service",
) -> ClockSkewCompensation:
    """计算单个客户端-服务端往返的物理时钟偏移与因果校准时间戳"""
    client_duration = max(0.1, client_receive_time_ms - client_send_time_ms)
    server_duration = max(0.05, raw_server_end_ms - raw_server_start_ms)

    # 估计单程网络时延与网络往返时延 (RTT)
    estimated_rtt = max(0.0, client_duration - server_duration)
    half_rtt = estimated_rtt / 2.0

    # 时钟偏移 skew = ((server_start - client_send) + (server_end - client_receive)) / 2
    # 若无时钟漂移，理想状况 server_start = client_send + half_rtt，此时 skew = 0
    skew_offset = ((raw_server_start_ms - client_send_time_ms) + (raw_server_end_ms - client_receive_time_ms)) / 2.0

    is_skew_detected = abs(skew_offset) > 2.0  # 偏移超 2ms 判定存在时钟差

    # 补偿校准后的服务端时间戳
    calibrated_start = raw_server_start_ms - skew_offset
    calibrated_end = raw_server_end_ms - skew_offset

    # 边界因果强制收敛：保证 client_send <= calibrated_start <= calibrated_end <= client_receive
    if calibrated_start < client_send_time_ms:
        calibrated_start = client_send_time_ms + (half_rtt * 0.1)
    if calibrated_end > client_receive_time_ms:
        calibrated_end = client_receive_time_ms - (half_rtt * 0.1)
    if calibrated_end < calibrated_start:
        calibrated_end = calibrated_start + server_duration

    causality_preserved = client_send_time_ms <= calibrated_start <= calibrated_end <= client_receive_time_ms

    result = ClockSkewCompensation(
        span_id=span_id,
        service_name=service_name,
        client_send_time_ms=client_send_time_ms,
        client_receive_time_ms=client_receive_time_ms,
        raw_server_start_ms=raw_server_start_ms,
        raw_server_end_ms=raw_server_end_ms,
        skew_offset_ms=skew_offset,
        estimated_rtt_ms=estimated_rtt,
        calibrated_server_start_ms=calibrated_start,
        calibrated_server_end_ms=calibrated_end,
        is_skew_detected=is_skew_detected,
        causality_preserved=causality_preserved,
    )
    _CLOCK_SKEW_HISTORY.append(result)
    return result


def align_span_tree_timestamps(
    client_step_span: Dict[str, Any],
    server_spans: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """递归校准服务端 Span 树的时间戳，消除网络时钟偏移并保持嵌套因果关系"""
    if not server_spans:
        return []

    c_send = float(client_step_span.get("start_time_ms", 0.0))
    c_recv = float(client_step_span.get("end_time_ms", c_send + 100.0))

    # 找出服务端根 Span（即 parent_span_id 为客户端 span 或空的第一个服务）
    root_server = next(
        (
            s
            for s in server_spans
            if not s.get("parent_span_id") or s.get("parent_span_id") == client_step_span.get("span_id")
        ),
        server_spans[0],
    )

    s_start = float(root_server.get("start_time_ms", c_send + 10.0))
    s_end = float(root_server.get("end_time_ms", s_start + 50.0))

    comp = calculate_clock_skew(
        client_send_time_ms=c_send,
        client_receive_time_ms=c_recv,
        raw_server_start_ms=s_start,
        raw_server_end_ms=s_end,
        span_id=str(root_server.get("span_id", "srv_root")),
        service_name=str(root_server.get("service_name", "root_service")),
    )

    skew = comp.skew_offset_ms

    aligned_spans: List[Dict[str, Any]] = []
    for s in server_spans:
        item = dict(s)
        raw_st = float(item.get("start_time_ms", s_start))
        raw_et = float(item.get("end_time_ms", s_end))

        cal_st = max(c_send, raw_st - skew)
        cal_et = min(c_recv, raw_et - skew)
        if cal_et < cal_st:
            cal_et = cal_st + max(0.1, raw_et - raw_st)

        item["start_time_ms"] = round(cal_st, 3)
        item["end_time_ms"] = round(cal_et, 3)
        item["duration_ms"] = round(cal_et - cal_st, 3)
        item["clock_skew_compensated"] = True
        item["applied_skew_ms"] = round(skew, 3)
        aligned_spans.append(item)

    return aligned_spans
