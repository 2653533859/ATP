import asyncio
import sys
import types
from types import SimpleNamespace

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

from app.api.v1 import web_assets
from app.models.bootstrap import load_all_models
from app.models.web_assets import WebElementAsset, WebPageObject
from app.schemas.web_assets import WebElementAssetCreate, WebElementAssetUpdate, WebElementFailureIn, WebLocatorRepairIn

load_all_models()


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _DB:
    def __init__(self, *, rows=None, objects=None):
        self.rows = list(rows or [])
        self.objects = dict(objects or {})
        self.commits = 0
        self.deleted = []

    async def get(self, model, key):
        return self.objects.get((model.__name__, key))

    async def execute(self, _query):
        return _Result(self.rows.pop(0) if self.rows else [])

    def add(self, _item):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None

    async def refresh(self, _item):
        return None

    async def delete(self, item):
        self.deleted.append(item)


def _allow_access(monkeypatch):
    async def fake_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(web_assets, "assert_project_access", fake_access)


def test_create_element_is_project_scoped(monkeypatch):
    _allow_access(monkeypatch)
    db = _DB(objects={("Project", 1): SimpleNamespace(id=1)})
    user = SimpleNamespace(id=8)

    result = asyncio.run(
        web_assets.create_web_element(
            1,
            WebElementAssetCreate(name="login_button", locator={"strategy": "role", "value": "button"}),
            db,
            user,
        )
    )

    assert result.project_id == 1
    assert result.owner_id == 8
    assert result.locator["strategy"] == "role"


def test_element_update_increments_version_and_records_failure(monkeypatch):
    _allow_access(monkeypatch)
    element = WebElementAsset(
        id=4,
        project_id=1,
        name="submit",
        locator={"strategy": "css", "value": "#submit"},
        fallback_locators=[],
        version=2,
    )
    db = _DB(objects={("WebElementAsset", 4): element, ("Project", 1): SimpleNamespace(id=1)})
    user = SimpleNamespace(id=8)

    asyncio.run(
        web_assets.update_web_element(4, WebElementAssetUpdate(locator={"strategy": "text", "value": "提交"}), db, user)
    )
    asyncio.run(web_assets.record_web_element_failure(4, WebElementFailureIn(reason="定位器失效"), db, user))

    assert element.version == 3
    assert element.locator["strategy"] == "text"
    assert element.last_failure_reason == "定位器失效"


def test_delete_page_object_is_project_scoped(monkeypatch):
    _allow_access(monkeypatch)
    page_object = WebPageObject(id=3, project_id=1, name="LoginPage", element_refs=[], actions=[])
    db = _DB(objects={("WebPageObject", 3): page_object, ("Project", 1): SimpleNamespace(id=1)})

    asyncio.run(web_assets.delete_web_page_object(3, db, SimpleNamespace(id=8)))

    assert db.deleted == [page_object]
    assert db.commits == 1


def test_repair_preview_returns_candidates_without_mutating_asset(monkeypatch):
    _allow_access(monkeypatch)
    element = WebElementAsset(
        id=5,
        project_id=1,
        name="submit",
        locator={"strategy": "role", "value": "button", "name": "Submit"},
        fallback_locators=[{"strategy": "text", "value": "Submit"}],
    )
    db = _DB(objects={("WebElementAsset", 5): element, ("Project", 1): SimpleNamespace(id=1)})

    result = asyncio.run(
        web_assets.preview_web_element_repair(
            5,
            WebLocatorRepairIn(observed_locators=[{"strategy": "test_id", "value": "submit-button"}]),
            db,
            SimpleNamespace(id=8),
        )
    )

    assert result.element_id == 5
    assert result.candidates
    assert any(item.locator["strategy"] == "test_id" for item in result.candidates)
    assert element.locator["strategy"] == "role"
    assert db.commits == 0
