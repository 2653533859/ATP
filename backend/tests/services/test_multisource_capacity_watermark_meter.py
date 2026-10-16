"""多源基础设施容量水位实时度量器单元测试 (T3.1)。"""

from __future__ import annotations

import pytest
from app.services.multisource_capacity_watermark_meter import (
    ResourceType,
    WatermarkLevel,
    clear_watermark_report_store,
    get_watermark_report,
    list_watermark_reports,
    meter_infrastructure_capacity_watermark,
)


@pytest.fixture(autouse=True)
def _reset_watermark_state():
    clear_watermark_report_store()
    yield
    clear_watermark_report_store()


def test_meter_infrastructure_capacity_watermark_high_load():
    """测试采集 DB 连接池、Redis 内存与 MQ 堆积，识别超过 85% 警戒水位短板。"""
    samples = [
        # 1. 数据库连接池: 92/100 -> 92.0% (SATURATED 逼近极限，需触发熔断)
        {
            "resource_id": "mysql_master_pool",
            "resource_type": "DATABASE_POOL",
            "current_value": 92.0,
            "capacity_limit": 100.0,
            "unit": "conns",
        },
        # 2. Redis 内存: 6000/10000 MB -> 60.0% (SAFE)
        {
            "resource_id": "redis_cluster_cache",
            "resource_type": "REDIS_CACHE",
            "current_value": 6000.0,
            "capacity_limit": 10000.0,
            "unit": "MB",
        },
        # 3. 消息队列堆积: 40000/50000 条 -> 80.0% (WARNING)
        {
            "resource_id": "kafka_order_topic",
            "resource_type": "MESSAGE_QUEUE",
            "current_value": 40000.0,
            "capacity_limit": 50000.0,
            "unit": "msgs",
        },
    ]

    report = meter_infrastructure_capacity_watermark(
        target_cluster_or_env="prod_east_az1",
        metric_samples=samples,
    )

    assert report.total_resources_measured == 3
    assert report.max_utilization_pct == 92.0
    assert report.weakest_bottleneck_resource == "mysql_master_pool"
    assert report.requires_avalanche_breaker is True  # 92% >= 85% 警戒线
    assert report.health_load_index_pct == 8.0  # 100 - 92 = 8%

    mysql_item = next(w for w in report.watermarks if w.resource_id == "mysql_master_pool")
    assert mysql_item.watermark_level == WatermarkLevel.SATURATED
    assert mysql_item.resource_type == ResourceType.DATABASE_POOL

    assert any("mysql_master_pool" in act for act in report.remediation_actions)

    saved = get_watermark_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id
    assert len(list_watermark_reports()) == 1


def test_meter_infrastructure_capacity_watermark_safe_load():
    """测试所有基础设施均处于低水位安全区间。"""
    samples = [
        {"resource_id": "db_01", "resource_type": "DATABASE_POOL", "current_value": 20.0, "capacity_limit": 100.0},
        {"resource_id": "redis_01", "resource_type": "REDIS_CACHE", "current_value": 1000.0, "capacity_limit": 10000.0},
    ]

    report = meter_infrastructure_capacity_watermark(target_cluster_or_env="safe_env", metric_samples=samples)
    assert report.max_utilization_pct == 20.0
    assert report.requires_avalanche_breaker is False
    assert report.health_load_index_pct == 80.0
