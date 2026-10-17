"""动态字段动态噪声自适应抑制器单测 (T2.2)"""

from __future__ import annotations

from app.services.dynamic_noise_suppressor import (
    NoiseSuppressionRule,
    NoiseType,
    is_heuristic_noise,
    match_custom_rule,
    suppress_traffic_diff_noise,
)
from app.services.traffic_response_diff_comparator import (
    DiffSeverity,
    ResponseDiffCategory,
    ResponseDiffItem,
    compare_traffic_responses,
)


def test_is_heuristic_noise_detection():
    # 1. 时间戳识别 (键名与正则)
    assert is_heuristic_noise("$.created_at", "2026-10-17T12:00:00Z", "2026-10-17T12:00:01Z") == NoiseType.TIMESTAMP
    assert is_heuristic_noise("$.timestamp", 1729166400, 1729166401) == NoiseType.TIMESTAMP

    # 2. 链路追踪 ID 识别
    assert (
        is_heuristic_noise("$.trace_id", "4bf92f3577b34da6a3ce929d0e0e4736", "7c98835265353385929d0e0e47361234")
        == NoiseType.TRACE_ID
    )
    assert is_heuristic_noise("$.request_id", "req_1", "req_2") == NoiseType.TRACE_ID

    # 3. 随机 UUID 识别
    assert (
        is_heuristic_noise(
            "$.data.session_id",
            "123e4567-e89b-12d3-a456-426614174000",
            "987f6543-e21b-12d3-a456-426614174999",
        )
        == NoiseType.UUID_RANDOM
    )

    # 4. 真实业务字段绝不误判
    assert is_heuristic_noise("$.data.order_status", "PAID", "CANCELLED") is None
    assert is_heuristic_noise("$.data.amount", 100.5, 99.0) is None


def test_custom_rule_matching():
    diff = ResponseDiffItem(
        diff_id="d1",
        category=ResponseDiffCategory.VALUE_MISMATCH,
        severity=DiffSeverity.MINOR,
        json_path="$.meta.server_ip",
        baseline_value="192.168.1.10",
        replayed_value="192.168.1.20",
        message="ip mismatch",
    )

    rule = NoiseSuppressionRule(
        rule_id="r1",
        name="忽略服务器IP偏离",
        noise_type=NoiseType.CUSTOM_RULE,
        path_pattern="*.server_ip",
        enabled=True,
    )

    assert match_custom_rule(diff, rule) is True

    # 禁用规则时不命中
    rule.enabled = False
    assert match_custom_rule(diff, rule) is False


def test_suppress_traffic_diff_noise_separation():
    base_body = {
        "order_id": "OD_1001",
        "created_at": "2026-10-17T10:00:00Z",  # 噪声
        "trace_id": "c74f9d1234567890abcdef1234567890",  # 噪声
        "amount": 99.0,  # 真实业务差异
    }
    replayed_body = {
        "order_id": "OD_1001",
        "created_at": "2026-10-17T10:00:05Z",  # 噪声
        "trace_id": "92c14c281234567890abcdef1234567890",  # 噪声
        "amount": 105.0,  # 真实业务差异
    }

    raw_report = compare_traffic_responses(
        record_id="rec_order_diff",
        baseline_status_code=200,
        baseline_body=base_body,
        replayed_status_code=200,
        replayed_body=replayed_body,
    )
    assert raw_report.diff_count == 3  # created_at, trace_id, amount

    # 运行自适应降噪
    suppressed = suppress_traffic_diff_noise(raw_report, enable_heuristics=True)

    assert suppressed.original_diff_count == 3
    assert suppressed.suppressed_noise_count == 2
    assert suppressed.effective_diff_count == 1

    # 真实业务差异仅剩 amount
    assert suppressed.effective_diffs[0].json_path == "$.amount"
    assert suppressed.effective_diffs[0].is_noise is False

    # 噪声列表包含两个时间与链路项
    noise_paths = [d.json_path for d in suppressed.noise_diffs]
    assert "$.created_at" in noise_paths
    assert "$.trace_id" in noise_paths
    assert all(d.is_noise is True for d in suppressed.noise_diffs)


def test_status_code_mismatch_never_suppressed():
    # 状态码偏离即使带时间戳键名也绝不能被抑制
    diff_report = compare_traffic_responses(
        record_id="rec_fail",
        baseline_status_code=200,
        baseline_body={"timestamp": 123},
        replayed_status_code=500,
        replayed_body={"timestamp": 456},
    )

    suppressed = suppress_traffic_diff_noise(diff_report)
    assert any(d.category == ResponseDiffCategory.STATUS_CODE_MISMATCH for d in suppressed.effective_diffs)
    assert suppressed.has_effective_breaking is True
