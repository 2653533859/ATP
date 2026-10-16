"""大规模测试套件智能动态分片调度器单元测试 (T1.2)。"""

from __future__ import annotations

import pytest
from app.services.test_suite_dynamic_sharding_scheduler import (
    TestCaseShardingInput,
    calculate_dynamic_sharding,
    clear_sharding_plans,
    detect_straggler_shards,
    get_sharding_plan,
    list_sharding_plans,
)


@pytest.fixture(autouse=True)
def _reset_sharding_state():
    clear_sharding_plans()
    yield
    clear_sharding_plans()


def test_calculate_dynamic_sharding_lpt_balance():
    """测试基于 LPT 贪心装箱算法的耗时负载均衡分配。"""
    cases = [
        TestCaseShardingInput(
            case_id="case_1", case_name="长耗时端到端登录", historical_duration_ms=6000.0, priority="P0"
        ),
        TestCaseShardingInput(case_id="case_2", case_name="结算流程用例", historical_duration_ms=5000.0, priority="P0"),
        TestCaseShardingInput(case_id="case_3", case_name="用户资料更新", historical_duration_ms=4000.0, priority="P1"),
        TestCaseShardingInput(case_id="case_4", case_name="修改密码", historical_duration_ms=3000.0, priority="P1"),
        TestCaseShardingInput(case_id="case_5", case_name="查询订单列表", historical_duration_ms=2000.0, priority="P2"),
        TestCaseShardingInput(case_id="case_6", case_name="商品搜索", historical_duration_ms=1000.0, priority="P2"),
    ]

    # 切分 3 个节点
    plan = calculate_dynamic_sharding(cases=cases, total_shards=3)

    assert plan.total_cases == 6
    assert plan.total_shards == 3
    assert len(plan.shards) == 3

    # 每个分片都分到了用例，总耗时 21000ms，平均 7000ms 左右
    durations = [s.estimated_duration_ms for s in plan.shards]
    assert all(d > 0 for d in durations)
    assert plan.balance_score_pct >= 80.0  # 均衡度应达到 80% 以上
    assert plan.makespan_ms >= plan.min_shard_duration_ms

    # 验证全局计划仓库已持久化
    saved = get_sharding_plan(plan.plan_id)
    assert saved is not None
    assert saved.plan_id == plan.plan_id


def test_calculate_dynamic_sharding_empty_cases():
    """测试待分片列表为空时的边界情况。"""
    plan = calculate_dynamic_sharding(cases=[], total_shards=2)
    assert plan.total_cases == 0
    assert plan.total_shards == 2
    assert plan.makespan_ms == 0.0
    assert plan.balance_score_pct == 100.0
    assert len(plan.shards) == 2


def test_detect_straggler_shards():
    """测试长尾掉队节点探测机制。"""
    progress_data = [
        {"shard_index": 0, "node_id": "worker-1", "elapsed_ms": 12000.0, "remaining_cases": 15, "total_cases": 20},
        {"shard_index": 1, "node_id": "worker-2", "elapsed_ms": 3000.0, "remaining_cases": 0, "total_cases": 15},
        {"shard_index": 2, "node_id": "worker-3", "elapsed_ms": 3500.0, "remaining_cases": 1, "total_cases": 15},
    ]

    detection = detect_straggler_shards(progress_data)
    assert detection["has_straggler"] is True
    assert len(detection["stragglers"]) == 1
    assert detection["stragglers"][0]["node_id"] == "worker-1"
    assert "重平衡" in detection["recommendation"]


def test_list_and_clear_sharding_plans():
    """测试方案列表查询与清空。"""
    cases = [TestCaseShardingInput(case_id="c1", case_name="测试用例1", historical_duration_ms=500.0)]
    calculate_dynamic_sharding(cases=cases, total_shards=2)

    plans = list_sharding_plans()
    assert len(plans) == 1

    clear_sharding_plans()
    assert len(list_sharding_plans()) == 0
