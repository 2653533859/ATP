"""大模型评测与 RAG 质量基准 REST API 单测 (T1.3)"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user, require_engineer
from app.main import app
from app.models.user import User

HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(autouse=True)
def setup_eval_api():
    mock_user = User(id=1, email="llm_qa@example.com", username="llm_qa", role="engineer")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[require_engineer] = lambda: mock_user
    yield
    app.dependency_overrides.clear()


def test_api_evaluate_rag_triad():
    client = TestClient(app)

    # 1. 正常评测
    r1 = client.post(
        "/api/v1/llm-eval/rag-triad",
        headers=HEADERS,
        json={
            "query": "ATP 如何保证全链路压测数据隔离？",
            "contexts": [
                "ATP 具备影子存储隔离机制，所有压测写操作自动路由至 t_order_shadow。",
            ],
            "answer": "ATP 通过影子存储机制将写操作路由至 t_order_shadow 影子表进行隔离。",
        },
    )
    assert r1.status_code == 200
    data = r1.json()
    assert data["status"] == "success"
    assert data["report"]["composite_score"] >= 75.0
    assert data["report"]["grade"] in {"EXCELLENT", "GOOD"}

    # 2. 空参数校验
    r2 = client.post(
        "/api/v1/llm-eval/rag-triad",
        headers=HEADERS,
        json={
            "query": "   ",
            "contexts": [],
            "answer": "回答",
        },
    )
    assert r2.status_code == 400


def test_api_detect_hallucination():
    client = TestClient(app)

    # 1. 正常幻觉检测
    r1 = client.post(
        "/api/v1/llm-eval/hallucination/detect",
        headers=HEADERS,
        json={
            "query": "压测并发上限是多少？",
            "answer": "ATP 压测单节点上限为 2000 个虚拟用户。",
            "golden_facts": [
                "ATP 压测单发压节点承载上限为 2000 个虚拟用户 (VU)。",
            ],
            "model_name": "qwen-2.5-72b",
        },
    )
    assert r1.status_code == 200
    data = r1.json()
    assert data["status"] == "success"
    assert data["report"]["verdict"] == "FACTUAL_PASS"
    assert data["report"]["factual_consistency_score"] == 100.0

    # 2. 空黄金事实返回 400
    r2 = client.post(
        "/api/v1/llm-eval/hallucination/detect",
        headers=HEADERS,
        json={
            "query": "测试",
            "answer": "测试回答",
            "golden_facts": [],
        },
    )
    assert r2.status_code == 400


def test_api_batch_evaluate():
    client = TestClient(app)
    resp = client.post(
        "/api/v1/llm-eval/batch-evaluate",
        headers=HEADERS,
        json={
            "benchmark_name": "支付结算智能体评测套件",
            "items": [
                {
                    "item_id": "item_01",
                    "query": "如何执行退款？",
                    "contexts": ["退款接口为 /pay/refund，需提供 order_id。"],
                    "answer": "调用 /pay/refund 接口并传入 order_id 即可退款。",
                    "golden_facts": ["退款接口为 /pay/refund，需提供 order_id。"],
                },
                {
                    "item_id": "item_02",
                    "query": "支持哪些币种？",
                    "contexts": ["系统支持 CNY 和 USD。"],
                    "answer": "目前支持人民币 CNY 与美元 USD 结算。",
                },
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["total_items"] == 2
    assert data["average_rag_score"] >= 70.0
    assert len(data["results"]) == 2


def test_api_benchmarks_overview():
    client = TestClient(app)
    resp = client.get("/api/v1/llm-eval/benchmarks/overview", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["evaluated_models_count"] >= 3
    assert any(m["model_name"] == "qwen-2.5-72b" for m in data["models"])


def test_api_authentication_and_engineer_role_enforcement():
    """测试未登录请求被 401 拦截，以及普通非工程用户调用批量评测被 403 阻断"""
    client = TestClient(app)

    # 1. 模拟未认证请求被 401 拦截
    from fastapi import HTTPException

    def raise_401():
        raise HTTPException(status_code=401, detail="Not authenticated")

    app.dependency_overrides[get_current_user] = raise_401
    r_anon = client.get("/api/v1/llm-eval/benchmarks/overview")
    assert r_anon.status_code == 401

    # 2. 模拟普通只读用户 (viewer 角色) 访问 batch-evaluate 被 403 拒绝
    viewer_user = User(id=99, email="viewer@example.com", username="viewer", role="viewer")
    app.dependency_overrides[get_current_user] = lambda: viewer_user

    def forbid_non_engineer():
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    app.dependency_overrides[require_engineer] = forbid_non_engineer
    r_viewer = client.post(
        "/api/v1/llm-eval/batch-evaluate",
        headers=HEADERS,
        json={"items": [{"query": "Q", "contexts": ["C"], "answer": "A"}]},
    )
    assert r_viewer.status_code == 403
