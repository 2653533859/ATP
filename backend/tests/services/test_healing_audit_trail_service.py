"""Unit tests for D2.3 Healing Audit Trail & Root Cause Clustering Service."""

import pytest

from app.services.healing_audit_trail_service import (
    HealingActionType,
    HealingVerificationStatus,
    calculate_healing_metrics,
    cluster_error_event,
    get_fault_cluster,
    list_fault_clusters,
    list_healing_audit_entries,
    normalize_error_signature,
    record_healing_action,
    reset_healing_audit_registry,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_healing_audit_registry()
    yield
    reset_healing_audit_registry()


def test_normalize_error_signature():
    # 两个带有不同动态 UUID 和内存地址的同因报错
    err1 = "Element not found: id=button-123e4567-e89b-12d3-a456-426614174000 at 0x7fff5fbff880"
    err2 = "Element not found: id=button-987fcb12-1111-2222-3333-444455556666 at 0x7fff5fbff990"

    sig1 = normalize_error_signature("NoSuchElementException", err1)
    sig2 = normalize_error_signature("NoSuchElementException", err2)

    # 动态噪声被剔除后，签名指纹必须完全一致
    assert sig1 == sig2
    assert len(sig1) == 16


def test_cluster_error_event_aggregation():
    # 模拟在用例 101 与 102 中抛出相同根因的元素未找到异常
    cluster1 = cluster_error_event(
        case_id=101,
        run_id=50,
        exception_type="NoSuchElementException",
        error_message="Unable to locate element: //button[@id='submit-order-10001']",
    )

    assert cluster1.occurrences_count == 1
    assert 101 in cluster1.affected_case_ids

    # 第二次发生，参数稍有变化
    cluster2 = cluster_error_event(
        case_id=102,
        run_id=51,
        exception_type="NoSuchElementException",
        error_message="Unable to locate element: //button[@id='submit-order-10002']",
    )

    # 必须聚类到同一个故障簇中
    assert cluster1.cluster_id == cluster2.cluster_id
    assert cluster2.occurrences_count == 2
    assert 101 in cluster2.affected_case_ids
    assert 102 in cluster2.affected_case_ids
    assert len(list_fault_clusters()) == 1


def test_record_healing_action_and_metrics():
    # 1. 记录一次自愈成功的操作
    entry1 = record_healing_action(
        case_id=101,
        step_name="点击提交订单",
        action_type=HealingActionType.LOCATOR_REPLACED,
        original_value="//button[@id='old-btn']",
        healed_value="//*[@data-testid='submit-btn']",
        confidence_score=0.95,
        verification_status=HealingVerificationStatus.VERIFIED_SUCCESS,
        duration_ms=45.2,
    )
    assert entry1.audit_id.startswith("audit_act_")

    # 2. 记录一次自愈重试
    record_healing_action(
        case_id=102,
        step_name="等待页面渲染",
        action_type=HealingActionType.RETRY_WITH_BACKOFF,
        original_value=None,
        healed_value={"retry_interval": 2.0},
        confidence_score=0.88,
        verification_status=HealingVerificationStatus.AUTO_ACCEPTED,
        duration_ms=120.0,
    )

    # 3. 统计度量
    metrics = calculate_healing_metrics()
    assert metrics["total_healing_actions_count"] == 2
    assert metrics["verification_success_rate_pct"] == 100.0
    assert metrics["average_confidence_score"] > 0.90
    assert metrics["estimated_engineering_hours_saved"] > 0.5


def test_list_healing_audit_entries_filter():
    record_healing_action(
        case_id=201,
        step_name="输入用户名",
        action_type=HealingActionType.LOCATOR_REPLACED,
        original_value="#user",
        healed_value="input[name='username']",
        confidence_score=0.90,
    )
    record_healing_action(
        case_id=202,
        step_name="校验响应",
        action_type=HealingActionType.SCHEMA_AUTOFIXED,
        original_value={},
        healed_value={"type": "object"},
        confidence_score=0.92,
    )

    # 按用例筛选
    case201_entries = list_healing_audit_entries(case_id=201)
    assert len(case201_entries) == 1
    assert case201_entries[0].step_name == "输入用户名"

    # 按动作类型筛选
    schema_entries = list_healing_audit_entries(action_type=HealingActionType.SCHEMA_AUTOFIXED)
    assert len(schema_entries) == 1
    assert schema_entries[0].case_id == 202

    # 查询不存在的故障簇返回 None
    assert get_fault_cluster("non_existent_cluster") is None
