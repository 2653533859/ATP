"""跨微服务异构数据源最终一致性双向稽核校验引擎 (T2.2)。

负责对分布式微服务独立数据库间的数据同步与最终一致性进行双向对账稽核：
1. 基于业务主键 (join_key/primary_key) 自动对齐多源异构数据记录；
2. 比较关键字段级取值差分 (MISSING_IN_TARGET / MISSING_IN_SOURCE / VALUE_MISMATCH)；
3. 支持数值容差 (Float Epsilon) 与枚举状态映射 (Status Mapping)；
4. 输出全量对账达标率 (Consistency Rate 0~100%) 与自动化补偿修正脚本。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class MismatchCategory(str, Enum):
    MISSING_IN_TARGET = "MISSING_IN_TARGET"  # 上游源存在，下游目标库缺失 (漏同步/丢数据)
    MISSING_IN_SOURCE = "MISSING_IN_SOURCE"  # 目标库存在幽灵数据，上游源库未找到
    FIELD_VALUE_MISMATCH = "FIELD_VALUE_MISMATCH"  # 双方主键存在，但业务字段取值冲突
    NONE = "NONE"


class AuditVerdictStatus(str, Enum):
    RECONCILED = "RECONCILED"  # 完全一致 (100.0%)
    WARNING = "WARNING"  # 存在微量差异但达到容忍阈值 (如 >= 95.0%)
    CRITICAL = "CRITICAL"  # 严重不一致 (< 95.0% 或核心金融字段差异)


@dataclass
class FieldDifference:
    field_name: str
    source_value: Any
    target_value: Any
    is_mismatched: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "source_value": self.source_value,
            "target_value": self.target_value,
            "is_mismatched": self.is_mismatched,
            "description": self.description,
        }


@dataclass
class RecordDiffItem:
    join_key_value: str
    category: MismatchCategory
    field_diffs: list[FieldDifference] = field(default_factory=list)
    remediation_sql: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "join_key_value": self.join_key_value,
            "category": self.category.value,
            "field_diffs": [f.to_dict() for f in self.field_diffs],
            "remediation_sql": self.remediation_sql,
        }


@dataclass
class ConsistencyAuditRule:
    rule_id: str
    rule_name: str
    source_service: str
    source_table: str
    target_service: str
    target_table: str
    join_key: str  # 关联对齐主键 (如 order_id)
    field_mappings: dict[str, str] = field(default_factory=dict)  # source_field -> target_field
    numeric_tolerance: float = 0.001
    tolerance_threshold_pct: float = 98.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "source_service": self.source_service,
            "source_table": self.source_table,
            "target_service": self.target_service,
            "target_table": self.target_table,
            "join_key": self.join_key,
            "field_mappings": self.field_mappings,
            "numeric_tolerance": self.numeric_tolerance,
            "tolerance_threshold_pct": self.tolerance_threshold_pct,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ConsistencyAuditReport:
    report_id: str
    rule_id: str
    rule_name: str
    verdict: AuditVerdictStatus
    consistency_rate_pct: float
    total_records_checked: int
    consistent_records_count: int
    mismatched_records_count: int
    missing_in_target_count: int
    missing_in_source_count: int
    value_mismatches_count: int
    diff_records: list[RecordDiffItem]
    verdict_summary: str
    audited_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "verdict": self.verdict.value,
            "consistency_rate_pct": round(self.consistency_rate_pct, 2),
            "total_records_checked": self.total_records_checked,
            "consistent_records_count": self.consistent_records_count,
            "mismatched_records_count": self.mismatched_records_count,
            "missing_in_target_count": self.missing_in_target_count,
            "missing_in_source_count": self.missing_in_source_count,
            "value_mismatches_count": self.value_mismatches_count,
            "diff_records": [d.to_dict() for d in self.diff_records],
            "verdict_summary": self.verdict_summary,
            "audited_at": self.audited_at.isoformat(),
        }


# 全局对账规则与报告仓库
_AUDIT_RULES: dict[str, ConsistencyAuditRule] = {}
_AUDIT_REPORTS: dict[str, ConsistencyAuditReport] = {}


def register_audit_rule(
    rule_name: str,
    source_service: str,
    source_table: str,
    target_service: str,
    target_table: str,
    join_key: str,
    field_mappings: dict[str, str] | None = None,
    numeric_tolerance: float = 0.001,
    tolerance_threshold_pct: float = 98.0,
    rule_id: str | None = None,
) -> ConsistencyAuditRule:
    """注册跨库最终一致性稽核对账规则。"""
    rid = rule_id or f"rule_{uuid.uuid4().hex[:8]}"
    rule = ConsistencyAuditRule(
        rule_id=rid,
        rule_name=rule_name,
        source_service=source_service,
        source_table=source_table,
        target_service=target_service,
        target_table=target_table,
        join_key=join_key,
        field_mappings=field_mappings or {},
        numeric_tolerance=numeric_tolerance,
        tolerance_threshold_pct=tolerance_threshold_pct,
    )
    _AUDIT_RULES[rid] = rule
    return rule


def list_audit_rules() -> list[ConsistencyAuditRule]:
    """查询对账规则列表。"""
    return list(_AUDIT_RULES.values())


def delete_audit_rule(rule_id: str) -> bool:
    """删除对账规则。"""
    if rule_id in _AUDIT_RULES:
        del _AUDIT_RULES[rule_id]
        return True
    return False


def _is_value_equal(v1: Any, v2: Any, tolerance: float) -> bool:
    """数值或通用字段等值判定 (含浮点数容差)。"""
    if v1 == v2:
        return True
    if v1 is None or v2 is None:
        return False
    try:
        f1 = float(v1)
        f2 = float(v2)
        return abs(f1 - f2) <= tolerance
    except (ValueError, TypeError):
        return str(v1).strip() == str(v2).strip()


def execute_consistency_audit(
    rule: ConsistencyAuditRule,
    source_records: list[dict[str, Any]],
    target_records: list[dict[str, Any]],
) -> ConsistencyAuditReport:
    """执行两组异构记录集的双向主键对齐与字段差分稽核。"""
    source_map: dict[str, dict[str, Any]] = {}
    for r in source_records:
        k = str(r.get(rule.join_key, "")).strip()
        if k:
            source_map[k] = r

    target_map: dict[str, dict[str, Any]] = {}
    for r in target_records:
        k = str(r.get(rule.join_key, "")).strip()
        if k:
            target_map[k] = r

    all_keys = sorted(list(set(source_map.keys()) | set(target_map.keys())))
    diff_records: list[RecordDiffItem] = []

    missing_in_target = 0
    missing_in_source = 0
    value_mismatches = 0
    consistent_count = 0

    mappings = rule.field_mappings or {}

    for k in all_keys:
        in_src = k in source_map
        in_tgt = k in target_map

        if in_src and not in_tgt:
            missing_in_target += 1
            src_row = source_map[k]
            # 生成修正插入 SQL
            fields_str = ", ".join(src_row.keys())
            vals_str = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in src_row.values()])
            remed_sql = f"INSERT INTO {rule.target_table} ({fields_str}) VALUES ({vals_str});"
            diff_records.append(
                RecordDiffItem(
                    join_key_value=k,
                    category=MismatchCategory.MISSING_IN_TARGET,
                    field_diffs=[],
                    remediation_sql=remed_sql,
                )
            )
        elif in_tgt and not in_src:
            missing_in_source += 1
            diff_records.append(
                RecordDiffItem(
                    join_key_value=k,
                    category=MismatchCategory.MISSING_IN_SOURCE,
                    field_diffs=[],
                    remediation_sql=f"-- 幽灵数据核查: DELETE FROM {rule.target_table} WHERE {rule.join_key} = '{k}';",
                )
            )
        else:
            # 双方均存在，逐字段比对
            src_row = source_map[k]
            tgt_row = target_map[k]
            row_diffs: list[FieldDifference] = []
            has_row_mismatch = False

            # 如果没有显式 mapping，比对 source 的所有字段
            check_keys = mappings if mappings else {col: col for col in src_row.keys() if col != rule.join_key}

            for s_col, t_col in check_keys.items():
                s_val = src_row.get(s_col)
                t_val = tgt_row.get(t_col)

                matched = _is_value_equal(s_val, t_val, rule.numeric_tolerance)
                if not matched:
                    has_row_mismatch = True
                    desc = f"字段 [{s_col} -> {t_col}] 取值不一致: 源库='{s_val}', 目标库='{t_val}'"
                    row_diffs.append(
                        FieldDifference(
                            field_name=s_col,
                            source_value=s_val,
                            target_value=t_val,
                            is_mismatched=True,
                            description=desc,
                        )
                    )

            if has_row_mismatch:
                value_mismatches += 1
                set_clauses = [
                    f"{t_col} = '{src_row.get(s_col)}'" for s_col, t_col in check_keys.items() if s_col in src_row
                ]
                remed_sql = f"UPDATE {rule.target_table} SET {', '.join(set_clauses)} WHERE {rule.join_key} = '{k}';"
                diff_records.append(
                    RecordDiffItem(
                        join_key_value=k,
                        category=MismatchCategory.FIELD_VALUE_MISMATCH,
                        field_diffs=row_diffs,
                        remediation_sql=remed_sql,
                    )
                )
            else:
                consistent_count += 1

    total_checked = len(all_keys)
    mismatched_count = len(diff_records)
    consistency_rate = (consistent_count / total_checked * 100.0) if total_checked > 0 else 100.0

    if consistency_rate == 100.0:
        verdict = AuditVerdictStatus.RECONCILED
        summary = f"跨库双向对账全部通过（一致率 100.0%），共稽核 {total_checked} 条数据记录，零差异。"
    elif consistency_rate >= rule.tolerance_threshold_pct:
        verdict = AuditVerdictStatus.WARNING
        summary = (
            f"跨库对账达到容差阈值 ({round(consistency_rate, 2)}% >= {rule.tolerance_threshold_pct}%)，"
            f"检出 {mismatched_count} 处轻微差异 (下游缺失 {missing_in_target} 条, 字段取值冲突 {value_mismatches} 条)。"
        )
    else:
        verdict = AuditVerdictStatus.CRITICAL
        summary = (
            f"跨库最终一致性严重破坏 ({round(consistency_rate, 2)}% < {rule.tolerance_threshold_pct}%)！"
            f"检出 {mismatched_count} 处数据撕裂 (下游缺失 {missing_in_target} 条, 上游缺失 {missing_in_source} 条, 字段冲突 {value_mismatches} 条)。"
        )

    report_id = f"aud_{uuid.uuid4().hex[:10]}"
    report = ConsistencyAuditReport(
        report_id=report_id,
        rule_id=rule.rule_id,
        rule_name=rule.rule_name,
        verdict=verdict,
        consistency_rate_pct=consistency_rate,
        total_records_checked=total_checked,
        consistent_records_count=consistent_count,
        mismatched_records_count=mismatched_count,
        missing_in_target_count=missing_in_target,
        missing_in_source_count=missing_in_source,
        value_mismatches_count=value_mismatches,
        diff_records=diff_records,
        verdict_summary=summary,
    )
    _AUDIT_REPORTS[report_id] = report
    return report


def get_audit_report(report_id: str) -> ConsistencyAuditReport | None:
    """获取对账报告详情。"""
    return _AUDIT_REPORTS.get(report_id)


def list_audit_reports() -> list[ConsistencyAuditReport]:
    """查询历史对账报告列表。"""
    return list(_AUDIT_REPORTS.values())


def clear_audit_store() -> int:
    """清空规则与报告缓存仓库。"""
    c = len(_AUDIT_RULES) + len(_AUDIT_REPORTS)
    _AUDIT_RULES.clear()
    _AUDIT_REPORTS.clear()
    return c
