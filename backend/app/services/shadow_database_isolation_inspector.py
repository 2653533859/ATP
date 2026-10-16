"""影子数据库/影子表路由拦截与读写防污染安全隔离检查器 (T1.2)。"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class IsolationStrategy(str, Enum):
    """影子存储隔离策略枚举。"""

    SHADOW_TABLE = "SHADOW_TABLE"  # 影子表隔离 (例如 t_order -> __shadow_t_order__)
    SHADOW_DATABASE = "SHADOW_DATABASE"  # 影子库隔离 (例如 order_prod -> order_shadow)
    SHADOW_SCHEMA = "SHADOW_SCHEMA"  # 影子模式/Schema 隔离


class SqlRoutingVerdict(str, Enum):
    """SQL 拦截与路由判定。"""

    ROUTED_TO_SHADOW = "ROUTED_TO_SHADOW"  # 成功重写路由至影子库/表
    BLOCKED_PROD_POLLUTION_ATTEMPT = "BLOCKED_PROD_POLLUTION_ATTEMPT"  # 阻断压测脏数据污染生产真实表
    SAFE_PROD_PASSTHROUGH = "SAFE_PROD_PASSTHROUGH"  # 正常生产业务流量安全放行
    READ_ONLY_SAFE = "READ_ONLY_SAFE"  # 只读查询安全透传


@dataclass
class ShadowTableMapping:
    """生产表到影子表映射规则。"""

    mapping_id: str
    production_table: str
    shadow_table: str
    isolation_strategy: IsolationStrategy
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "production_table": self.production_table,
            "shadow_table": self.shadow_table,
            "isolation_strategy": self.isolation_strategy.value,
            "is_active": self.is_active,
        }


@dataclass
class SqlRoutingInspectionItem:
    """单条 SQL 路由拦截判定明细。"""

    item_id: str
    original_sql: str
    is_shadow_traffic: bool
    is_write_operation: bool
    detected_target_table: str
    verdict: SqlRoutingVerdict
    rewritten_sql: str | None
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "original_sql": self.original_sql,
            "is_shadow_traffic": self.is_shadow_traffic,
            "is_write_operation": self.is_write_operation,
            "detected_target_table": self.detected_target_table,
            "verdict": self.verdict.value,
            "rewritten_sql": self.rewritten_sql,
            "explanation": self.explanation,
        }


@dataclass
class DbIsolationAuditReport:
    """影子库表防污染隔离安全全景报告。"""

    report_id: str
    target_cluster: str
    total_queries_checked: int
    routed_to_shadow_count: int
    blocked_pollution_count: int
    safe_passthrough_count: int
    isolation_safety_score_pct: float
    has_critical_pollution_risk: bool
    inspections: list[SqlRoutingInspectionItem]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "target_cluster": self.target_cluster,
            "total_queries_checked": self.total_queries_checked,
            "routed_to_shadow_count": self.routed_to_shadow_count,
            "blocked_pollution_count": self.blocked_pollution_count,
            "safe_passthrough_count": self.safe_passthrough_count,
            "isolation_safety_score_pct": round(self.isolation_safety_score_pct, 1),
            "has_critical_pollution_risk": self.has_critical_pollution_risk,
            "inspections": [i.to_dict() for i in self.inspections],
            "created_at": self.created_at.isoformat(),
        }


# 全局默认影子表映射配置仓库
_SHADOW_MAPPINGS: dict[str, ShadowTableMapping] = {
    "t_order": ShadowTableMapping("map_01", "t_order", "__shadow_t_order__", IsolationStrategy.SHADOW_TABLE),
    "t_payment": ShadowTableMapping("map_02", "t_payment", "__shadow_t_payment__", IsolationStrategy.SHADOW_TABLE),
    "t_inventory": ShadowTableMapping(
        "map_03", "t_inventory", "__shadow_t_inventory__", IsolationStrategy.SHADOW_TABLE
    ),
}

# 全局审计报告存储
_DB_ISOLATION_REPORTS: dict[str, DbIsolationAuditReport] = {}


def clear_db_isolation_store() -> None:
    """清空影子库表映射与报告仓库 (单测专用)。"""
    _DB_ISOLATION_REPORTS.clear()
    _SHADOW_MAPPINGS.clear()
    _SHADOW_MAPPINGS.update(
        {
            "t_order": ShadowTableMapping("map_01", "t_order", "__shadow_t_order__", IsolationStrategy.SHADOW_TABLE),
            "t_payment": ShadowTableMapping(
                "map_02", "t_payment", "__shadow_t_payment__", IsolationStrategy.SHADOW_TABLE
            ),
            "t_inventory": ShadowTableMapping(
                "map_03", "t_inventory", "__shadow_t_inventory__", IsolationStrategy.SHADOW_TABLE
            ),
        }
    )


def register_shadow_mapping(
    production_table: str,
    shadow_table: str,
    strategy: IsolationStrategy = IsolationStrategy.SHADOW_TABLE,
) -> ShadowTableMapping:
    """注册或更新生产表对应的影子表映射。"""
    map_id = f"map_{uuid.uuid4().hex[:6]}"
    mapping = ShadowTableMapping(
        mapping_id=map_id,
        production_table=production_table.strip(),
        shadow_table=shadow_table.strip(),
        isolation_strategy=strategy,
        is_active=True,
    )
    _SHADOW_MAPPINGS[production_table.strip()] = mapping
    return mapping


def list_shadow_mappings() -> list[dict[str, Any]]:
    """获取所有已注册的影子表路由映射。"""
    return [m.to_dict() for m in _SHADOW_MAPPINGS.values()]


def _extract_table_name(sql: str) -> str:
    """通过正则快速提取 SQL 语句中的目标表名。"""
    # 匹配 INSERT INTO table, UPDATE table, FROM table, DELETE FROM table
    match = re.search(r"\b(?:FROM|INTO|UPDATE|TABLE)\s+([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return "unknown_table"


def _is_write_sql(sql: str) -> bool:
    """判断 SQL 是否包含持久化写操作。"""
    cleaned = sql.strip().upper()
    return bool(re.match(r"^(INSERT|UPDATE|DELETE|REPLACE|MERGE|ALTER|DROP|CREATE)\b", cleaned))


def inspect_sql_isolation_routing(
    target_cluster: str,
    queries: list[dict[str, Any]],
) -> DbIsolationAuditReport:
    """模拟数据库连接池与驱动中间件，对压测影子 SQL 执行路由重写与生产防污染拦截。"""
    inspections: list[SqlRoutingInspectionItem] = []
    routed_c = 0
    blocked_c = 0
    safe_c = 0

    for q in queries:
        raw_sql = str(q.get("sql", "")).strip()
        is_shadow = bool(q.get("is_shadow_traffic", False))
        is_write = _is_write_sql(raw_sql)
        table_name = _extract_table_name(raw_sql)
        mapping = _SHADOW_MAPPINGS.get(table_name)

        item_id = f"sql_insp_{uuid.uuid4().hex[:6]}"

        if is_shadow:
            if not is_write:
                # 影子读操作：可安全透传(或走只读只查生产/影子副本)
                verdict = SqlRoutingVerdict.READ_ONLY_SAFE
                rewritten = raw_sql
                expl = "影子只读查询 (SELECT)，不发生数据写入，安全允许执行。"
                safe_c += 1
            else:
                # 影子写操作：必须有合法的影子表映射！
                if mapping and mapping.is_active:
                    verdict = SqlRoutingVerdict.ROUTED_TO_SHADOW
                    # 动态将生产表名替换为影子表名
                    rewritten = re.sub(rf"\b{table_name}\b", mapping.shadow_table, raw_sql, flags=re.IGNORECASE)
                    expl = (
                        f"成功将影子写操作由生产表 [{table_name}] 重定向至影子表 [{mapping.shadow_table}]，防污染生效。"
                    )
                    routed_c += 1
                else:
                    # 未配置影子表！属于高危致命隐患，必须直接拒绝执行，彻底杜绝污染真实生产数据
                    verdict = SqlRoutingVerdict.BLOCKED_PROD_POLLUTION_ATTEMPT
                    rewritten = None
                    expl = (
                        f"高危阻断！影子写操作命中了未配置影子映射的生产表 [{table_name}]，中间件已强行拦截抛出异常！"
                    )
                    blocked_c += 1
        else:
            # 正常生产业务流量
            if "__shadow_" in raw_sql.lower():
                verdict = SqlRoutingVerdict.BLOCKED_PROD_POLLUTION_ATTEMPT
                rewritten = None
                expl = "非影子业务流量企图访问影子表，判定非法并阻断。"
                blocked_c += 1
            else:
                verdict = SqlRoutingVerdict.SAFE_PROD_PASSTHROUGH
                rewritten = raw_sql
                expl = "正常业务生产流量，安全放行至生产表。"
                safe_c += 1

        inspections.append(
            SqlRoutingInspectionItem(
                item_id=item_id,
                original_sql=raw_sql,
                is_shadow_traffic=is_shadow,
                is_write_operation=is_write,
                detected_target_table=table_name,
                verdict=verdict,
                rewritten_sql=rewritten,
                explanation=expl,
            )
        )

    total_q = max(1, len(queries))
    # 安全合规得分：若存在高危阻断项，按比例扣减
    safety_score = 100.0 if blocked_c == 0 else max(0.0, 100.0 - (blocked_c / total_q) * 100.0)

    now = datetime.now(timezone.utc)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", target_cluster)[:16]
    report_id = f"db_iso_{safe_name}_{int(now.timestamp())}"

    report = DbIsolationAuditReport(
        report_id=report_id,
        target_cluster=target_cluster,
        total_queries_checked=len(queries),
        routed_to_shadow_count=routed_c,
        blocked_pollution_count=blocked_c,
        safe_passthrough_count=safe_c,
        isolation_safety_score_pct=safety_score,
        has_critical_pollution_risk=blocked_c > 0,
        inspections=inspections,
        created_at=now,
    )

    _DB_ISOLATION_REPORTS[report_id] = report
    return report


def get_db_isolation_report(report_id: str) -> DbIsolationAuditReport | None:
    """按 ID 查询影子库表隔离审计报告。"""
    return _DB_ISOLATION_REPORTS.get(report_id)


def list_db_isolation_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史隔离报告列表。"""
    reports = list(reversed(list(_DB_ISOLATION_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
