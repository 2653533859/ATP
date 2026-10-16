"""异常失败根因智能聚类与自愈执行流水审计服务 (D2.3).

对测试用例执行中的异常错误栈执行特征归一化与相似度聚类分析，
将多用例同因故障聚合为故障簇（Fault Cluster），并记录全生命周期自愈执行流水与成效度量。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import logging
import re
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class HealingActionType(str, Enum):
    LOCATOR_REPLACED = "locator_replaced"
    SCHEMA_AUTOFIXED = "schema_autofixed"
    ASSERTION_TOLERATED = "assertion_tolerated"
    RETRY_WITH_BACKOFF = "retry_with_backoff"


class HealingVerificationStatus(str, Enum):
    VERIFIED_SUCCESS = "verified_success"
    VERIFIED_FAILURE = "verified_failure"
    PENDING_VERIFY = "pending_verify"
    AUTO_ACCEPTED = "auto_accepted"


@dataclass
class FaultCluster:
    cluster_id: str
    signature: str
    primary_exception: str
    root_cause_summary: str
    occurrences_count: int = 1
    affected_case_ids: list[int] = field(default_factory=list)
    affected_run_ids: list[int] = field(default_factory=list)
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    suggested_healing_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "signature": self.signature,
            "primary_exception": self.primary_exception,
            "root_cause_summary": self.root_cause_summary,
            "occurrences_count": self.occurrences_count,
            "affected_case_ids": list(set(self.affected_case_ids)),
            "affected_run_ids": list(set(self.affected_run_ids)),
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "suggested_healing_action": self.suggested_healing_action,
        }


@dataclass
class HealingAuditEntry:
    audit_id: str
    case_id: int
    step_name: str
    action_type: HealingActionType
    original_value: Any
    healed_value: Any
    confidence_score: float
    verification_status: HealingVerificationStatus = HealingVerificationStatus.VERIFIED_SUCCESS
    cluster_id: str | None = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "case_id": self.case_id,
            "step_name": self.step_name,
            "action_type": self.action_type.value,
            "original_value": self.original_value,
            "healed_value": self.healed_value,
            "confidence_score": round(self.confidence_score, 4),
            "verification_status": self.verification_status.value,
            "cluster_id": self.cluster_id,
            "executed_at": self.executed_at.isoformat(),
            "duration_ms": round(self.duration_ms, 2),
            "metadata": self.metadata,
        }


# 内存故障簇库与自愈流水台账
_FAULT_CLUSTERS: dict[str, FaultCluster] = {}
_HEALING_AUDIT_TRAIL: list[HealingAuditEntry] = []

# 正则表达式：用于消除动态 UUID、十六进制内存地址与时间戳噪声
_UUID_REGEX = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_HEX_ADDR_REGEX = re.compile(r"0x[0-9a-fA-F]+")
_DIGITS_REGEX = re.compile(r"\b\d{4,}\b")


def normalize_error_signature(
    exception_type: str,
    error_message: str,
    stack_trace: str | None = None,
) -> str:
    """提取核心异常栈特征，清洗动态噪声并生成标准化指纹哈希。"""
    clean_msg = _UUID_REGEX.sub("<UUID>", error_message)
    clean_msg = _HEX_ADDR_REGEX.sub("<HEX>", clean_msg)
    clean_msg = _DIGITS_REGEX.sub("<NUM>", clean_msg)

    # 截取前 200 字符的核心错误行
    first_line = clean_msg.strip().split("\n")[0][:200]

    normalized_raw = f"{exception_type.strip()}::{first_line}"
    if stack_trace:
        # 取调用栈最关键的第一帧或最后异常帧
        stack_lines = [line.strip() for line in stack_trace.splitlines() if "File " in line or "at " in line]
        if stack_lines:
            normalized_raw += f"::{stack_lines[-1][:120]}"

    return hashlib.sha256(normalized_raw.encode("utf-8")).hexdigest()[:16]


def cluster_error_event(
    case_id: int,
    run_id: int,
    exception_type: str,
    error_message: str,
    stack_trace: str | None = None,
    root_cause_hint: str | None = None,
) -> FaultCluster:
    """对单次执行失败进行特征归一化，自动聚合至既有故障簇或开辟新故障簇。"""
    sig = normalize_error_signature(exception_type, error_message, stack_trace)
    now = datetime.now(timezone.utc)

    if sig in _FAULT_CLUSTERS:
        cluster = _FAULT_CLUSTERS[sig]
        cluster.occurrences_count += 1
        if case_id not in cluster.affected_case_ids:
            cluster.affected_case_ids.append(case_id)
        if run_id not in cluster.affected_run_ids:
            cluster.affected_run_ids.append(run_id)
        cluster.last_seen = now
        logger.info(
            "Aggregated error to existing cluster cluster_id=%s count=%s", cluster.cluster_id, cluster.occurrences_count
        )
        return cluster

    cluster_id = f"cluster_{exception_type}_{sig[:8]}"
    summary = root_cause_hint or f"[{exception_type}] {error_message.strip().splitlines()[0][:100]}"
    suggested = (
        "执行定位器差分自愈"
        if "NoSuchElement" in exception_type
        else "执行 Schema 柔性漂移修正"
        if "Assertion" in exception_type
        else "建议重试重放"
    )

    new_cluster = FaultCluster(
        cluster_id=cluster_id,
        signature=sig,
        primary_exception=exception_type,
        root_cause_summary=summary,
        occurrences_count=1,
        affected_case_ids=[case_id],
        affected_run_ids=[run_id],
        first_seen=now,
        last_seen=now,
        suggested_healing_action=suggested,
    )

    _FAULT_CLUSTERS[sig] = new_cluster
    logger.info("Created new fault cluster cluster_id=%s signature=%s", cluster_id, sig)
    return new_cluster


def record_healing_action(
    case_id: int,
    step_name: str,
    action_type: HealingActionType,
    original_value: Any,
    healed_value: Any,
    confidence_score: float,
    verification_status: HealingVerificationStatus = HealingVerificationStatus.VERIFIED_SUCCESS,
    cluster_id: str | None = None,
    duration_ms: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> HealingAuditEntry:
    """记录一次用例自愈执行动作流水并关联故障簇。"""
    audit_id = f"audit_act_{uuid.uuid4().hex[:12]}"
    entry = HealingAuditEntry(
        audit_id=audit_id,
        case_id=case_id,
        step_name=step_name,
        action_type=action_type,
        original_value=original_value,
        healed_value=healed_value,
        confidence_score=confidence_score,
        verification_status=verification_status,
        cluster_id=cluster_id,
        duration_ms=duration_ms,
        metadata=metadata or {},
    )

    _HEALING_AUDIT_TRAIL.append(entry)
    logger.info(
        "Recorded healing action audit_id=%s case_id=%s type=%s confidence=%s",
        audit_id,
        case_id,
        action_type.value,
        confidence_score,
    )
    return entry


def list_fault_clusters() -> list[FaultCluster]:
    """查询所有归纳聚合的故障簇列表。"""
    return list(_FAULT_CLUSTERS.values())


def get_fault_cluster(cluster_id: str) -> FaultCluster | None:
    """根据 ID 获取指定故障簇。"""
    for c in _FAULT_CLUSTERS.values():
        if c.cluster_id == cluster_id:
            return c
    return None


def list_healing_audit_entries(
    case_id: int | None = None,
    action_type: HealingActionType | None = None,
) -> list[HealingAuditEntry]:
    """多维查询自愈执行流水记录。"""
    entries = list(_HEALING_AUDIT_TRAIL)
    if case_id is not None:
        entries = [e for e in entries if e.case_id == case_id]
    if action_type is not None:
        entries = [e for e in entries if e.action_type == action_type]
    return entries


def calculate_healing_metrics() -> dict[str, Any]:
    """统计全生命周期自愈成效、二次验证成功率与估算节省工时。"""
    total = len(_HEALING_AUDIT_TRAIL)
    if total == 0:
        return {
            "total_healing_actions_count": 0,
            "verification_success_rate_pct": 100.0,
            "average_confidence_score": 0.0,
            "total_fault_clusters_count": len(_FAULT_CLUSTERS),
            "estimated_engineering_hours_saved": 0.0,
        }

    verified_success = sum(
        1
        for e in _HEALING_AUDIT_TRAIL
        if e.verification_status
        in {HealingVerificationStatus.VERIFIED_SUCCESS, HealingVerificationStatus.AUTO_ACCEPTED}
    )
    success_rate = (verified_success / float(total)) * 100.0
    avg_confidence = sum(e.confidence_score for e in _HEALING_AUDIT_TRAIL) / float(total)

    # 估算节省工时：假设平均每次人工定位排查与修改用例耗时 20 分钟 (0.33 小时)
    hours_saved = verified_success * 0.33

    return {
        "total_healing_actions_count": total,
        "verification_success_rate_pct": round(success_rate, 2),
        "average_confidence_score": round(avg_confidence, 4),
        "total_fault_clusters_count": len(_FAULT_CLUSTERS),
        "estimated_engineering_hours_saved": round(hours_saved, 2),
    }


def reset_healing_audit_registry() -> None:
    """仅供单元测试清理状态使用。"""
    _FAULT_CLUSTERS.clear()
    _HEALING_AUDIT_TRAIL.clear()
