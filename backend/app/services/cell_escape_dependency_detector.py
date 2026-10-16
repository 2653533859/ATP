"""跨单元服务依赖逃逸 (Cell Escape) 与拓扑孤岛检测器 (T2.2)。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EscapeViolationType(str, Enum):
    """跨单元逃逸违规分类。"""

    SHADOW_TRAFFIC_ESCAPE = "SHADOW_TRAFFIC_ESCAPE"  # 影子压测流量逃逸至生产单元 (致命阻断)
    CROSS_CELL_RPC_ESCAPE = "CROSS_CELL_RPC_ESCAPE"  # 跨单元服务越界远程调用
    SHARED_RESOURCE_CONTAMINATION = "SHARED_RESOURCE_CONTAMINATION"  # 混用未隔离全局共享存储
    ORPHAN_TOPOLOGY_ISLAND = "ORPHAN_TOPOLOGY_ISLAND"  # 缺乏自治闭环的拓扑孤岛依赖


class EscapeSeverity(str, Enum):
    """逃逸缺陷严重度。"""

    CRITICAL = "CRITICAL"  # 压测影子流量逃逸到生产单元
    HIGH = "HIGH"  # 跨单元写共享数据源或直连跨单元 RPC
    MEDIUM = "MEDIUM"  # 跨单元只读查询
    LOW = "LOW"  # 次要架构优化建议


@dataclass
class CellEscapeViolationItem:
    """单个单元逃逸违规明细。"""

    violation_id: str
    violation_type: EscapeViolationType
    severity: EscapeSeverity
    source_cell: str
    target_cell: str
    service_or_resource: str
    description: str
    remediation_suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_id": self.violation_id,
            "violation_type": self.violation_type.value,
            "severity": self.severity.value,
            "source_cell": self.source_cell,
            "target_cell": self.target_cell,
            "service_or_resource": self.service_or_resource,
            "description": self.description,
            "remediation_suggestion": self.remediation_suggestion,
        }


@dataclass
class CellEscapeAuditReport:
    """单元化依赖逃逸全景审计报告。"""

    report_id: str
    topology_name: str
    total_edges_checked: int
    total_escapes_count: int
    shadow_escapes_count: int
    isolation_purity_score_pct: float
    is_strictly_cell_isolated: bool
    violations: list[CellEscapeViolationItem]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "topology_name": self.topology_name,
            "total_edges_checked": self.total_edges_checked,
            "total_escapes_count": self.total_escapes_count,
            "shadow_escapes_count": self.shadow_escapes_count,
            "isolation_purity_score_pct": round(self.isolation_purity_score_pct, 1),
            "is_strictly_cell_isolated": self.is_strictly_cell_isolated,
            "violations": [v.to_dict() for v in self.violations],
            "created_at": self.created_at.isoformat(),
        }


# 全局审计报告仓库
_CELL_ESCAPE_REPORTS: dict[str, CellEscapeAuditReport] = {}


def clear_cell_escape_store() -> None:
    """清空单元逃逸报告仓库 (单测专用)。"""
    _CELL_ESCAPE_REPORTS.clear()


def detect_cell_escapes(
    topology_name: str,
    invocation_edges: list[dict[str, Any]],
) -> CellEscapeAuditReport:
    """分析微服务拓扑调用边，深度探查跨单元跨界 RPC、共享资源混用与影子流量逃逸。"""
    violations: list[CellEscapeViolationItem] = []
    shadow_escapes = 0

    for edge in invocation_edges:
        src_cell = str(edge.get("source_cell_id") or "cell_default").strip()
        tgt_cell = str(edge.get("target_cell_id") or "cell_default").strip()
        src_svc = str(edge.get("source_service") or "service_a").strip()
        tgt_svc = str(edge.get("target_service") or "service_b").strip()
        res_type = str(edge.get("target_resource_type") or "MICROSERVICE_RPC").upper()
        is_shadow = bool(edge.get("is_shadow_traffic", False))
        is_shared = bool(edge.get("is_shared_resource", False))

        # 1. 检查影子压测流量是否逃逸至生产单元 (CRITICAL)
        if is_shadow and src_cell != tgt_cell and ("prod" in tgt_cell.lower() or "east" in tgt_cell.lower()):
            shadow_escapes += 1
            violations.append(
                CellEscapeViolationItem(
                    violation_id=f"esc_{uuid.uuid4().hex[:6]}",
                    violation_type=EscapeViolationType.SHADOW_TRAFFIC_ESCAPE,
                    severity=EscapeSeverity.CRITICAL,
                    source_cell=src_cell,
                    target_cell=tgt_cell,
                    service_or_resource=f"{src_svc} -> {tgt_svc}",
                    description=f"高危！压测影子流量由 [{src_cell}] 逃逸跨入生产活跃单元 [{tgt_cell}]，严重破坏压测安全红线！",
                    remediation_suggestion="在网关与服务发现层强制配置单元就近访问路由规则，严禁压测跨单元下发。",
                )
            )

        # 2. 检查跨单元直接 RPC 调用 (违背单元化内部自治)
        if src_cell != tgt_cell and not is_shadow and res_type == "MICROSERVICE_RPC":
            violations.append(
                CellEscapeViolationItem(
                    violation_id=f"esc_{uuid.uuid4().hex[:6]}",
                    violation_type=EscapeViolationType.CROSS_CELL_RPC_ESCAPE,
                    severity=EscapeSeverity.HIGH,
                    source_cell=src_cell,
                    target_cell=tgt_cell,
                    service_or_resource=f"{src_svc} -> {tgt_svc}",
                    description=f"检测到跨单元直接远程调用 [{src_cell}] -> [{tgt_cell}]，破坏了单元独立性与自愈隔离能力。",
                    remediation_suggestion="检查该服务是否应在各 Cell 内独立全量部署，或通过异步 MQ 消息解耦解开强依赖。",
                )
            )

        # 3. 检查混用共享全局非隔离资源 (如共享单点数据库/Redis)
        if is_shared and res_type in ("DATABASE", "REDIS_CACHE"):
            violations.append(
                CellEscapeViolationItem(
                    violation_id=f"esc_{uuid.uuid4().hex[:6]}",
                    violation_type=EscapeViolationType.SHARED_RESOURCE_CONTAMINATION,
                    severity=EscapeSeverity.HIGH,
                    source_cell=src_cell,
                    target_cell=tgt_cell,
                    service_or_resource=f"{tgt_svc} ({res_type})",
                    description=f"单元 [{src_cell}] 混用了全局共享数据源 [{tgt_svc}]，单点过载将导致所有单元发生雪崩连带故障。",
                    remediation_suggestion="将数据库与缓存依据用户分片下沉至各业务单元专属数据切片，避免单点争用。",
                )
            )

    # 隔离纯度得分
    total_edges = max(1, len(invocation_edges))
    crit_count = sum(1 for v in violations if v.severity == EscapeSeverity.CRITICAL)
    high_count = sum(1 for v in violations if v.severity == EscapeSeverity.HIGH)
    med_count = sum(1 for v in violations if v.severity == EscapeSeverity.MEDIUM)

    penalty = (crit_count * 40.0) + (high_count * 20.0) + (med_count * 10.0)
    purity_score = max(0.0, min(100.0, 100.0 - penalty))

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", topology_name)[:16]
    report_id = f"esc_rpt_{safe_name}_{int(now.timestamp())}"

    report = CellEscapeAuditReport(
        report_id=report_id,
        topology_name=topology_name,
        total_edges_checked=total_edges,
        total_escapes_count=len(violations),
        shadow_escapes_count=shadow_escapes,
        isolation_purity_score_pct=purity_score,
        is_strictly_cell_isolated=(len(violations) == 0),
        violations=violations,
        created_at=now,
    )

    _CELL_ESCAPE_REPORTS[report_id] = report
    return report


def get_cell_escape_report(report_id: str) -> CellEscapeAuditReport | None:
    """按 ID 查询逃逸审计报告。"""
    return _CELL_ESCAPE_REPORTS.get(report_id)


def list_cell_escape_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史逃逸审计报告列表。"""
    reports = list(reversed(list(_CELL_ESCAPE_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
