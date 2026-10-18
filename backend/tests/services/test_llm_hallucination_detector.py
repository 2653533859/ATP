"""大模型幻觉率统计与事实一致性校验器单测 (T1.2)"""

from __future__ import annotations

from app.services.llm_hallucination_detector import (
    HallucinationSeverity,
    HallucinationType,
    HallucinationVerdict,
    _extract_numbers,
    _split_into_sentences,
    detect_llm_hallucinations,
)


def test_helpers_extract_numbers_and_sentences():
    nums = _extract_numbers("当前压测并发为 5000 VU，P99 时延达到 185.5ms，错误率 1.5%")
    assert "5000" in nums
    assert "185.5" in nums
    assert "1.5%" in nums

    sents = _split_into_sentences("金丝雀发布支持分流。此外支持影子库隔离；看门狗会进行自动熔断！")
    assert len(sents) == 3


def test_detect_hallucinations_factual_pass():
    golden_facts = [
        "ATP 全链路压测单发压节点承载上限为 2000 个虚拟用户 (VU)。",
        "当生产微服务 CPU 突破 85% 或错误率超过 1.0% 时，看门狗会立即触发自动断路切流。",
    ]
    answer = (
        "ATP 平台的发压节点单 Pod 最大承载为 2000 个虚拟用户 (VU)。"
        "同时系统具备过载熔断看门狗，当 CPU 达到 85% 或错误率达 1.0% 时会自动断路。"
    )

    report = detect_llm_hallucinations(
        query="ATP 压测的并发限制和熔断条件是什么？",
        answer=answer,
        golden_facts=golden_facts,
        model_name="qwen-2.5-72b",
    )

    assert report.verdict == HallucinationVerdict.FACTUAL_PASS
    assert report.hallucinated_claims_count == 0
    assert report.hallucination_rate_pct == 0.0
    assert report.factual_consistency_score == 100.0


def test_detect_numerical_conflict():
    golden_facts = [
        "生产微服务系统的 P99 响应延迟保护阈值上限设定为 500ms。",
    ]
    # 模型生成了冲突的数值：把 500ms 编造成 8500ms
    answer = "生产微服务的 P99 延迟上限为 8500ms，超时才会报警。"

    report = detect_llm_hallucinations(
        query="延迟上限是多少？",
        answer=answer,
        golden_facts=golden_facts,
    )

    assert report.hallucinated_claims_count >= 1
    assert any(f.hallucination_type == HallucinationType.NUMERICAL_CONFLICT for f in report.findings)
    assert report.hallucination_rate_pct > 0


def test_detect_logical_contradiction():
    golden_facts = [
        "在全链路压测过程中，严禁向生产真实核心主表写入测试数据。",
    ]
    # 极性反转：把“严禁”反转为“可以写入”
    answer = "在全链路压测过程中，可以向生产真实核心主表写入测试数据以验证真实承载能力。"

    report = detect_llm_hallucinations(
        query="压测是否可以直接写生产主表？",
        answer=answer,
        golden_facts=golden_facts,
    )

    assert report.verdict == HallucinationVerdict.CRITICAL_HALLUCINATION
    assert any(f.hallucination_type == HallucinationType.LOGICAL_CONTRADICTION for f in report.findings)
    assert any(f.severity == HallucinationSeverity.CRITICAL for f in report.findings)


def test_detect_fabricated_entity():
    golden_facts = [
        "ATP 核心服务包含 order_service 与 payment_service 两个微服务。",
    ]
    # 虚构了不存在的实体模块
    answer = "系统底层调用了 `QuantumTeleportationDriver` 驱动进行跨星系分布式通讯。"

    report = detect_llm_hallucinations(
        query="系统调用什么驱动？",
        answer=answer,
        golden_facts=golden_facts,
    )

    assert any(f.hallucination_type == HallucinationType.FABRICATED_ENTITY for f in report.findings)
    assert "未在黄金知识事实库中登记" in report.findings[0].conflict_detail


def test_report_serialization():
    report = detect_llm_hallucinations(
        query="测试",
        answer="这是一个事实测试断言。",
        golden_facts=["这是一个事实测试断言。"],
    )
    d = report.to_dict()
    assert d["model_name"] == "qwen-2.5-72b"
    assert "hallucination_rate_pct" in d
    assert "factual_consistency_score" in d
    assert "verdict" in d
    assert "findings" in d
