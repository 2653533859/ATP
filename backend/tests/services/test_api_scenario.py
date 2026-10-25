import pytest
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.models.case import CaseType, TestCase
from app.models.bootstrap import load_all_models
from app.api.v1.api_scenarios import _bind_source_cases

from app.services.api_scenario import ApiScenarioError, build_api_scenario_policy, step_dependencies

load_all_models()


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


def test_source_case_binding_captures_and_preserves_import_fingerprint():
    source = TestCase(id=11, module_id=4, case_type=CaseType.api, config={"method": "GET", "url": "/orders"})

    class _DB:
        async def execute(self, _statement):
            class _Result:
                def scalars(self):
                    return self

                def all(self):
                    return [source]

            return _Result()

    step = {"method": "GET", "url": "/orders", "sourceCaseId": 11}
    bound = asyncio.run(_bind_source_cases(_DB(), 7, [step]))
    fingerprint = bound[0]["sourceCaseFingerprint"]
    assert len(fingerprint) == 64
    assert "sourceCaseFingerprint" not in step

    source.config = {"method": "GET", "url": "/orders-v2"}
    rebound = asyncio.run(_bind_source_cases(_DB(), 7, bound, preserve_existing=True))
    assert rebound[0]["sourceCaseFingerprint"] == fingerprint

    fresh = asyncio.run(_bind_source_cases(_DB(), 7, bound))
    assert fresh[0]["sourceCaseFingerprint"] != fingerprint


def test_scenario_create_and_update_persist_source_binding(tmp_path, monkeypatch):
    import app.api.v1.api_scenarios as scenarios

    source = TestCase(id=11, module_id=4, case_type=CaseType.api, config={"method": "GET", "url": "/orders"})

    class _DB:
        async def execute(self, _statement):
            class _Result:
                def scalars(self):
                    return self

                def all(self):
                    return [source]

            return _Result()

    monkeypatch.setattr(scenarios, "_store_path", lambda: tmp_path / "api_scenarios.json")
    monkeypatch.setattr(scenarios, "assert_project_access", AsyncMock())
    db = _DB()
    user = SimpleNamespace(id=1)
    body = scenarios.ApiScenarioSaveIn(
        project_id=7, name="订单场景", steps=[{"method": "GET", "url": "/orders", "sourceCaseId": 11}]
    )
    created = asyncio.run(scenarios.create_api_scenario(body, user, db))
    fingerprint = created["steps"][0]["sourceCaseFingerprint"]

    source.config = {"method": "GET", "url": "/orders-v2"}
    updated_body = scenarios.ApiScenarioSaveIn(project_id=7, name="订单场景", steps=created["steps"])
    updated = asyncio.run(scenarios.update_api_scenario(created["id"], updated_body, user, db))
    assert updated["steps"][0]["sourceCaseFingerprint"] == fingerprint
    assert scenarios._load_all()[0]["steps"][0]["sourceCaseFingerprint"] == fingerprint
