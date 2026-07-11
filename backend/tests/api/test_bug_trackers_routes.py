"""bug_trackers API 路由单元测试（Q13 补覆盖：此前 55%）。

聚焦 CRUD 的密钥加密/掩码编排与 _merge_sensitive_config（更新时保留未变更的密钥）、
以及 test-connection 的类型不匹配守卫与错误吞。encrypt/decrypt/mask/审计按测试注入。
"""

import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


async def _noop_async(*_a, **_kw):
    return None


_deps = sys.modules.setdefault("app.api.deps", types.SimpleNamespace())
for _name, _value in (
    ("get_current_user", lambda: None),
    ("require_engineer", lambda: None),
    ("assert_project_access", _noop_async),
):
    if not hasattr(_deps, _name):
        setattr(_deps, _name, _value)

from fastapi import HTTPException  # noqa: E402

from app.api.v1 import bug_trackers as bt  # noqa: E402
from app.models.bootstrap import load_all_models  # noqa: E402

load_all_models()

from app.models.bug_tracker import TrackerType  # noqa: E402
from app.models.user_project import ProjectRole  # noqa: E402
from app.schemas.bug_tracker import (  # noqa: E402
    BugTrackerConnectionTestRequest,
    BugTrackerCreate,
    BugTrackerUpdate,
)


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeResult:
    def __init__(self, rows=None):
        self._rows = rows or []

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, objects=None, execute_results=None):
        self.objects = dict(objects or {})
        self.execute_results = list(execute_results or [])
        self.added = []
        self.deleted = []
        self.commits = 0

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    def add(self, obj):
        if not getattr(obj, "id", None):
            obj.id = 700
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.commits += 1

    async def execute(self, _query):
        return self.execute_results.pop(0) if self.execute_results else _FakeResult()

    async def refresh(self, obj):
        now = _now()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now


def _now():
    return datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def stub_crypto_and_audit(monkeypatch):
    # 加密=包一层 enc()，解密=去一层，掩码=敏感键→******，验证 route 的编排
    monkeypatch.setattr(bt, "encrypt_config", lambda cfg: {**cfg, "_enc": True})
    monkeypatch.setattr(bt, "decrypt_config", lambda cfg: {k: v for k, v in cfg.items() if k != "_enc"})
    monkeypatch.setattr(bt, "mask_config", lambda cfg: {**cfg, "api_token": "******"} if cfg.get("api_token") else cfg)
    monkeypatch.setattr(bt, "write_audit_log", _noop_async)
    monkeypatch.setattr(bt, "assert_project_access", _noop_async)


def _user(uid=9):
    return _Obj(id=uid, username="amy")


def _tracker(tid=1, project_id=5, ttype=TrackerType.jira, config=None):
    return _Obj(
        id=tid,
        name="Jira",
        project_id=project_id,
        tracker_type=ttype,
        config=config if config is not None else {"base_url": "https://j", "api_token": "enc-tok", "_enc": True},
        field_mapping={},
        is_enabled=True,
        created_at=_now(),
        updated_at=_now(),
    )


# ── _merge_sensitive_config（纯逻辑，核心不变量）─────────────


def test_merge_sensitive_config_preserves_secrets_when_masked_or_omitted():
    existing = {"base_url": "https://j", "api_token": "real-token", "password": "pw"}

    # 掩码值 ****** → 保留旧密钥；未提供的字段也保留
    merged = bt._merge_sensitive_config(existing, {"base_url": "https://new", "api_token": "******"})
    assert merged["api_token"] == "real-token"  # 未被 ****** 覆盖
    assert merged["password"] == "pw"  # 未提供 → 保留
    assert merged["base_url"] == "https://new"  # 普通字段更新


def test_merge_sensitive_config_accepts_new_secret():
    existing = {"api_token": "old"}
    merged = bt._merge_sensitive_config(existing, {"api_token": "brand-new"})
    assert merged["api_token"] == "brand-new"


# ── CRUD 编排 ───────────────────────────────────────────────


def test_create_bug_tracker_encrypts_config_and_masks_output():
    project = _Obj(id=5)
    db = _FakeDB({("Project", 5): project})
    body = BugTrackerCreate(
        name="Jira", project_id=5, tracker_type=TrackerType.jira, config={"base_url": "https://j", "api_token": "tok"}
    )

    out = asyncio.run(bt.create_bug_tracker(body=body, db=db, user=_user()))

    created = db.added[0]
    assert created.config["_enc"] is True  # 落库前加密
    assert out["config"]["api_token"] == "******"  # 返回掩码
    assert db.commits == 2  # 创建 + 审计


def test_create_bug_tracker_404_when_project_missing():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            bt.create_bug_tracker(
                body=BugTrackerCreate(name="x", project_id=404, tracker_type=TrackerType.jira),
                db=_FakeDB(),
                user=_user(),
            )
        )
    assert exc.value.status_code == 404


def test_list_bug_trackers_masks_each():
    db = _FakeDB(execute_results=[_FakeResult(rows=[_tracker()])])
    out = asyncio.run(bt.list_bug_trackers(project_id=5, db=db, user=_user()))
    assert out[0]["config"]["api_token"] == "******"


def test_get_bug_tracker_masks_and_404():
    db = _FakeDB({("BugTracker", 1): _tracker()})
    assert asyncio.run(bt.get_bug_tracker(tracker_id=1, db=db, user=_user()))["config"]["api_token"] == "******"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(bt.get_bug_tracker(tracker_id=404, db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404


def test_update_bug_tracker_preserves_masked_secret():
    tracker = _tracker(config={"base_url": "https://j", "api_token": "real-token"})
    db = _FakeDB({("BugTracker", 1): tracker})
    # 用户改 base_url，api_token 传 ****** → 应保留原密钥
    body = BugTrackerUpdate(config={"base_url": "https://new", "api_token": "******"})

    asyncio.run(bt.update_bug_tracker(tracker_id=1, body=body, db=db, user=_user()))

    # tracker.config 被重新加密（含 _enc），且 api_token 仍是原值（合并保留）
    assert tracker.config["_enc"] is True
    assert tracker.config["api_token"] == "real-token"
    assert tracker.config["base_url"] == "https://new"


def test_update_bug_tracker_404():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(bt.update_bug_tracker(tracker_id=404, body=BugTrackerUpdate(name="x"), db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404


def test_delete_bug_tracker_removes_and_404():
    tracker = _tracker()
    db = _FakeDB({("BugTracker", 1): tracker})
    asyncio.run(bt.delete_bug_tracker(tracker_id=1, db=db, user=_user()))
    assert db.deleted == [tracker]

    with pytest.raises(HTTPException):
        asyncio.run(bt.delete_bug_tracker(tracker_id=404, db=_FakeDB(), user=_user()))


# ── test-connection ─────────────────────────────────────────


def test_connection_with_inline_config(monkeypatch):
    async def fake_test(ttype, config):
        return {"ok": True, "message": f"connected {ttype}"}

    monkeypatch.setattr(bt, "test_connection", fake_test)
    body = BugTrackerConnectionTestRequest(tracker_type=TrackerType.github, config={"owner": "acme"})

    out = asyncio.run(bt.test_bug_tracker_connection(body=body, db=_FakeDB()))

    assert out.ok is True and "github" in out.message


def test_connection_merges_saved_tracker_secrets(monkeypatch):
    captured = {}

    async def fake_test(ttype, config):
        captured["config"] = config
        return {"ok": True, "message": "ok"}

    monkeypatch.setattr(bt, "test_connection", fake_test)
    tracker = _tracker(config={"base_url": "https://j", "api_token": "saved-tok"})
    db = _FakeDB({("BugTracker", 1): tracker})
    # 只传 base_url + 掩码 token → 应合并出 saved-tok
    body = BugTrackerConnectionTestRequest(
        tracker_id=1, tracker_type=TrackerType.jira, config={"base_url": "https://j", "api_token": "******"}
    )

    asyncio.run(bt.test_bug_tracker_connection(body=body, db=db))

    assert captured["config"]["api_token"] == "saved-tok"


def test_connection_rejects_type_mismatch_gracefully(monkeypatch):
    tracker = _tracker(ttype=TrackerType.jira)
    db = _FakeDB({("BugTracker", 1): tracker})
    body = BugTrackerConnectionTestRequest(tracker_id=1, tracker_type=TrackerType.github, config={})

    # HTTPException 被捕获转成 ok=False，而非抛出
    out = asyncio.run(bt.test_bug_tracker_connection(body=body, db=db))

    assert out.ok is False and "类型不匹配" in out.message


def test_connection_swallows_backend_errors(monkeypatch):
    async def broken(_t, _c):
        raise RuntimeError("network down")

    monkeypatch.setattr(bt, "test_connection", broken)
    body = BugTrackerConnectionTestRequest(tracker_type=TrackerType.jira, config={})

    out = asyncio.run(bt.test_bug_tracker_connection(body=body, db=_FakeDB()))

    assert out.ok is False and "network down" in out.message
