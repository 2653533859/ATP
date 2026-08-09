import pytest

from app.services.api_scenario import ApiScenarioError, build_api_scenario_policy, step_dependencies


def test_policy_defaults_keep_legacy_api_behavior():
    policy = build_api_scenario_policy({})
    assert policy.failure_strategy == "continue"
    assert policy.context_scope == "scenario"
    assert policy.session_lifecycle == "isolated"


def test_legacy_reuse_flag_maps_to_session_lifecycle():
    assert build_api_scenario_policy({"reuse_api_session": True}).session_lifecycle == "reuse"


def test_legacy_reuse_flag_wins_over_default_isolated_lifecycle():
    assert (
        build_api_scenario_policy({"reuse_api_session": True, "session_lifecycle": "isolated"}).session_lifecycle
        == "reuse"
    )


def test_step_dependencies_only_allow_previous_steps_and_deduplicate():
    assert step_dependencies({"depends_on": [0, "0", 1]}, 2) == [0, 1]
    with pytest.raises(ApiScenarioError, match="更早"):
        step_dependencies({"depends_on": [2]}, 2)


@pytest.mark.parametrize(
    "config",
    [
        {"failure_strategy": "unknown"},
        {"context_scope": "request"},
        {"session_lifecycle": "global"},
    ],
)
def test_policy_rejects_unknown_values(config):
    with pytest.raises(ApiScenarioError):
        build_api_scenario_policy(config)
