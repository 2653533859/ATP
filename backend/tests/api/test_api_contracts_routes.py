import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from app.api.v1 import api_contracts

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
