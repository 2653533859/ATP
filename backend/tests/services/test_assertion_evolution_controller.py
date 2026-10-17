"""断言演进置信度评分与安全回滚控制器单测 (T2.3)"""

from __future__ import annotations

import pytest

from app.services.assertion_drift_evolution_synthesizer import (
    AssertionEvolutionResult,
    EvolutionStatus,
)
from app.services.assertion_evolution_controller import (
    DryRunStatus,
    RiskLevel,
    SnapshotStatus,
    clear_assertion_snapshots,
    dry_run_evolved_assertion,
    evaluate_assertion_evolution_confidence,
    get_assertion_version_snapshot,
    list_assertion_snapshots,
    record_assertion_version_snapshot,
    rollback_assertion_version,
)
from app.services.response_schema_drift_detector import (
    DriftMutationType,
    SchemaDriftItem,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_assertion_snapshots()
    yield
    clear_assertion_snapshots()


def test_confidence_evaluation_low_risk():
    evolution = AssertionEvolutionResult(
        evolution_id="evo_1",
        original_code="assert res['user_id'] == 1001",
        evolved_code="assert res['userId'] == 1001",
        unified_diff="",
        applied_drift_ids=["d1"],
        status=EvolutionStatus.EVOLVED,
        evolution_notes=[],
    )
    drift = SchemaDriftItem(
        drift_id="d1",
        mutation_type=DriftMutationType.FIELD_RENAMED,
        old_path="$.user_id",
        new_path="$.userId",
        old_value_sample=1001,
        new_value_sample=1001,
        confidence=0.95,
        explanation="重命名",
    )

    eval_res = evaluate_assertion_evolution_confidence(evolution, [drift])
    assert eval_res.score >= 85.0
    assert eval_res.risk_level == RiskLevel.LOW
    assert eval_res.is_safe_to_auto_apply is True
    assert "底层 Schema 漂移高置信对齐" in eval_res.reasons[0]


def test_confidence_evaluation_with_relocation_penalty():
    evolution = AssertionEvolutionResult(
        evolution_id="evo_2",
        original_code="assert res['role'] == 'admin'",
        evolved_code="assert res['account']['profile']['role'] == 'admin'",
        unified_diff="",
        applied_drift_ids=["d2"],
        status=EvolutionStatus.EVOLVED,
        evolution_notes=[],
    )
    drift = SchemaDriftItem(
        drift_id="d2",
        mutation_type=DriftMutationType.PATH_RELOCATED,
        old_path="$.role",
        new_path="$.account.profile.role",
        old_value_sample="admin",
        new_value_sample="admin",
        confidence=0.90,
        explanation="深层位移",
    )

    eval_res = evaluate_assertion_evolution_confidence(evolution, [drift])
    # 扣减了 10 分
    assert eval_res.score == 85.0
    assert any("涉及深层路径位移" in r for r in eval_res.reasons)


def test_dry_run_sandbox_pass_and_fail():
    payload = {"data": {"orderId": "OD_123", "amount": 99.0}}

    # 1. PASS 断言
    res_pass = dry_run_evolved_assertion(
        "assert res['data']['orderId'] == 'OD_123' and res['data']['amount'] > 50",
        payload,
    )
    assert res_pass.status == DryRunStatus.PASS
    assert res_pass.error_message is None
    assert res_pass.elapsed_ms >= 0

    # 2. FAIL 断言 (AssertionError)
    res_fail = dry_run_evolved_assertion(
        "assert res['data']['orderId'] == 'OD_999'",
        payload,
    )
    assert res_fail.status == DryRunStatus.FAIL
    assert "断言条件未能成立" in res_fail.output_summary

    # 3. ERROR 断言 (KeyError)
    res_err = dry_run_evolved_assertion(
        "assert res['non_existent_key']['sub'] == 1",
        payload,
    )
    assert res_err.status == DryRunStatus.ERROR
    assert "KeyError" in str(res_err.error_message)


def test_snapshot_lifecycle_and_rollback():
    snap = record_assertion_version_snapshot(
        case_id="case_api_01",
        step_id="step_check_order",
        original_assertion="assert res['order_id'] == 888",
        evolved_assertion="assert res['data']['orderId'] == 888",
        confidence_score=92.5,
        risk_level=RiskLevel.LOW,
        applied_drift_ids=["d_order"],
    )
    assert snap.status == SnapshotStatus.ACTIVE
    assert snap.current_assertion == "assert res['data']['orderId'] == 888"

    # 查询单张快照与列表
    fetched = get_assertion_version_snapshot(snap.version_id)
    assert fetched is not None
    assert fetched.version_id == snap.version_id

    listed = list_assertion_snapshots(case_id="case_api_01")
    assert len(listed) == 1

    # 执行一键回滚
    rollbacked = rollback_assertion_version(snap.version_id)
    assert rollbacked is not None
    assert rollbacked.status == SnapshotStatus.ROLLBACKED
    assert rollbacked.current_assertion == "assert res['order_id'] == 888"
    assert rollbacked.rollbacked_at is not None

    d = rollbacked.to_dict()
    assert d["status"] == "ROLLBACKED"
    assert d["risk_level"] == "LOW"
