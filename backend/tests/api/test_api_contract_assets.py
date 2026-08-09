"""Tests for project-scoped Provider/Consumer contract assets."""

import asyncio
import types

import pytest

from app.api.v1 import api_contract_assets, api_contracts
from app.models import load_all_models
from app.models.api_contract_asset import ApiContractAsset
from app.schemas.api_contract_asset import ApiContractAssetCompareIn, ApiContractAssetCreate, ApiContractAssetUpdate

load_all_models()


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _DB:
    def __init__(self, *, objects=None, rows=None):
        self.objects = dict(objects or {})
        self.rows = list(rows or [])
        self.items = []
        self.commits = 0

    async def get(self, model, key):
        return self.objects.get((model.__name__, key))

    async def execute(self, _query):
        return _Result(self.rows)

    def add(self, item):
        item.id = len(self.items) + 1
        self.items.append(item)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None

    async def refresh(self, _item):
        return None

    async def delete(self, _item):
        return None


def _allow_access(monkeypatch):
    async def fake_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(api_contract_assets, "assert_project_access", fake_access)


def test_contract_asset_crud_is_project_scoped(monkeypatch):
    _allow_access(monkeypatch)
    db = _DB(objects={("Project", 1): types.SimpleNamespace(id=1)})
    user = types.SimpleNamespace(id=8)
    created = asyncio.run(
        api_contract_assets.create_api_contract_asset(
            1,
            ApiContractAssetCreate(
                name="orders-provider",
                role="provider",
                format="openapi",
                definition={"openapi": "3.0.0", "paths": {}},
            ),
            db,
            user,
        )
    )
    assert created.project_id == 1
    assert created.owner_id == 8
    assert created.role == "provider"
    created.version = 1

    db.objects[("ApiContractAsset", 1)] = created
    asyncio.run(
        api_contract_assets.update_api_contract_asset(
            1,
            ApiContractAssetUpdate(definition={"openapi": "3.0.0", "paths": {"/orders": {}}}),
            db,
            user,
        )
    )
    assert created.version == 2


def test_contract_asset_definition_is_bounded():
    with pytest.raises(ValueError):
        ApiContractAssetCreate(
            name="too-large",
            role="consumer",
            format="json_schema",
            definition={"value": "x" * (2 * 1024 * 1024)},
        )


def test_compare_saved_contract_assets_rejects_foreign_project(monkeypatch):
    calls = []

    async def fake_access(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(api_contracts, "assert_project_access", fake_access)
    baseline = ApiContractAsset(id=1, project_id=1, name="provider", role="provider", format="openapi", definition={})
    current = ApiContractAsset(id=2, project_id=2, name="consumer", role="consumer", format="openapi", definition={})
    db = _DB(objects={("ApiContractAsset", 1): baseline, ("ApiContractAsset", 2): current})

    with pytest.raises(api_contracts.HTTPException) as error:
        asyncio.run(
            api_contracts.compare_api_contract_assets(
                1, ApiContractAssetCompareIn(baseline_asset_id=1, current_asset_id=2), db, types.SimpleNamespace(id=8)
            )
        )

    assert error.value.status_code == 404
    assert calls
