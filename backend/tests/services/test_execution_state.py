from app.models.case import RunStatus
from app.models.mobile_special import RunStatus as MobileRunStatus
from app.models.performance import PerformanceRunStatus
from app.models.plan import PlanRunStatus
from app.models.suite import SuiteRunStatus
from app.services.execution_state import (
    EXECUTION_STATE_POLICIES,
    can_execute_action,
    decide_execution_action,
    execution_action_rejection_detail,
)


def test_policy_statuses_match_persisted_domain_enums():
    enum_statuses = {
        "case": {status.value for status in RunStatus},
        "suite": {status.value for status in SuiteRunStatus},
        "plan": {status.value for status in PlanRunStatus},
        "android": {status.value for status in MobileRunStatus},
        "performance": {status.value for status in PerformanceRunStatus},
    }

    assert {domain: set(policy.statuses) for domain, policy in EXECUTION_STATE_POLICIES.items()} == enum_statuses


def test_action_availability_preserves_each_domain_contract():
    assert can_execute_action("case", "failed", "retry") is True
    assert can_execute_action("suite", "error", "retry") is True
    assert can_execute_action("plan", "passed", "retry") is False
    assert can_execute_action("android", "stopped", "retry") is True
    assert can_execute_action("android", "running", "stop") is True
    assert can_execute_action("performance", "cancelled", "retry") is True
    assert can_execute_action("performance", "cancelling", "stop") is False


def test_action_decision_distinguishes_unknown_unsupported_and_disallowed_states():
    assert decide_execution_action("case", "missing", "retry").rejection_code == "unknown_status"
    assert decide_execution_action("case", "running", "stop").rejection_code == "unsupported_action"
    assert decide_execution_action("android", "completed", "stop").rejection_code == "status_not_allowed"
    assert decide_execution_action("performance", "failed", "retry").rejection_code is None

    detail = execution_action_rejection_detail("android", "completed", "stop")
    assert detail == "android 任务当前状态为 completed：当前状态不支持停止"


def test_policy_partitions_active_and_terminal_states():
    for policy in EXECUTION_STATE_POLICIES.values():
        assert policy.active.isdisjoint(policy.terminal)
        assert policy.active | policy.terminal == policy.statuses
        assert policy.failed <= policy.terminal
        assert policy.retryable <= policy.terminal
        assert policy.stoppable <= policy.active
