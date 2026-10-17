"""灰度流量数据隔离与影子存储防污染校验器服务 (T2.3)

校验全链路金丝雀染色流量写操作是否严格路由至影子库表，防止生产脏数据污染:
1. 影子存储路由与防污染规则定义 (Shadow Table / Shadow DB / Shadow Topic 检验);
2. 生产主库写穿泄漏判定 (CRITICAL_LEAK: 检测到染色流量直接写入生产核心主表);
3. 数据隔离合规率精算 (isolation_compliance_pct = 影子写入数 / 总写操作数);
4. 结构化隔离审计报告输出 (CanaryDataIsolationReport & DataWriteAuditEvent)。
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


class IsolationLeakSeverity(str, enum.Enum):
    CLEAN_ISOLATED = "CLEAN_ISOLATED"  # 100% 隔离合规，染色写操作全量安全路由至影子库表
    WARNING_SUSPICIOUS = "WARNING_SUSPICIOUS"  # 存在可疑非标准表命名或透传标记模糊
    CRITICAL_LEAK = "CRITICAL_LEAK"  # 致命污染泄漏！染色流量直接穿透写入了生产主库主表！


# 生产绝对禁止被直接写入的核心业务主表黑名单 (必须走影子表)
CRITICAL_PRODUCTION_MASTER_TABLES = [
    r"t_order\b",
    r"t_order_item\b",
    r"t_account_balance\b",
    r"t_payment_record\b",
    r"t_billing_settlement\b",
    r"t_user_credential\b",
    r"t_inventory_stock\b",
]

# 合法的影子库表识别特征
SHADOW_TARGET_PATTERNS = [
    r".*_shadow\b",
    r".*_canary\b",
    r".*_sandbox\b",
    r".*shadow_.*",
    r".*sandbox_.*",
]


@dataclass
class DataWriteAuditEvent:
    event_id: str
    target_service: str
    is_canary_traffic: bool
    operation_type: str  # INSERT | UPDATE | DELETE | MQ_PUBLISH
    target_table_or_topic: str
    statement_or_payload: str
    is_shadow_routed: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanaryDataIsolationReport:
    report_id: str
    target_service: str
    total_write_events: int
    shadow_routed_count: int
    leaked_master_writes_count: int
    isolation_compliance_pct: float
    leak_severity: IsolationLeakSeverity
    is_pollution_detected: bool
    leak_incidents: List[DataWriteAuditEvent]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "target_service": self.target_service,
            "total_write_events": self.total_write_events,
            "shadow_routed_count": self.shadow_routed_count,
            "leaked_master_writes_count": self.leaked_master_writes_count,
            "isolation_compliance_pct": round(self.isolation_compliance_pct, 1),
            "leak_severity": self.leak_severity.value,
            "is_pollution_detected": self.is_pollution_detected,
            "leak_incidents": [e.to_dict() for e in self.leak_incidents],
            "generated_at": self.generated_at,
        }


def _is_legitimate_shadow_target(target: str) -> bool:
    """检查表名或 Topic 是否符合影子隔离命名模式"""
    t_lower = target.lower().strip()
    for pat in SHADOW_TARGET_PATTERNS:
        if re.search(pat, t_lower):
            return True
    return False


def _is_critical_master_table(target: str) -> bool:
    """检查是否属于生产敏感核心主表"""
    t_lower = target.lower().strip()
    for pat in CRITICAL_PRODUCTION_MASTER_TABLES:
        if re.search(pat, t_lower):
            return True
    return False


def inspect_canary_data_isolation(
    write_events: List[DataWriteAuditEvent],
    target_service: str = "order-service",
) -> CanaryDataIsolationReport:
    """深度审查金丝雀写操作事件流，判定是否存在生产脏数据污染泄漏"""
    report_id = f"iso_{uuid.uuid4().hex[:10]}"
    if not write_events:
        return CanaryDataIsolationReport(
            report_id=report_id,
            target_service=target_service,
            total_write_events=0,
            shadow_routed_count=0,
            leaked_master_writes_count=0,
            isolation_compliance_pct=100.0,
            leak_severity=IsolationLeakSeverity.CLEAN_ISOLATED,
            is_pollution_detected=False,
            leak_incidents=[],
        )

    shadow_count = 0
    leaks: List[DataWriteAuditEvent] = []
    suspicious_count = 0

    for ev in write_events:
        # 只对金丝雀染色写操作进行影子路由防污染审查
        if not ev.is_canary_traffic:
            continue

        target = ev.target_table_or_topic

        # 1. 检查是否成功路由至合法影子库/表/Topic
        if ev.is_shadow_routed or _is_legitimate_shadow_target(target):
            shadow_count += 1
            ev.is_shadow_routed = True
        else:
            # 2. 未路由至影子表：若直接写入生产核心主表，定性为致命 CRITICAL_LEAK！
            if _is_critical_master_table(target):
                leaks.append(ev)
            else:
                suspicious_count += 1

    canary_writes_total = sum(1 for e in write_events if e.is_canary_traffic)
    if canary_writes_total == 0:
        compliance_pct = 100.0
    else:
        compliance_pct = shadow_count / canary_writes_total * 100.0

    has_leak = len(leaks) > 0
    if has_leak:
        severity = IsolationLeakSeverity.CRITICAL_LEAK
    elif suspicious_count > 0:
        severity = IsolationLeakSeverity.WARNING_SUSPICIOUS
    else:
        severity = IsolationLeakSeverity.CLEAN_ISOLATED

    return CanaryDataIsolationReport(
        report_id=report_id,
        target_service=target_service,
        total_write_events=len(write_events),
        shadow_routed_count=shadow_count,
        leaked_master_writes_count=len(leaks),
        isolation_compliance_pct=compliance_pct,
        leak_severity=severity,
        is_pollution_detected=has_leak,
        leak_incidents=leaks,
    )
