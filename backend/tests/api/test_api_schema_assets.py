import asyncio
import sys
import types

import pytest

_deps = sys.modules.setdefault("app.api.deps", types.SimpleNamespace())


async def _noop_async(*_args, **_kwargs):
    return None


for _name, _value in (
    ("get_current_user", lambda: None),
    ("require_engineer", lambda: None),
    ("assert_project_access", _noop_async),
):
    if not hasattr(_deps, _name):
        setattr(_deps, _name, _value)

from app.api.v1 import api_schema_assets  # noqa: E402
from app.models.api_schema import ApiSchemaAsset  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.schemas.api_schema import ApiSchemaAssetCreate, ApiSchemaAssetUpdate  # noqa: E402
from app.worker.executors.api_executor import _resolve_schema_assertions  # noqa: E402


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

    monkeypatch.setattr(api_schema_assets, "assert_project_access", fake_access)


def test_schema_asset_crud_is_project_scoped(monkeypatch):
    _allow_access(monkeypatch)
    db = _DB(objects={("Project", 1): types.SimpleNamespace(id=1)})
    user = types.SimpleNamespace(id=8)
    created = asyncio.run(
        api_schema_assets.create_api_schema_asset(
            1,
            ApiSchemaAssetCreate(name="UserResponse", definition={"type": "object", "required": ["id"]}),
            db,
            user,
        )
    )
    assert created.project_id == 1
    assert created.owner_id == 8
    assert created.definition["required"] == ["id"]
    created.version = 1

    db.objects[("ApiSchemaAsset", 1)] = created
    asyncio.run(
        api_schema_assets.update_api_schema_asset(
            1,
            ApiSchemaAssetUpdate(definition={"type": "object", "required": ["id", "name"]}),
            db,
            user,
        )
    )
    assert created.version == 2
    assert created.definition["required"] == ["id", "name"]


def test_schema_asset_definition_is_bounded():
    with pytest.raises(ValueError):
        ApiSchemaAssetCreate(name="too-large", definition={"value": "x" * (512 * 1024)})


def test_executor_resolves_schema_asset_and_rejects_foreign_asset():
    asset = ApiSchemaAsset(id=7, project_id=1, name="UserResponse", definition={"type": "object"}, version=1)
    db = _DB(objects={("ApiSchemaAsset", 7): asset})
    resolved = asyncio.run(
        _resolve_schema_assertions(db, [{"target": "json_schema", "schema_asset_id": 7}], project_id=1)
    )
    assert resolved[0]["schema"] == {"type": "object"}

    with pytest.raises(ValueError, match="不属于当前项目"):
        asyncio.run(_resolve_schema_assertions(db, [{"schema_asset_id": 7}], project_id=2))
