import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import api_contracts
from app.api.v1 import api_scenarios

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class _DB:
    pass


def test_compare_api_contracts_checks_project_access(monkeypatch):
    calls = {}

    async def fake_access(db, user, project_id, role):
        calls.update(db=db, user=user, project_id=project_id, role=role)

    monkeypatch.setattr(api_contracts, "assert_project_access", fake_access)
    body = api_contracts.ApiContractCompareIn(baseline={"type": "object"}, current={"type": "object"})
    user = SimpleNamespace(id=9)

    result = asyncio.run(api_contracts.compare_api_contracts(7, body, _DB(), user))

    assert result["compatible"] is True
    assert calls["project_id"] == 7


def test_scenario_impact_snapshot_is_project_scoped_and_read_only(monkeypatch, tmp_path):
    monkeypatch.setattr(type(api_scenarios.settings), "LOCAL_DATA_PATH", property(lambda _self: tmp_path))
    path = tmp_path / "api_scenarios.json"
    raw = [
        {"id": 1, "project_id": 7, "steps": [{"method": "GET", "url": "/orders"}]},
        {"id": 2, "project_id": 8, "steps": []},
    ]
    path.write_text(json.dumps(raw), encoding="utf-8")

    assert api_scenarios.read_project_scenarios_snapshot(7) == [raw[0]]
    assert json.loads(path.read_text(encoding="utf-8")) == raw

    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        api_scenarios.read_project_scenarios_snapshot(7)
    assert exc.value.status_code == 503
    assert path.read_text(encoding="utf-8") == "{broken"
