"""数据库 Schema 结构与索引变更漂移自动比对器 (T2.2)。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SchemaDriftSeverity(str, Enum):
    """Schema 漂移严重程度。"""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    IDENTICAL = "IDENTICAL"


class SchemaDriftType(str, Enum):
    """表结构差异分类。"""

    TABLE_MISSING = "TABLE_MISSING"
    TABLE_EXTRA = "TABLE_EXTRA"
    COLUMN_MISSING = "COLUMN_MISSING"
    COLUMN_EXTRA = "COLUMN_EXTRA"
    COLUMN_TYPE_MISMATCH = "COLUMN_TYPE_MISMATCH"
    COLUMN_NULLABILITY_DRIFT = "COLUMN_NULLABILITY_DRIFT"
    INDEX_MISSING = "INDEX_MISSING"
    INDEX_EXTRA = "INDEX_EXTRA"


@dataclass
class ColumnSpec:
    """列定义规范。"""

    name: str
    data_type: str  # VARCHAR, INTEGER, TIMESTAMP, BOOLEAN, BIGINT 等
    nullable: bool = True
    default_value: str | None = None
    is_primary_key: bool = False


@dataclass
class IndexSpec:
    """索引定义规范。"""

    name: str
    columns: list[str]
    is_unique: bool = False


@dataclass
class TableSchemaSnapshot:
    """单张表的 Schema 快照。"""

    table_name: str
    columns: dict[str, ColumnSpec]
    indexes: dict[str, IndexSpec] = field(default_factory=dict)


@dataclass
class SchemaDriftItem:
    """单条 Schema 差异项。"""

    table_name: str
    object_name: str  # 列名或索引名
    drift_type: SchemaDriftType
    severity: SchemaDriftSeverity
    base_detail: str | None
    target_detail: str | None
    risk_explanation: str
    remediation_ddl: str  # 自动生成的修复 SQL

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_name": self.table_name,
            "object_name": self.object_name,
            "drift_type": self.drift_type.value,
            "severity": self.severity.value,
            "base_detail": self.base_detail,
            "target_detail": self.target_detail,
            "risk_explanation": self.risk_explanation,
            "remediation_ddl": self.remediation_ddl,
        }


@dataclass
class SchemaDriftReport:
    """数据库 Schema 跨环境比对报告。"""

    report_id: str
    database_name: str
    base_env: str
    target_env: str
    total_tables_checked: int
    identical_tables_count: int
    drift_items_count: int
    highest_severity: SchemaDriftSeverity
    compatibility_rate_pct: float  # 结构兼容度 0~100%
    remediation_ddl_script: str  # 汇总修复 SQL 脚本
    drifts: list[SchemaDriftItem]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "database_name": self.database_name,
            "base_env": self.base_env,
            "target_env": self.target_env,
            "total_tables_checked": self.total_tables_checked,
            "identical_tables_count": self.identical_tables_count,
            "drift_items_count": self.drift_items_count,
            "highest_severity": self.highest_severity.value,
            "compatibility_rate_pct": round(self.compatibility_rate_pct, 1),
            "remediation_ddl_script": self.remediation_ddl_script,
            "drifts": [d.to_dict() for d in self.drifts],
            "created_at": self.created_at.isoformat(),
        }


# 全局 Schema 快照与报告存储
_DB_SCHEMA_SNAPSHOTS: dict[str, dict[str, TableSchemaSnapshot]] = {}  # key: f"{env}:{db_name}"
_SCHEMA_DRIFT_REPORTS: dict[str, SchemaDriftReport] = {}


def clear_schema_drift_store() -> None:
    """清空 Schema 仓库（单测专用）。"""
    _DB_SCHEMA_SNAPSHOTS.clear()
    _SCHEMA_DRIFT_REPORTS.clear()


def register_db_schema_snapshot(
    env_name: str,
    database_name: str,
    tables: list[dict[str, Any]],
) -> dict[str, Any]:
    """登记环境数据库完整表结构快照。"""
    store_key = f"{env_name.lower()}:{database_name.lower()}"
    parsed_tables: dict[str, TableSchemaSnapshot] = {}

    for t in tables:
        t_name = t["table_name"]
        cols: dict[str, ColumnSpec] = {}
        for c in t.get("columns", []):
            cols[c["name"]] = ColumnSpec(
                name=c["name"],
                data_type=c["data_type"].upper(),
                nullable=c.get("nullable", True),
                default_value=c.get("default_value"),
                is_primary_key=c.get("is_primary_key", False),
            )
        idxs: dict[str, IndexSpec] = {}
        for idx in t.get("indexes", []):
            idxs[idx["name"]] = IndexSpec(
                name=idx["name"],
                columns=idx["columns"],
                is_unique=idx.get("is_unique", False),
            )
        parsed_tables[t_name] = TableSchemaSnapshot(table_name=t_name, columns=cols, indexes=idxs)

    _DB_SCHEMA_SNAPSHOTS[store_key] = parsed_tables
    return {
        "message": f"环境 [{env_name}] 数据库 [{database_name}] Schema 快照登记成功",
        "store_key": store_key,
        "tables_count": len(parsed_tables),
    }


def compare_database_schemas(
    database_name: str,
    base_env: str = "production",
    target_env: str = "testing",
    base_tables: list[dict[str, Any]] | None = None,
    target_tables: list[dict[str, Any]] | None = None,
) -> SchemaDriftReport:
    """比对基准环境与目标环境数据库 Schema 结构与索引差异。"""
    b_tables = {}
    if base_tables is not None:
        for t in base_tables:
            cols = {
                c["name"]: ColumnSpec(
                    name=c["name"],
                    data_type=c["data_type"].upper(),
                    nullable=c.get("nullable", True),
                    default_value=c.get("default_value"),
                    is_primary_key=c.get("is_primary_key", False),
                )
                for c in t.get("columns", [])
            }
            idxs = {
                i["name"]: IndexSpec(name=i["name"], columns=i["columns"], is_unique=i.get("is_unique", False))
                for i in t.get("indexes", [])
            }
            b_tables[t["table_name"]] = TableSchemaSnapshot(table_name=t["table_name"], columns=cols, indexes=idxs)
    else:
        b_tables = _DB_SCHEMA_SNAPSHOTS.get(f"{base_env.lower()}:{database_name.lower()}", {})

    t_tables = {}
    if target_tables is not None:
        for t in target_tables:
            cols = {
                c["name"]: ColumnSpec(
                    name=c["name"],
                    data_type=c["data_type"].upper(),
                    nullable=c.get("nullable", True),
                    default_value=c.get("default_value"),
                    is_primary_key=c.get("is_primary_key", False),
                )
                for c in t.get("columns", [])
            }
            idxs = {
                i["name"]: IndexSpec(name=i["name"], columns=i["columns"], is_unique=i.get("is_unique", False))
                for i in t.get("indexes", [])
            }
            t_tables[t["table_name"]] = TableSchemaSnapshot(table_name=t["table_name"], columns=cols, indexes=idxs)
    else:
        t_tables = _DB_SCHEMA_SNAPSHOTS.get(f"{target_env.lower()}:{database_name.lower()}", {})

    all_table_names = sorted(set(b_tables.keys()) | set(t_tables.keys()))
    drifts: list[SchemaDriftItem] = []
    identical_tables = 0

    severity_order = {
        SchemaDriftSeverity.CRITICAL: 4,
        SchemaDriftSeverity.HIGH: 3,
        SchemaDriftSeverity.MEDIUM: 2,
        SchemaDriftSeverity.LOW: 1,
        SchemaDriftSeverity.IDENTICAL: 0,
    }
    highest_sev = SchemaDriftSeverity.IDENTICAL

    for tbl_name in all_table_names:
        in_b = tbl_name in b_tables
        in_t = tbl_name in t_tables

        if in_b and not in_t:
            # 目标环境缺失整张表
            b_tbl = b_tables[tbl_name]
            col_defs = [
                f"{c.name} {c.data_type}"
                + (" PRIMARY KEY" if c.is_primary_key else "")
                + (" NOT NULL" if not c.nullable else "")
                for c in b_tbl.columns.values()
            ]
            ddl = f"CREATE TABLE {tbl_name} (\n  " + ",\n  ".join(col_defs) + "\n);"
            item = SchemaDriftItem(
                table_name=tbl_name,
                object_name=tbl_name,
                drift_type=SchemaDriftType.TABLE_MISSING,
                severity=SchemaDriftSeverity.CRITICAL,
                base_detail=f"包含 {len(b_tbl.columns)} 列",
                target_detail=None,
                risk_explanation=f"目标环境缺少整张业务表 [{tbl_name}]，执行关联查询将发生 Table Not Found 崩溃。",
                remediation_ddl=ddl,
            )
            drifts.append(item)
            if severity_order[item.severity] > severity_order[highest_sev]:
                highest_sev = item.severity
            continue

        if in_t and not in_b:
            # 目标环境存在额外表
            item = SchemaDriftItem(
                table_name=tbl_name,
                object_name=tbl_name,
                drift_type=SchemaDriftType.TABLE_EXTRA,
                severity=SchemaDriftSeverity.LOW,
                base_detail=None,
                target_detail=f"包含 {len(t_tables[tbl_name].columns)} 列",
                risk_explanation=f"目标环境存在基准环境尚未上线的额外表 [{tbl_name}]。",
                remediation_ddl=f"-- 确认无误后可保留或清理: DROP TABLE IF EXISTS {tbl_name};",
            )
            drifts.append(item)
            if severity_order[item.severity] > severity_order[highest_sev]:
                highest_sev = item.severity
            continue

        # 两环境均有此表，比对列与索引
        b_tbl = b_tables[tbl_name]
        t_tbl = t_tables[tbl_name]
        tbl_drift_count_before = len(drifts)

        # 1. 列比对
        all_cols = sorted(set(b_tbl.columns.keys()) | set(t_tbl.columns.keys()))
        for c_name in all_cols:
            has_b_col = c_name in b_tbl.columns
            has_t_col = c_name in t_tbl.columns

            if has_b_col and not has_t_col:
                col = b_tbl.columns[c_name]
                ddl = (
                    f"ALTER TABLE {tbl_name} ADD COLUMN {c_name} {col.data_type}"
                    + (" NOT NULL" if not col.nullable else "")
                    + ";"
                )
                item = SchemaDriftItem(
                    table_name=tbl_name,
                    object_name=c_name,
                    drift_type=SchemaDriftType.COLUMN_MISSING,
                    severity=SchemaDriftSeverity.HIGH,
                    base_detail=f"{col.data_type} (nullable={col.nullable})",
                    target_detail=None,
                    risk_explanation=f"表 [{tbl_name}] 在目标环境中缺少必要列 [{c_name}]。",
                    remediation_ddl=ddl,
                )
                drifts.append(item)
            elif has_t_col and not has_b_col:
                col = t_tbl.columns[c_name]
                item = SchemaDriftItem(
                    table_name=tbl_name,
                    object_name=c_name,
                    drift_type=SchemaDriftType.COLUMN_EXTRA,
                    severity=SchemaDriftSeverity.LOW,
                    base_detail=None,
                    target_detail=f"{col.data_type}",
                    risk_explanation=f"表 [{tbl_name}] 目标环境存在额外未同步列 [{c_name}]。",
                    remediation_ddl=f"-- 目标环境额外列: ALTER TABLE {tbl_name} DROP COLUMN IF EXISTS {c_name};",
                )
                drifts.append(item)
            else:
                b_c = b_tbl.columns[c_name]
                t_c = t_tbl.columns[c_name]
                if b_c.data_type != t_c.data_type:
                    ddl = f"ALTER TABLE {tbl_name} ALTER COLUMN {c_name} TYPE {b_c.data_type};"
                    item = SchemaDriftItem(
                        table_name=tbl_name,
                        object_name=c_name,
                        drift_type=SchemaDriftType.COLUMN_TYPE_MISMATCH,
                        severity=SchemaDriftSeverity.HIGH,
                        base_detail=b_c.data_type,
                        target_detail=t_c.data_type,
                        risk_explanation=f"列 [{tbl_name}.{c_name}] 数据类型不一致 ({b_c.data_type} vs {t_c.data_type})，存在类型转换截断风险。",
                        remediation_ddl=ddl,
                    )
                    drifts.append(item)
                elif b_c.nullable != t_c.nullable:
                    ddl = f"ALTER TABLE {tbl_name} ALTER COLUMN {c_name} " + (
                        "DROP NOT NULL;" if b_c.nullable else "SET NOT NULL;"
                    )
                    item = SchemaDriftItem(
                        table_name=tbl_name,
                        object_name=c_name,
                        drift_type=SchemaDriftType.COLUMN_NULLABILITY_DRIFT,
                        severity=SchemaDriftSeverity.MEDIUM,
                        base_detail=f"nullable={b_c.nullable}",
                        target_detail=f"nullable={t_c.nullable}",
                        risk_explanation=f"列 [{tbl_name}.{c_name}] 非空约束漂移，写入 NULL 值行为不一致。",
                        remediation_ddl=ddl,
                    )
                    drifts.append(item)

        # 2. 索引比对
        all_idxs = sorted(set(b_tbl.indexes.keys()) | set(t_tbl.indexes.keys()))
        for idx_name in all_idxs:
            has_b_idx = idx_name in b_tbl.indexes
            has_t_idx = idx_name in t_tbl.indexes
            if has_b_idx and not has_t_idx:
                idx = b_tbl.indexes[idx_name]
                uniq = "UNIQUE " if idx.is_unique else ""
                cols_str = ", ".join(idx.columns)
                ddl = f"CREATE {uniq}INDEX {idx_name} ON {tbl_name} ({cols_str});"
                item = SchemaDriftItem(
                    table_name=tbl_name,
                    object_name=idx_name,
                    drift_type=SchemaDriftType.INDEX_MISSING,
                    severity=SchemaDriftSeverity.HIGH if idx.is_unique else SchemaDriftSeverity.MEDIUM,
                    base_detail=f"Columns: {cols_str}, Unique: {idx.is_unique}",
                    target_detail=None,
                    risk_explanation=f"表 [{tbl_name}] 目标环境缺少索引 [{idx_name}]，可能引发性能全表扫描或唯一约束失效。",
                    remediation_ddl=ddl,
                )
                drifts.append(item)

        if len(drifts) == tbl_drift_count_before:
            identical_tables += 1
        else:
            for d in drifts[tbl_drift_count_before:]:
                if severity_order[d.severity] > severity_order[highest_sev]:
                    highest_sev = d.severity

    # 计算兼容度得分与合并修复 SQL 脚本
    total_tbls = len(all_table_names)
    compat_score = (identical_tables / total_tbls * 100.0) if total_tbls > 0 else 100.0
    combined_ddl = "\n\n".join(d.remediation_ddl for d in drifts if d.remediation_ddl)

    now = datetime.now(timezone.utc)
    report_id = f"schema_drift_{database_name}_{base_env}_{target_env}_{int(now.timestamp())}"
    report = SchemaDriftReport(
        report_id=report_id,
        database_name=database_name,
        base_env=base_env,
        target_env=target_env,
        total_tables_checked=total_tbls,
        identical_tables_count=identical_tables,
        drift_items_count=len(drifts),
        highest_severity=highest_sev,
        compatibility_rate_pct=compat_score,
        remediation_ddl_script=combined_ddl,
        drifts=drifts,
        created_at=now,
    )
    _SCHEMA_DRIFT_REPORTS[report_id] = report
    return report


def get_schema_drift_report(report_id: str) -> SchemaDriftReport | None:
    """按 ID 查询 Schema 漂移报告。"""
    return _SCHEMA_DRIFT_REPORTS.get(report_id)


def list_schema_drift_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史 Schema 漂移报告列表。"""
    reports = list(reversed(list(_SCHEMA_DRIFT_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
