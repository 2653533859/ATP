"""ai_healing iter5 phase 2 apply-loop 行为测试。

直接驱动路由函数：validate_lowcode_patch 走真实现（白名单校验+preview 生成），
_cases 的快照/落库/审计 helper 与回归触发按测试注入，AI_HEALING_APPLY_ENABLED
feature flag 的开关语义为核心断言。
"""

import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


async def _noop_async(*_a, **_kw):
    return None


# conftest 的 app.api.deps stub 缺 assert_project_access；只补缺失字段
_deps = sys.modules.setdefault("app.api.deps", types.SimpleNamespace())
for _name, _value in (
    ("get_current_user", lambda: None),
    ("require_engineer", lambda: None),
    ("require_admin", lambda: None),
    ("assert_project_access", _noop_async),
):
    if not hasattr(_deps, _name):
        setattr(_deps, _name, _value)

from fastapi import HTTPException  # noqa: E402

from app.api.v1 import ai_healing_iter5 as iter5  # noqa: E402
from app.models.bootstrap import load_all_models  # noqa: E402

load_all_models()

from app.schemas.ai_healing_iter5 import (  # noqa: E402
    HealingPatchApplyRequest,
    StructuredHealingPatchIn,
    StructuredHealingSuggestionIn,
)


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeDB:
    def __init__(self, objects=None):
        self.objects = dict(objects or {})
        self.added = []
        self.commits = 0

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        if not getattr(obj, "id", None):
            obj.id = 7777


def _web_case(case_id=1, module_id=2):
    return _Obj(
        id=case_id,
        module_id=module_id,
        name="登录流程",
        case_type=types.SimpleNamespace(value="web"),
        config={"steps": [{"action": "click", "params": {"selector": "#old"}}]},
    )


def _apply_body(**overrides):
    values = dict(
        case_id=1,
        suggestion=StructuredHealingSuggestionIn(
            root_cause="selector changed",
            confidence=0.9,
            patch=StructuredHealingPatchIn(
                case_type="web",
                step_index=0,
                action="click",
                params={"selector": "button[type=submit]"},
            ),
        ),
    )
    values.update(overrides)
    return HealingPatchApplyRequest(**values)


@pytest.fixture()
def apply_seam(monkeypatch):
    """注入 _cases 的快照/落库/审计 helper 与回归触发，隔离真实 DB 写。"""
    calls = {"snapshot": [], "audit": [], "replace_steps": [], "regression": []}

    async def next_snapshot_version(_db, case_id):
        return 5

    def build_snapshot(case, version, user_id):
        calls["snapshot"].append((case.id, version, user_id))
        return _Obj(case_id=case.id, version=version)

    async def enforce_retention(_db, _case_id):
        return 0

    async def replace_case_steps(_db, case, steps):
        calls["replace_steps"].append(case.id)

    def normalize_steps(_body, _case_type, _config, _name):
        return []

    async def write_audit_log(_db, **kwargs):
        calls["audit"].append(kwargs)

    async def invalidate_stats_cache():
        return None

    monkeypatch.setattr(iter5._cases, "_next_snapshot_version", next_snapshot_version)
    monkeypatch.setattr(iter5._cases, "_build_snapshot", build_snapshot)
    monkeypatch.setattr(iter5._cases, "_enforce_snapshot_retention", enforce_retention)
    monkeypatch.setattr(iter5._cases, "_replace_case_steps", replace_case_steps)
    monkeypatch.setattr(iter5._cases, "_normalize_steps", normalize_steps)
    monkeypatch.setattr(iter5._cases, "write_audit_log", write_audit_log)
    monkeypatch.setattr(iter5._cases, "invalidate_stats_cache", invalidate_stats_cache)

    async def trigger_regression(_db, case, _user, _body, _patch):
        calls["regression"].append(case.id)
        return 909

    monkeypatch.setattr(iter5, "_trigger_regression_run", trigger_regression)
    return calls


def _run(coro):
    return asyncio.run(coro)


# ── feature flag 门禁 ───────────────────────────────────────


def test_apply_is_forbidden_when_flag_disabled(monkeypatch, apply_seam):
    monkeypatch.setattr(iter5.settings, "AI_HEALING_APPLY_ENABLED", False)
    db = _FakeDB({("TestCase", 1): _web_case(), ("Module", 2): _Obj(id=2, project_id=3)})

    with pytest.raises(HTTPException) as exc:
        _run(iter5.apply_healing_patch(body=_apply_body(), db=db, user=_Obj(id=9, username="qa")))

    assert exc.value.status_code == 403
    # 门禁在任何写操作之前：无快照、无 commit
    assert db.commits == 0 and apply_seam["snapshot"] == []


def test_apply_flag_defaults_off():
    from app.core.config import Settings

    assert Settings().AI_HEALING_APPLY_ENABLED is False


# ── 启用后的正常闭环 ────────────────────────────────────────


def test_apply_snapshots_audits_and_writes_when_enabled(monkeypatch, apply_seam):
    monkeypatch.setattr(iter5.settings, "AI_HEALING_APPLY_ENABLED", True)
    case = _web_case()
    db = _FakeDB({("TestCase", 1): case, ("Module", 2): _Obj(id=2, project_id=3)})

    out = _run(iter5.apply_healing_patch(body=_apply_body(), db=db, user=_Obj(id=9, username="qa")))

    assert out.accepted is True
    assert out.snapshot_version == 5
    assert out.normalized_patch["params"]["selector"] == "button[type=submit]"
    # 快照在写之前建立，审计记录写入，case.config 被更新
    assert apply_seam["snapshot"] == [(1, 5, 9)]
    assert apply_seam["audit"][0]["action"] == "ai_healing_patch_apply"
    assert case.config["steps"][0]["params"]["selector"] == "button[type=submit]"
    assert out.regression_run_id is None  # 未请求回归


def test_apply_triggers_regression_when_requested(monkeypatch, apply_seam):
    monkeypatch.setattr(iter5.settings, "AI_HEALING_APPLY_ENABLED", True)
    db = _FakeDB({("TestCase", 1): _web_case(), ("Module", 2): _Obj(id=2, project_id=3)})

    out = _run(
        iter5.apply_healing_patch(
            body=_apply_body(trigger_regression=True, source_run_id=100, source_step_id=200),
            db=db,
            user=_Obj(id=9, username="qa"),
        )
    )

    assert out.regression_run_id == 909
    assert apply_seam["regression"] == [1]


def test_apply_rejects_patch_failing_whitelist_without_writing(monkeypatch, apply_seam):
    monkeypatch.setattr(iter5.settings, "AI_HEALING_APPLY_ENABLED", True)
    db = _FakeDB({("TestCase", 1): _web_case(), ("Module", 2): _Obj(id=2, project_id=3)})
    # 敏感字段不在白名单 → 校验拒绝
    bad = _apply_body(
        suggestion=StructuredHealingSuggestionIn(
            root_cause="x",
            confidence=0.5,
            patch=StructuredHealingPatchIn(
                case_type="web", step_index=0, action="click", params={"authorization": "Bearer x"}
            ),
        )
    )

    out = _run(iter5.apply_healing_patch(body=bad, db=db, user=_Obj(id=9, username="qa")))

    assert out.accepted is False and out.reasons
    # 拒绝路径不建快照、不 commit
    assert apply_seam["snapshot"] == [] and db.commits == 0


def test_apply_404_when_case_missing(monkeypatch, apply_seam):
    monkeypatch.setattr(iter5.settings, "AI_HEALING_APPLY_ENABLED", True)
    with pytest.raises(HTTPException) as exc:
        _run(iter5.apply_healing_patch(body=_apply_body(case_id=404), db=_FakeDB(), user=_Obj(id=9)))
    assert exc.value.status_code == 404


# ── 只读 preview 不受 flag 影响 ─────────────────────────────


def test_preview_is_open_regardless_of_apply_flag(monkeypatch):
    monkeypatch.setattr(iter5.settings, "AI_HEALING_APPLY_ENABLED", False)
    db = _FakeDB({("TestCase", 1): _web_case(), ("Module", 2): _Obj(id=2, project_id=3)})

    out = _run(iter5.preview_healing_patch(body=_apply_body(), db=db, user=_Obj(id=9)))

    assert out.accepted is True
    assert out.preview_config["steps"][0]["params"]["selector"] == "button[type=submit]"
    assert db.commits == 0  # preview 永不落库
