"""Unit tests for API scenario template snapshot, conflict-aware diff, and batch sync."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.api_scenario_sync import (
    apply_step_sync,
    build_case_sync_metadata,
    compute_step_sync_diff,
)


def _mock_case(**cfg):
    return SimpleNamespace(id=10, name="创建订单", config=cfg)


def test_auto_syncable_when_only_source_case_changed():
    v1_case = _mock_case(
        method="POST", url="/api/v1/orders", params={"channel": "web"}, body_type="json", body={"a": 1}
    )
    snap_v1, fp_v1 = build_case_sync_metadata(v1_case)

    step = {
        "uid": "s1",
        "sourceCaseId": 10,
        "sourceCaseFingerprint": fp_v1,
        "sourceSnapshot": snap_v1,
        **snap_v1,
    }

    # Source case updates url & body
    v2_case = _mock_case(
        method="POST", url="/api/v2/orders", params={"channel": "web"}, body_type="json", body={"a": 1, "b": 2}
    )
    snap_v2, fp_v2 = build_case_sync_metadata(v2_case)

    diff = compute_step_sync_diff(step, snap_v2, fp_v2)
    assert diff["sync_status"] == "stale_auto_syncable"
    assert diff["conflicts"] == []
    assert {u["field"] for u in diff["auto_updates"]} == {"url", "body"}

    updated, unresolved = apply_step_sync(step, snap_v2, fp_v2)
    assert unresolved == []
    assert updated["url"] == "/api/v2/orders"
    assert updated["body"] == {"a": 1, "b": 2}
    assert updated["sourceCaseFingerprint"] == fp_v2


def test_conflict_detected_when_both_local_step_and_source_case_changed_and_no_deep_merge():
    v1_case = _mock_case(method="POST", url="/api/v1/orders", body_type="json", body={"a": 1, "drop_me": True})
    snap_v1, fp_v1 = build_case_sync_metadata(v1_case)

    # Local step explicitly deleted "drop_me" from body
    step = {
        "uid": "s1",
        "sourceCaseId": 10,
        "sourceCaseFingerprint": fp_v1,
        "sourceSnapshot": snap_v1,
        **snap_v1,
        "body": {"a": 1},
    }

    # Source case also modified body
    v2_case = _mock_case(method="POST", url="/api/v1/orders", body_type="json", body={"a": 2, "drop_me": True, "c": 3})
    snap_v2, fp_v2 = build_case_sync_metadata(v2_case)

    diff = compute_step_sync_diff(step, snap_v2, fp_v2)
    assert diff["sync_status"] == "conflict"
    assert [c["field"] for c in diff["conflicts"]] == ["body"]

    # Refuses silent overwrite when choices missing
    untouched, unresolved = apply_step_sync(step, snap_v2, fp_v2, choices={})
    assert len(unresolved) == 1
    assert untouched["body"] == {"a": 1}

    # Explicit keep_local preserves deleted key (no deep merge resurrection)
    kept, unresolved2 = apply_step_sync(step, snap_v2, fp_v2, choices={"body": "keep_local"})
    assert unresolved2 == []
    assert kept["body"] == {"a": 1}
    assert "drop_me" not in kept["body"]
    assert "body" in kept["overriddenFields"]

    # Explicit use_latest adopts latest whole body
    adopted, unresolved3 = apply_step_sync(step, snap_v2, fp_v2, choices={"body": "use_latest"})
    assert unresolved3 == []
    assert adopted["body"] == {"a": 2, "drop_me": True, "c": 3}


def test_batch_sync_multiple_steps_same_scenario_without_self_version_conflict(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    from app.api.v1 import api_scenarios
    from app.api.v1.api_scenarios import ScenarioSyncApplyIn, ScenarioSyncApplyItemIn

    v1 = _mock_case(method="GET", url="/v1/item")
    snap_v1, fp_v1 = build_case_sync_metadata(v1)
    v2 = _mock_case(method="GET", url="/v2/item")

    stored = [
        {
            "id": 1,
            "project_id": 1,
            "version": 3,
            "steps": [
                {"uid": "s1", "sourceCaseId": 10, "sourceCaseFingerprint": fp_v1, "sourceSnapshot": snap_v1, **snap_v1},
                {"uid": "s2", "sourceCaseId": 10, "sourceCaseFingerprint": fp_v1, "sourceSnapshot": snap_v1, **snap_v1},
            ],
        }
    ]
    monkeypatch.setattr(api_scenarios, "_load_source_api_case", AsyncMock(return_value=(v2, 1)))
    monkeypatch.setattr(api_scenarios, "_load_all", lambda: stored)
    monkeypatch.setattr(api_scenarios, "_save_all", lambda items: stored.__setitem__(0, items[0]))

    res = asyncio.run(
        api_scenarios.apply_source_case_sync_batch(
            case_id=10,
            body=ScenarioSyncApplyIn(
                items=[
                    ScenarioSyncApplyItemIn(scenario_id=1, scenario_version=3, step_uid="s1"),
                    ScenarioSyncApplyItemIn(scenario_id=1, scenario_version=3, step_uid="s2"),
                ]
            ),
            current_user=SimpleNamespace(id=1),
            db=AsyncMock(),
        )
    )
    assert res["applied"] == 2
    assert res["failed"] == 0
    assert stored[0]["version"] == 4
    assert stored[0]["steps"][0]["url"] == "/v2/item"
    assert stored[0]["steps"][1]["url"] == "/v2/item"
