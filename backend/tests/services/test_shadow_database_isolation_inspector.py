"""影子数据库/影子表隔离与防污染拦截单元测试 (T1.2)。"""

from __future__ import annotations

import pytest
from app.services.shadow_database_isolation_inspector import (
    IsolationStrategy,
    SqlRoutingVerdict,
    clear_db_isolation_store,
    get_db_isolation_report,
    inspect_sql_isolation_routing,
    list_db_isolation_reports,
    list_shadow_mappings,
    register_shadow_mapping,
)


@pytest.fixture(autouse=True)
def _reset_db_isolation_state():
    clear_db_isolation_store()
    yield
    clear_db_isolation_store()


def test_inspect_sql_isolation_routing_success_and_blocking():
    """测试将影子写重写至影子表，以及对未映射生产表的影子写直接强行阻断。"""
    queries = [
        # 1. 影子读操作 (SELECT) -> 安全放行
        {
            "sql": "SELECT * FROM t_order WHERE user_id = 1001",
            "is_shadow_traffic": True,
        },
        # 2. 影子写操作 (INSERT 到已配置影子表的 t_order) -> 成功重写为 __shadow_t_order__
        {
            "sql": "INSERT INTO t_order (order_id, amount) VALUES ('ord_01', 99.0)",
            "is_shadow_traffic": True,
        },
        # 3. 影子写操作 (UPDATE 到未配置影子表的 t_user_balance) -> 高危阻断！
        {
            "sql": "UPDATE t_user_balance SET balance = balance - 100 WHERE user_id = 1001",
            "is_shadow_traffic": True,
        },
        # 4. 正常生产业务写操作 -> 放行至生产表
        {
            "sql": "INSERT INTO t_order (order_id, amount) VALUES ('real_ord_99', 50.0)",
            "is_shadow_traffic": False,
        },
    ]

    report = inspect_sql_isolation_routing(target_cluster="prod_cluster_primary", queries=queries)

    assert report.total_queries_checked == 4
    assert report.routed_to_shadow_count == 1
    assert report.blocked_pollution_count == 1
    assert report.safe_passthrough_count == 2
    assert report.has_critical_pollution_risk is True

    verdicts = [i.verdict for i in report.inspections]
    assert SqlRoutingVerdict.READ_ONLY_SAFE in verdicts
    assert SqlRoutingVerdict.ROUTED_TO_SHADOW in verdicts
    assert SqlRoutingVerdict.BLOCKED_PROD_POLLUTION_ATTEMPT in verdicts
    assert SqlRoutingVerdict.SAFE_PROD_PASSTHROUGH in verdicts

    # 验证重写 SQL 包含影子表
    shadow_insert = next(i for i in report.inspections if i.verdict == SqlRoutingVerdict.ROUTED_TO_SHADOW)
    assert "__shadow_t_order__" in (shadow_insert.rewritten_sql or "")


def test_register_and_list_shadow_mappings():
    """测试动态注册新生产表与影子表映射。"""
    mapping = register_shadow_mapping(
        production_table="t_coupon_record",
        shadow_table="__shadow_t_coupon_record__",
        strategy=IsolationStrategy.SHADOW_TABLE,
    )
    assert mapping.production_table == "t_coupon_record"
    assert mapping.shadow_table == "__shadow_t_coupon_record__"

    mappings = list_shadow_mappings()
    assert any(m["production_table"] == "t_coupon_record" for m in mappings)

    # 持久化检验
    rep = inspect_sql_isolation_routing(
        target_cluster="test_cluster",
        queries=[{"sql": "SELECT 1 FROM t_order", "is_shadow_traffic": False}],
    )
    saved = get_db_isolation_report(rep.report_id)
    assert saved is not None
    assert saved.report_id == rep.report_id
    assert len(list_db_isolation_reports()) == 1
