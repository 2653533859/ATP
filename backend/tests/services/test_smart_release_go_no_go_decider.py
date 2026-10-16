"""自动化发版准入阻断裁决器与豁免流转单元测试 (T4.2)。"""

from __future__ import annotations

import pytest
from app.services.smart_release_go_no_go_decider import (
    ReleaseVerdict,
    clear_release_gate_store,
    evaluate_release_gate,
    get_release_gate_record,
    grant_risk_waiver,
    list_release_gate_records,
    revoke_risk_waiver,
)


@pytest.fixture(autouse=True)
def _reset_gate_state():
    clear_release_gate_store()
    yield
    clear_release_gate_store()


def test_evaluate_release_gate_go():
    """测试各项质量达标时输出 GO 准入放行。"""
    rec = evaluate_release_gate(
        target_version="v4.2.0",
        quality_score=92.5,
        p0_defects_count=0,
        p1_defects_count=0,
        critical_security_flaws_count=0,
        test_pass_rate_pct=100.0,
    )
    assert rec.verdict == ReleaseVerdict.GO
    assert len(rec.blocking_reasons) == 0
    assert len(rec.warning_reasons) == 0


def test_evaluate_release_gate_caution():
    """测试质量处于预警区间或存在 P1 缺陷时输出 CAUTION 警示放行。"""
    rec = evaluate_release_gate(
        target_version="v4.2.0-beta",
        quality_score=78.0,
        p0_defects_count=0,
        p1_defects_count=1,
        test_pass_rate_pct=98.5,
    )
    assert rec.verdict == ReleaseVerdict.CAUTION
    assert len(rec.blocking_reasons) == 0
    assert len(rec.warning_reasons) >= 1


def test_evaluate_release_gate_no_go_and_waiver():
    """测试存在 P0 缺陷时触发 NO_GO 严苛阻断，随后签署特批豁免流转为 WAIVED_GO。"""
    rec = evaluate_release_gate(
        target_version="v4.2.0-rc1",
        quality_score=60.0,
        p0_defects_count=1,
    )
    assert rec.verdict == ReleaseVerdict.NO_GO
    assert len(rec.blocking_reasons) >= 1

    # 签署特批风险豁免
    waiver_res = grant_risk_waiver(
        release_id=rec.release_id,
        approver="chief_architect_zhang",
        waiver_reason="线上已配置功能灰度开关，P0 仅影响非核心辅助流，且已具备回滚方案",
        rollback_plan="Git revert 提交并在 10 分钟内完成热容器重新部署",
    )
    assert waiver_res["success"] is True
    assert waiver_res["record"]["verdict"] == ReleaseVerdict.WAIVED_GO.value
    assert waiver_res["record"]["is_waived"] is True

    # 验证撤销豁免
    revoke_res = revoke_risk_waiver(rec.release_id)
    assert revoke_res["success"] is True
    assert revoke_res["record"]["verdict"] == ReleaseVerdict.NO_GO.value


def test_list_and_get_records():
    """测试记录持久化与列表查询。"""
    rec = evaluate_release_gate(target_version="v1.0", quality_score=90.0)
    found = get_release_gate_record(rec.release_id)
    assert found is not None
    assert found.release_id == rec.release_id

    records = list_release_gate_records()
    assert len(records) == 1
