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


def test_api_scenario_atomic_save_and_corrupt_handling(tmp_path, monkeypatch):
    import app.api.v1.api_scenarios as scn_mod

    store_file = tmp_path / "api_scenarios.json"
    monkeypatch.setattr(scn_mod, "_store_path", lambda: store_file)

    assert scn_mod._load_all() == []

    test_data = [{"id": 1, "scenario_code": "SCN-0001", "name": "测试场景", "project_id": 99}]
    scn_mod._save_all(test_data)
    assert scn_mod._load_all() == test_data

    # 写入损坏数据，验证捕获并备份
    store_file.write_text("invalid json {{{", encoding="utf-8")
    assert scn_mod._load_all() == []
    assert (tmp_path / "api_scenarios.corrupted").exists()
