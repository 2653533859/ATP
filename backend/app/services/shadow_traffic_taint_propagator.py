"""跨协议影子流量染色标动态注入与透明透传校验器 (T1.1)。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ProtocolType(str, Enum):
    """跨协议通信类型枚举。"""

    HTTP_REST = "HTTP_REST"
    GRPC = "GRPC"
    KAFKA_MQ = "KAFKA_MQ"
    RABBITMQ = "RABBITMQ"
    ROCKETMQ = "ROCKETMQ"


class PropagationVerdict(str, Enum):
    """透传链路检验裁决。"""

    FULL_PROPAGATION_SUCCESS = "FULL_PROPAGATION_SUCCESS"  # 染色全链路完整透传
    TAINT_LEAKAGE_DETECTED = "TAINT_LEAKAGE_DETECTED"  # 丢标泄漏 (存在污染生产风险)
    CORRUPTED_METADATA = "CORRUPTED_METADATA"  # 染色标头校验和错乱


@dataclass
class ServiceHopRecord:
    """拓扑链路中的单跳服务快照。"""

    hop_order: int
    service_name: str
    protocol: ProtocolType
    received_shadow_flag: bool
    retained_trace_id: str | None
    is_taint_lost: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "hop_order": self.hop_order,
            "service_name": self.service_name,
            "protocol": self.protocol.value,
            "received_shadow_flag": self.received_shadow_flag,
            "retained_trace_id": self.retained_trace_id,
            "is_taint_lost": self.is_taint_lost,
        }


@dataclass
class ShadowTaintValidationReport:
    """影子流量染色透传全景校验报告。"""

    report_id: str
    trace_id: str
    total_hops_count: int
    lost_hops_count: int
    verdict: PropagationVerdict
    integrity_score_pct: float
    has_leakage_risk: bool
    hops: list[ServiceHopRecord]
    remediation_advice: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "trace_id": self.trace_id,
            "total_hops_count": self.total_hops_count,
            "lost_hops_count": self.lost_hops_count,
            "verdict": self.verdict.value,
            "integrity_score_pct": round(self.integrity_score_pct, 1),
            "has_leakage_risk": self.has_leakage_risk,
            "hops": [h.to_dict() for h in self.hops],
            "remediation_advice": self.remediation_advice,
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告仓库
_SHADOW_TAINT_REPORTS: dict[str, ShadowTaintValidationReport] = {}


def clear_shadow_taint_store() -> None:
    """清空影子染色报告仓库 (单测专用)。"""
    _SHADOW_TAINT_REPORTS.clear()


def inject_shadow_taint(
    protocol: ProtocolType,
    payload_headers: dict[str, Any] | None = None,
    trace_id: str | None = None,
    cluster_tag: str = "prod_stress_01",
) -> dict[str, Any]:
    """对各通信协议报文动态注入标准化的影子染色标头。"""
    headers = dict(payload_headers or {})
    tid = trace_id or f"st_{uuid.uuid4().hex[:12]}"

    if protocol == ProtocolType.HTTP_REST:
        headers["X-ATP-Shadow"] = "true"
        headers["X-ATP-Shadow-Trace"] = tid
        headers["X-ATP-Shadow-Cluster"] = cluster_tag
    elif protocol == ProtocolType.GRPC:
        headers["x-atp-shadow"] = "true"
        headers["x-atp-shadow-trace"] = tid
        headers["x-atp-shadow-cluster"] = cluster_tag
    else:
        # MQ 消息头标准透传
        headers["__atp_shadow_taint__"] = "true"
        headers["__atp_shadow_trace__"] = tid
        headers["__atp_shadow_cluster__"] = cluster_tag

    return headers


def verify_trace_propagation(
    trace_id: str,
    hop_traces: list[dict[str, Any]],
) -> ShadowTaintValidationReport:
    """深度校验端到端拓扑链路中染色标的保留完整性，防范穿透污染。"""
    hops: list[ServiceHopRecord] = []
    lost_count = 0
    advice: list[str] = []

    for idx, h in enumerate(hop_traces, start=1):
        s_name = str(h.get("service_name") or f"svc_hop_{idx}")
        prot_str = str(h.get("protocol") or "HTTP_REST").upper()
        try:
            prot = ProtocolType[prot_str]
        except KeyError:
            prot = ProtocolType.HTTP_REST

        headers = dict(h.get("headers") or {})

        # 检查各协议染色字段是否存在
        if prot == ProtocolType.HTTP_REST:
            has_flag = headers.get("X-ATP-Shadow") == "true" or headers.get("x-atp-shadow") == "true"
            rec_tid = headers.get("X-ATP-Shadow-Trace") or headers.get("x-atp-shadow-trace")
        elif prot == ProtocolType.GRPC:
            has_flag = headers.get("x-atp-shadow") == "true"
            rec_tid = headers.get("x-atp-shadow-trace")
        else:
            has_flag = headers.get("__atp_shadow_taint__") == "true"
            rec_tid = headers.get("__atp_shadow_trace__")

        is_lost = (not has_flag) or (rec_tid != trace_id)
        if is_lost:
            lost_count += 1
            advice.append(
                f"服务节点 [{s_name}] ({prot.value}) 丢失影子染色标，"
                f"请检查线程池传递 (ThreadLocal)、AsyncContext 或 RPC 过滤器拦截链未透传 Header。"
            )

        hops.append(
            ServiceHopRecord(
                hop_order=idx,
                service_name=s_name,
                protocol=prot,
                received_shadow_flag=has_flag,
                retained_trace_id=rec_tid,
                is_taint_lost=is_lost,
            )
        )

    # 裁决与打分
    total_hops = max(1, len(hops))
    integrity_score = max(0.0, ((total_hops - lost_count) / total_hops) * 100.0)

    if lost_count == 0:
        verdict = PropagationVerdict.FULL_PROPAGATION_SUCCESS
        has_risk = False
        advice.append("全链路影子流量染色标透明透传 100% 闭环，具备生产级全链路压测准入条件。")
    else:
        verdict = PropagationVerdict.TAINT_LEAKAGE_DETECTED
        has_risk = True

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", trace_id)[:16]
    report_id = f"taint_rpt_{safe_name}_{int(now.timestamp())}"

    report = ShadowTaintValidationReport(
        report_id=report_id,
        trace_id=trace_id,
        total_hops_count=total_hops,
        lost_hops_count=lost_count,
        verdict=verdict,
        integrity_score_pct=integrity_score,
        has_leakage_risk=has_risk,
        hops=hops,
        remediation_advice=advice,
        created_at=now,
    )

    _SHADOW_TAINT_REPORTS[report_id] = report
    return report


def get_shadow_taint_report(report_id: str) -> ShadowTaintValidationReport | None:
    """按 ID 查询染色校验报告。"""
    return _SHADOW_TAINT_REPORTS.get(report_id)


def list_shadow_taint_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史染色校验报告列表。"""
    reports = list(reversed(list(_SHADOW_TAINT_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
