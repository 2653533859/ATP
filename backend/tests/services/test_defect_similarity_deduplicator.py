"""缺陷相似度计算与海量失败聚类去重器单测 (T1.2)"""

from __future__ import annotations

from app.services.defect_failure_fingerprint_extractor import (
    extract_failure_fingerprint,
)
from app.services.defect_similarity_deduplicator import (
    DefectClusteringAction,
    TestCaseFailureRecord,
    calculate_failure_similarity,
    cluster_and_deduplicate_failures,
)


def test_calculate_failure_similarity():
    fp_a = extract_failure_fingerprint(
        raw_error_message="ConnectionTimeout: Redis unreachable at 0x1122",
        raw_stack_trace='  File "/app/services/cache.py", line 12, in get\n    connect()',
    )
    fp_b = extract_failure_fingerprint(
        raw_error_message="ConnectionTimeout: Redis unreachable at 0x9988",
        raw_stack_trace='  File "/app/services/cache.py", line 12, in get\n    connect()',
    )
    # 同源故障相似度为 1.0
    sim_identical = calculate_failure_similarity(fp_a, fp_b)
    assert sim_identical == 1.0

    # 不同异常
    fp_c = extract_failure_fingerprint(
        raw_error_message="ValueError: Invalid user id",
        raw_stack_trace='  File "/app/services/user.py", line 30, in parse\n    check()',
    )
    sim_diff = calculate_failure_similarity(fp_a, fp_c)
    assert sim_diff < 0.3


def test_cluster_and_deduplicate_batch_failures():
    # 模拟一次批量执行中 10 个用例因同一底层数据库超时失败
    failures: list[TestCaseFailureRecord] = []
    for i in range(1, 11):
        failures.append(
            TestCaseFailureRecord(
                run_id="run_batch_01",
                case_id=f"case_order_{i}",
                case_name=f"下单验证测试场景_{i}",
                error_message=f"DatabaseConnectionTimeout: db unreachable (temp_id={i * 100})",
                stack_trace='  File "/app/services/order.py", line 40, in create_order\n    db.commit()',
                target_service="order-service",
            )
        )

    result = cluster_and_deduplicate_failures(failures)
    assert result.total_raw_failures == 10
    assert result.total_deduplicated_clusters == 1  # 10 个失败成功聚类为 1 个 Master 缺陷
    assert result.deduplication_ratio_pct == 90.0  # (10 - 1) / 10 = 90% 去重率
    assert result.new_master_defects_count == 1
    assert result.merged_to_existing_count == 0

    cluster = result.clusters[0]
    assert cluster.total_failures_count == 10
    assert len(cluster.linked_case_ids) == 10
    assert "case_order_1" in cluster.linked_case_ids
    assert "case_order_10" in cluster.linked_case_ids
    assert cluster.action == DefectClusteringAction.CREATED_NEW_MASTER
    assert "order-service" in cluster.master_title


def test_cluster_merges_to_known_open_defect():
    # 模拟今天失败的缺陷命中昨天已提的工单
    failure = TestCaseFailureRecord(
        run_id="run_nightly_02",
        case_id="case_checkout_pay",
        case_name="支付收银台场景",
        error_message="PaymentGatewayTimeout: upstream 504",
        stack_trace='  File "/app/services/payment.py", line 55, in charge\n    pay()',
        target_service="payment-service",
    )

    known_defects = [
        {
            "id": "DEF-9001",
            "title": "[payment-service] PaymentGatewayTimeout in payment.py:charge",
            "target_service": "payment-service",
        }
    ]

    result = cluster_and_deduplicate_failures([failure], known_open_defects=known_defects)
    assert result.total_deduplicated_clusters == 1
    assert result.new_master_defects_count == 0
    assert result.merged_to_existing_count == 1

    cl = result.clusters[0]
    assert cl.action == DefectClusteringAction.MERGED_TO_EXISTING_DEFECT
    assert cl.existing_defect_id == "DEF-9001"


def test_cluster_multiple_distinct_failure_groups():
    # 2 个支付超时 + 2 个鉴权失败 -> 应该聚类为 2 个不同的主缺陷组
    failures = [
        TestCaseFailureRecord(
            run_id="run_1",
            case_id="c_pay_1",
            case_name="支付A",
            error_message="PaymentError: insufficient",
            stack_trace='  File "/app/pay.py", line 10, in do_pay\n    pay()',
            target_service="payment-service",
        ),
        TestCaseFailureRecord(
            run_id="run_1",
            case_id="c_pay_2",
            case_name="支付B",
            error_message="PaymentError: insufficient",
            stack_trace='  File "/app/pay.py", line 10, in do_pay\n    pay()',
            target_service="payment-service",
        ),
        TestCaseFailureRecord(
            run_id="run_1",
            case_id="c_auth_1",
            case_name="登录A",
            error_message="AuthTokenExpiredError: expired",
            stack_trace='  File "/app/auth.py", line 25, in verify\n    auth()',
            target_service="auth-service",
        ),
        TestCaseFailureRecord(
            run_id="run_1",
            case_id="c_auth_2",
            case_name="登录B",
            error_message="AuthTokenExpiredError: expired",
            stack_trace='  File "/app/auth.py", line 25, in verify\n    auth()',
            target_service="auth-service",
        ),
    ]

    result = cluster_and_deduplicate_failures(failures)
    assert result.total_raw_failures == 4
    assert result.total_deduplicated_clusters == 2
    assert result.deduplication_ratio_pct == 50.0

    d = result.to_dict()
    assert d["total_raw_failures"] == 4
    assert len(d["clusters"]) == 2


def test_cluster_empty_failures():
    res = cluster_and_deduplicate_failures([])
    assert res.total_raw_failures == 0
    assert res.total_deduplicated_clusters == 0
    assert res.deduplication_ratio_pct == 100.0
