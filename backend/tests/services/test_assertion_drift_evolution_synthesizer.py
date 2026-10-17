"""语义断言智能演进与语法重写器单测 (T2.2)"""

from __future__ import annotations

from app.services.assertion_drift_evolution_synthesizer import (
    EvolutionStatus,
    synthesize_assertion_evolution,
)
from app.services.response_schema_drift_detector import (
    DriftMutationType,
    SchemaDriftItem,
)


def test_synthesize_field_renamed():
    original_code = 'assert resp["user_id"] == 1001'
    drift = SchemaDriftItem(
        drift_id="d1",
        mutation_type=DriftMutationType.FIELD_RENAMED,
        old_path="$.user_id",
        new_path="$.userId",
        old_value_sample=1001,
        new_value_sample=1001,
        confidence=0.96,
        explanation="字段重命名为驼峰",
    )

    res = synthesize_assertion_evolution(original_code, [drift])
    assert res.status == EvolutionStatus.EVOLVED
    assert res.evolved_code == "assert resp['userId'] == 1001"
    assert "d1" in res.applied_drift_ids
    assert "--- original_assertion.py" in res.unified_diff
    assert "+++ evolved_assertion.py" in res.unified_diff


def test_synthesize_envelope_unwrapped():
    original_code = 'assert res["order_id"] == 888 and res["amount"] > 10'
    drift1 = SchemaDriftItem(
        drift_id="d_order",
        mutation_type=DriftMutationType.ENVELOPE_UNWRAPPED,
        old_path="$.order_id",
        new_path="$.data.orderId",
        old_value_sample=888,
        new_value_sample=888,
        confidence=0.98,
        explanation="包裹入 data",
    )

    res = synthesize_assertion_evolution(original_code, [drift1])
    assert res.status == EvolutionStatus.EVOLVED
    assert "res['data']['orderId'] == 888" in res.evolved_code
    assert "res['amount'] > 10" in res.evolved_code


def test_synthesize_get_call_chaining():
    original_code = 'assert res.get("user_id") == 1001'
    drift = SchemaDriftItem(
        drift_id="d_get",
        mutation_type=DriftMutationType.ENVELOPE_UNWRAPPED,
        old_path="$.user_id",
        new_path="$.data.userId",
        old_value_sample=1001,
        new_value_sample=1001,
        confidence=0.97,
        explanation="包装展开",
    )

    res = synthesize_assertion_evolution(original_code, [drift])
    assert res.status == EvolutionStatus.EVOLVED
    assert "res.get('data', {}).get('userId') == 1001" in res.evolved_code


def test_synthesize_type_coercion():
    original_code = 'assert res["discount_rate"] == "0.15"'
    drift = SchemaDriftItem(
        drift_id="d_type",
        mutation_type=DriftMutationType.TYPE_MUTATED,
        old_path="$.discount_rate",
        new_path="$.discount_rate",
        old_value_sample="0.15",
        new_value_sample=0.15,
        confidence=0.95,
        explanation="类型演进为 float",
    )

    res = synthesize_assertion_evolution(original_code, [drift])
    assert res.status == EvolutionStatus.EVOLVED
    assert res.evolved_code == "assert res['discount_rate'] == 0.15"


def test_unchanged_and_syntax_error():
    # 语法错误用例
    bad_code = "assert res['user_id'] =="
    res_err = synthesize_assertion_evolution(bad_code, [])
    assert res_err.status == EvolutionStatus.SYNTAX_ERROR

    # 毫无关联代码
    unrelated_code = "assert 1 + 1 == 2"
    drift = SchemaDriftItem(
        drift_id="d_other",
        mutation_type=DriftMutationType.FIELD_RENAMED,
        old_path="$.token",
        new_path="$.accessToken",
        old_value_sample="abc",
        new_value_sample="abc",
        confidence=0.9,
        explanation="",
    )
    res_unchanged = synthesize_assertion_evolution(unrelated_code, [drift])
    assert res_unchanged.status == EvolutionStatus.UNCHANGED
