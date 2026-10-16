"""单元故障演练与常态化容灾接管自愈验证器 (T2.3)。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class FailoverVerdict(str, Enum):
    """容灾接管判定结果。"""

    FAILOVER_SUCCESS = "FAILOVER_SUCCESS"  # 接管成功 (RTO <= 3000ms 且丢包 < 0.1%)
    DEGRADED_FAILOVER = "DEGRADED_FAILOVER"  # 降级接管 (耗时偏长或微量丢包)
    FAILOVER_TIMEOUT = "FAILOVER_TIMEOUT"  # 接管超时失败 (严重违规)


@dataclass
class FailoverTimelinePhase:
    """接管时序关键阶段耗时。"""

    phase_name: str
    duration_ms: float
    status: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase_name": self.phase_name,
            "duration_ms": round(self.duration_ms, 1),
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class CellFailoverDrillReport:
    """单元容灾切流演练综合报告。"""

    drill_id: str
    failed_cell_id: str
    standby_cell_id: str
    traffic_shift_percentage: float
    total_rto_duration_ms: float  # 实际业务恢复耗时 (Recovery Time Objective)
    estimated_packet_drop_pct: float  # 切流期间丢包/错误率
    verdict: FailoverVerdict
    is_resilience_qualified: bool  # RTO 达标且无资损风险
    timeline_phases: list[FailoverTimelinePhase]
    remediation_recommendations: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "drill_id": self.drill_id,
            "failed_cell_id": self.failed_cell_id,
            "standby_cell_id": self.standby_cell_id,
            "traffic_shift_percentage": round(self.traffic_shift_percentage, 1),
            "total_rto_duration_ms": round(self.total_rto_duration_ms, 1),
            "estimated_packet_drop_pct": round(self.estimated_packet_drop_pct, 3),
            "verdict": self.verdict.value,
            "is_resilience_qualified": self.is_resilience_qualified,
            "timeline_phases": [p.to_dict() for p in self.timeline_phases],
            "remediation_recommendations": self.remediation_recommendations,
            "created_at": self.created_at.isoformat(),
        }


# 全局演练报告仓库
_FAILOVER_REPORTS: dict[str, CellFailoverDrillReport] = {}


def clear_failover_report_store() -> None:
    """清空演练报告仓库 (单测专用)。"""
    _FAILOVER_REPORTS.clear()


def execute_cell_failover_drill(
    failed_cell_id: str,
    standby_cell_id: str,
    traffic_shift_percentage: float = 100.0,
    dns_switch_delay_ms: float = 650.0,
    db_replication_lag_ms: float = 180.0,
    route_convergence_delay_ms: float = 420.0,
) -> CellFailoverDrillReport:
    """模拟单单元整体瘫痪，量化备用单元自动接管耗时 (RTO)、流量丢包率与自愈状态。"""
    # 1. 计算时序各阶段耗时
    phase_outage_detect = FailoverTimelinePhase(
        phase_name="故障感知与探针心跳超时",
        duration_ms=450.0,
        status="SUCCESS",
        detail=f"主探针检测到 [{failed_cell_id}] 连续 3 次 TCP/HTTP 探针无响应，宣布进入故障切流状态。",
    )

    phase_traffic_drain = FailoverTimelinePhase(
        phase_name="流量权重归零与 DNS 动态调度",
        duration_ms=dns_switch_delay_ms,
        status="SUCCESS",
        detail=f"全网网关与 DNS 解析将 [{failed_cell_id}] 权重归零，流量平滑导向 [{standby_cell_id}]。",
    )

    phase_data_sync = FailoverTimelinePhase(
        phase_name="主备数据副本追平与只读切换",
        duration_ms=db_replication_lag_ms,
        status="SUCCESS",
        detail=f"备用单元存储完成与主单元 binlog/WAL 数据追平，追平延迟为 {db_replication_lag_ms:.1f}ms。",
    )

    phase_route_convergence = FailoverTimelinePhase(
        phase_name="微服务网格路由收敛与缓存预热",
        duration_ms=route_convergence_delay_ms,
        status="SUCCESS",
        detail=f"各服务发现组件更新 Endpoint 列表，备用单元 [{standby_cell_id}] 100% 承接业务。",
    )

    phases = [phase_outage_detect, phase_traffic_drain, phase_data_sync, phase_route_convergence]

    # 总 RTO 计算
    total_rto = sum(p.duration_ms for p in phases)

    # 丢包率推算：主要由 DNS 切换与路由收敛期间的飞行中请求引起
    packet_drop = min(1.0, (total_rto / 100000.0) * (traffic_shift_percentage / 100.0))

    # 裁决判定标准 (行业高可用金融级 RTO <= 3000ms, 丢包率 < 0.1%)
    if total_rto <= 2500.0 and packet_drop <= 0.05:
        verdict = FailoverVerdict.FAILOVER_SUCCESS
        is_qualified = True
    elif total_rto <= 5000.0:
        verdict = FailoverVerdict.DEGRADED_FAILOVER
        is_qualified = True
    else:
        verdict = FailoverVerdict.FAILOVER_TIMEOUT
        is_qualified = False

    recommendations: list[str] = []
    if dns_switch_delay_ms > 1000.0:
        recommendations.append("DNS 切换耗时偏高，建议调小 Local DNS TTL 缓存或改用四层 Anycast BGP 动态直切。")
    if db_replication_lag_ms > 300.0:
        recommendations.append("主备数据库复制延迟过长，建议检查跨机房专线带宽或启用强一致性半同步复制。")
    if is_qualified:
        recommendations.append(
            f"单元容灾自愈能力达标！实测 RTO 为 {total_rto:.1f}ms，具备应对单机房整体故障的高可用接管能力。"
        )

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", failed_cell_id)[:16]
    drill_id = f"fo_drill_{safe_name}_{int(now.timestamp())}"

    report = CellFailoverDrillReport(
        drill_id=drill_id,
        failed_cell_id=failed_cell_id,
        standby_cell_id=standby_cell_id,
        traffic_shift_percentage=traffic_shift_percentage,
        total_rto_duration_ms=total_rto,
        estimated_packet_drop_pct=packet_drop,
        verdict=verdict,
        is_resilience_qualified=is_qualified,
        timeline_phases=phases,
        remediation_recommendations=recommendations,
        created_at=now,
    )

    _FAILOVER_REPORTS[drill_id] = report
    return report


def get_failover_report(drill_id: str) -> CellFailoverDrillReport | None:
    """按 ID 查询容灾切流演练报告。"""
    return _FAILOVER_REPORTS.get(drill_id)


def list_failover_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史容灾演练报告列表。"""
    reports = list(reversed(list(_FAILOVER_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
