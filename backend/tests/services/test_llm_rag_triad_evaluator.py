"""RAG 知识检索召回与上下文相关度精算器单测 (T1.1)"""

from __future__ import annotations

from app.services.llm_rag_triad_evaluator import (
    _split_into_claims,
    _tokenize_terms,
    evaluate_rag_triad,
)


def test_tokenize_terms_and_split_claims():
    tokens = _tokenize_terms("ATP 平台支持 HTTP 和 gRPC 全链路压测！")
    assert "atp" in tokens
    assert "http" in tokens
    assert "grpc" in tokens
    assert "压" in tokens
    assert "测" in tokens

    claims = _split_into_claims(
        "金丝雀发布支持流量染色。同时数据库写操作会自动路由至影子库；此外系统具备秒级自动熔断！"
    )
    assert len(claims) == 3
    assert "流量染色" in claims[0]
    assert "影子库" in claims[1]
    assert "自动熔断" in claims[2]


def test_evaluate_rag_triad_excellent_case():
    query = "ATP 平台如何防止压测流量污染生产主库？"
    contexts = [
        "ATP 全链路压测引擎具备影子存储隔离机制，所有带有 X-Stress-Test 标识的写操作会自动路由至影子表 t_order_shadow。",
        "若检测到压测流量直接穿透写入生产核心主表（如 t_order 或 t_account_balance），看门狗会立即触发致命拦截。",
    ]
    answer = (
        "ATP 平台通过影子存储隔离机制防止污染生产主库。系统将带有压测标的写操作自动路由至影子表 t_order_shadow。"
        "同时看门狗会监控核心主表，一旦发生直接穿透会立即触发拦截。"
    )

    report = evaluate_rag_triad(query, contexts, answer)

    assert report.context_relevance > 0.4
    assert report.groundedness >= 0.8  # 回答断言均有知识库上下文支撑
    assert report.answer_relevance > 0.5
    assert report.composite_score >= 75.0
    assert report.grade in {"EXCELLENT", "GOOD"}
    assert len(report.chunks) == 2
    assert all(chk.relevance_score > 0 for chk in report.chunks)


def test_evaluate_rag_triad_hallucination_detection():
    query = "ATP 平台支持哪些发压模型？"
    contexts = [
        "系统支持阶梯递进爬坡（Step Ramp-Up）与恒定稳态并发两种模式。",
    ]
    # 模型胡编乱造了未在上下文中出现的常识或虚假内容
    answer = "ATP 平台支持量子超导纠缠发压模型。此外还独家支持跨星际光速脉冲测试，每次可产生一亿并发。"

    report = evaluate_rag_triad(query, contexts, answer)

    assert report.groundedness < 0.3  # 极低忠实度（严重幻觉）
    assert any(not ca.is_grounded for ca in report.claim_attributions)
    assert "无检索上下文事实依据" in report.claim_attributions[0].evidence_snippet
    assert report.composite_score < 60.0
    assert report.grade in {"MARGINAL", "POOR"}


def test_evaluate_rag_triad_serialization():
    query = "测试查询"
    contexts = ["上下文片段一"]
    answer = "测试回答内容完整。"

    report = evaluate_rag_triad(query, contexts, answer)
    d = report.to_dict()

    assert d["query"] == query
    assert d["answer"] == answer
    assert "context_relevance" in d
    assert "groundedness" in d
    assert "answer_relevance" in d
    assert "composite_score" in d
    assert "grade" in d
    assert len(d["chunks"]) == 1
    assert len(d["claim_attributions"]) >= 1
