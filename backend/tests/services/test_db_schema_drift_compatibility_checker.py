"""数据库 Schema 结构与索引变更漂移单元测试 (T2.2)。"""

from __future__ import annotations

import pytest
from app.services.db_schema_drift_compatibility_checker import (
    SchemaDriftSeverity,
    SchemaDriftType,
    clear_schema_drift_store,
    compare_database_schemas,
    get_schema_drift_report,
    list_schema_drift_reports,
    register_db_schema_snapshot,
)


@pytest.fixture(autouse=True)
def _reset_schema_state():
    clear_schema_drift_store()
    yield
    clear_schema_drift_store()


def test_compare_identical_schemas():
    """测试当两环境表结构完全一致时输出 100% 兼容度与 IDENTICAL 状态。"""
    tables = [
        {
            "table_name": "orders",
            "columns": [
                {"name": "id", "data_type": "BIGINT", "nullable": False, "is_primary_key": True},
                {"name": "user_id", "data_type": "BIGINT", "nullable": False},
                {"name": "total_amount", "data_type": "DECIMAL", "nullable": False},
            ],
            "indexes": [
                {"name": "idx_orders_user_id", "columns": ["user_id"], "is_unique": False},
            ],
        }
    ]

    report = compare_database_schemas(
        database_name="orders_db",
        base_env="production",
        target_env="staging",
        base_tables=tables,
        target_tables=tables,
    )

    assert report.total_tables_checked == 1
    assert report.identical_tables_count == 1
    assert report.drift_items_count == 0
    assert report.compatibility_rate_pct == 100.0
    assert report.highest_severity == SchemaDriftSeverity.IDENTICAL
    assert report.remediation_ddl_script == ""


def test_compare_table_missing_and_column_drifts():
    """测试探测表缺失、列缺失、数据类型不一致与索引缺失，并生成修复 DDL。"""
    base_tables = [
        {
            "table_name": "users",
            "columns": [
                {"name": "id", "data_type": "BIGINT", "nullable": False, "is_primary_key": True},
                {"name": "email", "data_type": "VARCHAR(255)", "nullable": False},
                {"name": "phone", "data_type": "VARCHAR(32)", "nullable": True},
                {"name": "created_at", "data_type": "TIMESTAMP", "nullable": False},
            ],
            "indexes": [
                {"name": "uniq_users_email", "columns": ["email"], "is_unique": True},
            ],
        },
        {
            "table_name": "audit_logs",
            "columns": [
                {"name": "log_id", "data_type": "VARCHAR(64)", "nullable": False, "is_primary_key": True},
                {"name": "content", "data_type": "TEXT", "nullable": True},
            ],
        },
    ]

    target_tables = [
        {
            "table_name": "users",
            "columns": [
                {"name": "id", "data_type": "BIGINT", "nullable": False, "is_primary_key": True},
                {"name": "email", "data_type": "VARCHAR(255)", "nullable": False},
                # phone 缺失
                {"name": "created_at", "data_type": "BIGINT", "nullable": False},  # 类型改变 TIMESTAMP -> BIGINT
            ],
            "indexes": [],  # 索引缺失
        }
        # audit_logs 整表缺失
    ]

    report = compare_database_schemas(
        database_name="app_db",
        base_env="production",
        target_env="testing",
        base_tables=base_tables,
        target_tables=target_tables,
    )

    assert report.total_tables_checked == 2
    assert report.identical_tables_count == 0
    assert (
        report.drift_items_count == 4
    )  # audit_logs 表缺失 + phone 列缺失 + created_at 类型不一致 + uniq_users_email 索引缺失
    assert report.highest_severity == SchemaDriftSeverity.CRITICAL

    drifts_by_obj = {d.object_name: d for d in report.drifts}

    # 1. audit_logs 表缺失 -> CRITICAL
    log_drift = drifts_by_obj["audit_logs"]
    assert log_drift.drift_type == SchemaDriftType.TABLE_MISSING
    assert log_drift.severity == SchemaDriftSeverity.CRITICAL
    assert "CREATE TABLE audit_logs" in log_drift.remediation_ddl

    # 2. phone 列缺失 -> HIGH
    phone_drift = drifts_by_obj["phone"]
    assert phone_drift.drift_type == SchemaDriftType.COLUMN_MISSING
    assert phone_drift.severity == SchemaDriftSeverity.HIGH
    assert "ALTER TABLE users ADD COLUMN phone VARCHAR(32)" in phone_drift.remediation_ddl

    # 3. created_at 数据类型改变 -> HIGH
    created_drift = drifts_by_obj["created_at"]
    assert created_drift.drift_type == SchemaDriftType.COLUMN_TYPE_MISMATCH
    assert "ALTER TABLE users ALTER COLUMN created_at TYPE TIMESTAMP" in created_drift.remediation_ddl

    # 4. 索引缺失
    idx_drift = drifts_by_obj["uniq_users_email"]
    assert idx_drift.drift_type == SchemaDriftType.INDEX_MISSING
    assert "CREATE UNIQUE INDEX uniq_users_email" in idx_drift.remediation_ddl


def test_register_and_list_schema_snapshots():
    """测试通过快照注册并比对。"""
    tables = [
        {
            "table_name": "products",
            "columns": [{"name": "id", "data_type": "INT", "nullable": False, "is_primary_key": True}],
        }
    ]
    register_db_schema_snapshot(env_name="production", database_name="shop_db", tables=tables)
    register_db_schema_snapshot(env_name="testing", database_name="shop_db", tables=tables)

    report = compare_database_schemas(database_name="shop_db", base_env="production", target_env="testing")
    assert report.compatibility_rate_pct == 100.0

    saved = get_schema_drift_report(report.report_id)
    assert saved is not None
    assert len(list_schema_drift_reports()) == 1
