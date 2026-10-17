"""接口响应结构变迁与漂移检测器单测 (T2.1)"""

from __future__ import annotations

from app.services.response_schema_drift_detector import (
    DriftMutationType,
    ResponseSchemaDriftReport,
    detect_response_schema_drift,
    flatten_json_paths,
)


def test_flatten_json_paths():
    sample = {
        "user": {
            "name": "Alice",
            "age": 28,
            "roles": ["admin", "tester"],
        },
        "status": "active",
    }
    paths = flatten_json_paths(sample)
    assert "$.user.name" in paths
    assert paths["$.user.name"] == ("Alice", "str")
    assert "$.user.age" in paths
    assert paths["$.user.age"] == (28, "int")
    assert "$.user.roles[0]" in paths
    assert paths["$.user.roles[0]"] == ("admin", "str")
    assert "$.status" in paths


def test_detect_field_renamed_snake_to_camel():
    baseline = {
        "user_id": 1001,
        "user_name": "bob_tester",
    }
    actual = {
        "userId": 1001,
        "userName": "bob_tester",
    }

    report = detect_response_schema_drift(baseline, actual)
    assert isinstance(report, ResponseSchemaDriftReport)
    assert report.is_drift_detected is True
    assert report.drifted_field_count == 2

    types = [d.mutation_type for d in report.drifts]
    assert all(t == DriftMutationType.FIELD_RENAMED for t in types)

    d1 = next(d for d in report.drifts if d.old_path == "$.user_id")
    assert d1.new_path == "$.userId"
    assert d1.confidence >= 0.90


def test_detect_envelope_unwrapped():
    # 原扁平响应
    baseline = {
        "order_id": 999888,
        "pay_amount": 199.5,
    }
    # 微服务标准包装改版
    actual = {
        "code": 200,
        "message": "success",
        "data": {
            "orderId": 999888,
            "payAmount": 199.5,
        },
    }

    report = detect_response_schema_drift(baseline, actual)
    assert report.is_drift_detected is True
    assert report.drifted_field_count == 2

    envelope_drifts = [d for d in report.drifts if d.mutation_type == DriftMutationType.ENVELOPE_UNWRAPPED]
    assert len(envelope_drifts) == 2
    assert any(d.new_path == "$.data.orderId" for d in envelope_drifts)
    assert any(d.new_path == "$.data.payAmount" for d in envelope_drifts)

    # 查验新增加的顶层状态字段
    assert "$.code" in report.newly_added_paths
    assert "$.message" in report.newly_added_paths


def test_detect_type_mutation_and_serialization():
    baseline = {
        "discount_rate": "0.15",  # 字符串
    }
    actual = {
        "discount_rate": 0.15,  # 演进为浮点数
    }

    report = detect_response_schema_drift(baseline, actual)
    assert report.is_drift_detected is True
    assert len(report.drifts) == 1
    assert report.drifts[0].mutation_type == DriftMutationType.TYPE_MUTATED
    assert "原类型为 'str'" in report.drifts[0].explanation

    d = report.to_dict()
    assert d["report_id"].startswith("drf_")
    assert d["is_drift_detected"] is True
    assert len(d["drifts"]) == 1
