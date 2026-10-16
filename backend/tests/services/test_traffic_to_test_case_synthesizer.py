"""Unit tests for Traffic to TestCase Synthesizer Service (T1.3)."""

from __future__ import annotations

import json
import pytest

from app.services.traffic_to_test_case_synthesizer import (
    cluster_traffic_records,
    extract_schema_signature,
    generate_synthesized_assertions,
    get_synthesis_report,
    list_synthesis_reports,
    normalize_url_path,
    reset_synthesis_reports,
    synthesize_test_cases_from_traffic,
)


@pytest.fixture(autouse=True)
def clean_reports():
    reset_synthesis_reports()
    yield
    reset_synthesis_reports()


def test_normalize_url_path():
    """验证 URL 动态数字与 UUID 路径参数归一化。"""
    assert normalize_url_path("/api/v1/orders/1024") == "/api/v1/orders/{id}"
    assert normalize_url_path("/api/v1/users/123/profile") == "/api/v1/users/{id}/profile"
    assert normalize_url_path("/api/v1/items/c3d4e5f6-a7b8-1234-5678-abcdef123456") == "/api/v1/items/{uuid}"


def test_extract_schema_signature():
    """验证从 JSON 字典提取排序后的字段类型签名。"""
    sig = extract_schema_signature({"amount": 199.5, "user_id": 100, "paid": True})
    assert sig == "{amount:float,paid:bool,user_id:int}"

    list_sig = extract_schema_signature([{"id": 1}])
    assert list_sig == "[dict]"


def test_generate_synthesized_assertions():
    """验证自动为代表性流量生成状态码、SLA 与业务状态码断言。"""
    traffic = {
        "response_status_code": 200,
        "duration_ms": 60.0,
        "response_body": json.dumps({"code": 0, "message": "success", "data": {"order_id": 999}}),
    }

    assertions = generate_synthesized_assertions(traffic)
    assert len(assertions) >= 3

    # 1. status_code 断言
    status_assert = next(a for a in assertions if a["target"] == "status_code")
    assert status_assert["expected"] == 200

    # 2. SLA 时延断言
    sla_assert = next(a for a in assertions if a["target"] == "duration_ms")
    assert sla_assert["expected"] == 200.0  # max(200.0, 60*2)

    # 3. 业务状态码断言
    code_assert = next(a for a in assertions if a["target"] == "body.code")
    assert code_assert["expected"] == 0


def test_cluster_traffic_records():
    """验证相同路径模式与 Schema 的流量被归并至同一 Cluster，不同入参提取为 Dataset 行。"""
    records = [
        {
            "traffic_id": "trf_1",
            "protocol": "HTTP",
            "method": "POST",
            "path_or_endpoint": "/api/v1/orders/1001",
            "request_body": json.dumps({"amount": 50.0, "coupon": "C1"}),
            "response_status_code": 200,
        },
        {
            "traffic_id": "trf_2",
            "protocol": "HTTP",
            "method": "POST",
            "path_or_endpoint": "/api/v1/orders/1002",
            "request_body": json.dumps({"amount": 120.0, "coupon": "C2"}),
            "response_status_code": 200,
        },
        {
            "traffic_id": "trf_3",
            "protocol": "HTTP",
            "method": "POST",
            "path_or_endpoint": "/api/v1/orders/1003",
            "request_body": json.dumps({"amount": 300.0, "coupon": "C3"}),
            "response_status_code": 200,
        },
        {
            "traffic_id": "trf_4",
            "protocol": "HTTP",
            "method": "GET",
            "path_or_endpoint": "/api/v1/users/888",
            "request_body": "",
            "response_status_code": 200,
        },
    ]

    clusters = cluster_traffic_records(records)
    # 应聚类为 2 簇：POST /api/v1/orders/{id} (3 条) 与 GET /api/v1/users/{id} (1 条)
    assert len(clusters) == 2

    order_cluster = next(c for c in clusters if c.method == "POST")
    assert order_cluster.normalized_path == "/api/v1/orders/{id}"
    assert order_cluster.sample_count == 3
    assert len(order_cluster.extracted_dataset_rows) == 3


def test_synthesize_test_cases_with_auto_masking():
    """验证端到端测试用例合成，并确保自动脱敏清洗 PII 数据。"""
    records = [
        {
            "traffic_id": "trf_sensitive_1",
            "protocol": "HTTP",
            "method": "POST",
            "path_or_endpoint": "/api/v1/user/register",
            "headers": {"Authorization": "Bearer token_secret_123"},
            "query_params": {"channel": "h5"},
            "request_body": json.dumps(
                {
                    "phone": "13812345678",
                    "id_card": "110101199003071234",
                    "password": "ClearTextPassword123!",
                }
            ),
            "response_status_code": 200,
            "response_body": json.dumps({"code": 0, "phone": "13812345678"}),
            "duration_ms": 40.0,
        },
        {
            "traffic_id": "trf_sensitive_2",
            "protocol": "HTTP",
            "method": "POST",
            "path_or_endpoint": "/api/v1/user/register",
            "headers": {"Authorization": "Bearer token_secret_456"},
            "query_params": {"channel": "app"},
            "request_body": json.dumps(
                {
                    "phone": "13987654321",
                    "id_card": "110101199505051234",
                    "password": "AnotherPassword456!",
                }
            ),
            "response_status_code": 200,
            "response_body": json.dumps({"code": 0, "phone": "13987654321"}),
            "duration_ms": 45.0,
        },
    ]

    report = synthesize_test_cases_from_traffic(
        records=records,
        auto_mask_first=True,
        max_dataset_rows_per_case=5,
    )

    assert report.total_traffic_evaluated == 2
    assert report.clusters_formed == 1
    assert report.deduplication_ratio_pct == 50.0  # 2 条流量聚类成 1 条用例 -> 50% 去重率
    assert report.synthesized_cases_count == 1

    case = report.cases[0]
    assert case.protocol == "HTTP"
    assert case.method == "POST"
    assert case.url_path == "/api/v1/user/register"

    # 验证用例与数据集中的手机号/密码已被完全脱敏
    body_parsed = json.loads(case.request_body_template)
    assert body_parsed["phone"].startswith("138****")
    assert body_parsed["id_card"].startswith("110101********")
    assert body_parsed["password"] == "[REDACTED]"

    assert len(case.dataset_rows) == 2
    row_1_body = json.loads(case.dataset_rows[0]["request_body"])
    assert row_1_body["phone"].startswith("138****")

    # 验证可通过报告 ID 检索
    fetched = get_synthesis_report(report.report_id)
    assert fetched is not None
    assert fetched.report_id == report.report_id
    assert len(list_synthesis_reports()) == 1
