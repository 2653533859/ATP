"""单元故障演练与容灾接管自愈验证器单元测试 (T2.3)。"""

from __future__ import annotations

import pytest
from app.services.cell_failover_resilience_verifier import (
    FailoverVerdict,
    clear_failover_report_store,
    execute_cell_failover_drill,
    get_failover_report,
    list_failover_reports,
)


@pytest.fixture(autouse=True)
def _reset_failover_state():
    clear_failover_report_store()
    yield
    clear_failover_report_store()


def test_execute_cell_failover_drill_success():
    """测试常规单机房整体故障演练，RTO <= 2500ms 达成 FAILOVER_SUCCESS。"""
    report = execute_cell_failover_drill(
        failed_cell_id="cell_east_01",
        standby_cell_id="cell_east_02",
        traffic_shift_percentage=100.0,
        dns_switch_delay_ms=600.0,
        db_replication_lag_ms=150.0,
        route_convergence_delay_ms=350.0,
    )

    # 450 (detect) + 600 + 150 + 350 = 1550ms <= 2500ms
    assert report.total_rto_duration_ms == 1550.0
    assert report.verdict == FailoverVerdict.FAILOVER_SUCCESS
    assert report.is_resilience_qualified is True
    assert report.estimated_packet_drop_pct < 0.05
    assert len(report.timeline_phases) == 4

    saved = get_failover_report(report.drill_id)
    assert saved is not None
    assert saved.drill_id == report.drill_id
    assert len(list_failover_reports()) == 1


def test_execute_cell_failover_drill_timeout():
    """测试 DNS 延迟极高、数据库追平严重滞后引发的超时失败。"""
    report = execute_cell_failover_drill(
        failed_cell_id="cell_dr_beijing",
        standby_cell_id="cell_east_01",
        dns_switch_delay_ms=3500.0,
        db_replication_lag_ms=1800.0,
        route_convergence_delay_ms=1000.0,
    )

    # 450 + 3500 + 1800 + 1000 = 6750ms > 5000ms -> TIMEOUT
    assert report.total_rto_duration_ms > 5000.0
    assert report.verdict == FailoverVerdict.FAILOVER_TIMEOUT
    assert report.is_resilience_qualified is False
    assert len(report.remediation_recommendations) >= 2
