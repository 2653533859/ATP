"""补齐 defects.py 端点的未覆盖分支：内部缺陷 CRUD、运行关联、外部 Issue 守卫与 Webhook。"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1 import defects
from app.models.bootstrap import load_all_models
from app.models.defect import Defect
from app.models.user import UserRole
from app.schemas.defect import (
    DefectCreate,
    DefectCreateFromRun,
    DefectExternalCreate,
    DefectExternalLinkCreate,
    DefectExternalSyncIn,
    DefectRunLinkCreate,
    DefectUpdate,
)
from app.services.defect_external import EXTERNAL_SYNC_ERROR

load_all_models()

NOW = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows if rows is not None else []

    def scalar_one_or_none(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    """极简异步会话：get/execute 走预置映射，写操作只记录调用。"""

    def __init__(self, objects=None, results=None):
        self.objects = dict(objects or {})
        self.results = list(results or [])
        self.added = []
        self.deleted = []
        self.commits = 0
        self.execute_calls = 0

    async def get(self, model, ident):
        value = self.objects.get(model)
        return value(ident) if callable(value) else value

    async def execute(self, _statement):
        self.execute_calls += 1
        if self.results:
            return self.results.pop(0)
        return _Result()

    def add(self, value):
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def flush(self):
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = 11

    async def commit(self):
        self.commits += 1


class _Request:
    def __init__(self, payload=None, error=None):
        self._payload = payload
        self._error = error

    async def json(self):
        if self._error is not None:
            raise self._error
        return self._payload


def _user(user_id: int = 7, role=None):
    return SimpleNamespace(id=user_id, username="engineer", role=role or "engineer")


def _defect_view(
    defect_id: int = 11,
    *,
    project_id: int = 1,
    status: str = "open",
    case_id=None,
    run_links=None,
    external_links=None,
):
    return SimpleNamespace(
        id=defect_id,
        project_id=project_id,
        case_id=case_id,
        title="登录接口失败",
        description="HTTP 500",
        status=status,
        priority="P2",
        severity="major",
        fingerprint="fp",
        resolution=None,
        labels=[],
        occurrence_count=1,
        last_seen_at=NOW,
        creator_id=7,
        assignee_id=None,
        created_at=NOW,
        updated_at=NOW,
        run_links=run_links or [],
        external_links=external_links or [],
    )


def _tracker(*, enabled: bool = True, project_id: int = 1):
    from app.models.bug_tracker import TrackerType

    return SimpleNamespace(
        id=5,
        project_id=project_id,
        name="项目 Jira",
        tracker_type=TrackerType.jira,
        config={},
        field_mapping={},
        is_enabled=enabled,
    )


def _external_link(tracker=None, *, defect_id: int = 11):
    return SimpleNamespace(
        id=21,
        defect_id=defect_id,
        tracker_id=5,
        tracker=tracker or _tracker(),
        external_key="ATP-21",
        external_url="https://jira.example/browse/ATP-21",
        external_title="登录失败",
        external_status=None,
        sync_state="linked",
        last_synced_at=None,
        last_error=None,
        created_by=7,
        created_at=NOW,
        updated_at=NOW,
    )


def _no_access(monkeypatch):
    async def fake_access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(defects, "assert_project_access", fake_access)


def _ok_audit(monkeypatch):
    calls = []

    async def fake_audit(_db, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(defects, "write_audit_log", fake_audit)
    return calls


def test_safe_helpers_cover_none_invalid_and_truncated_inputs():
    assert defects._safe_text(None) is None
    assert defects._safe_json({"a": {"b": {"c": {"d": "x"}}}})["a"]["b"]["c"]["d"] == "[TRUNCATED]"
    fallback = defects._safe_json(datetime.now(timezone.utc))
    assert isinstance(fallback, str) and fallback
    assert defects._safe_asset_ref("http://[invalid") is None
    assert defects._safe_external_url("http://[invalid") is None


def test_safe_external_url_rejects_invalid_and_credentialed_urls():
    with pytest.raises(HTTPException) as invalid:
        defects._safe_external_url("http://[invalid", reject_invalid=True)
    assert invalid.value.status_code == 422

    with pytest.raises(HTTPException) as credentialed:
        defects._safe_external_url("https://user:pass@jira.example/browse/ATP-1", reject_invalid=True)
    assert credentialed.value.status_code == 422

    assert defects._safe_external_url("https://user:pass@jira.example/browse/ATP-1") is None


def test_get_defect_helper_scopes_and_404s(monkeypatch):
    calls = []

    async def fake_access(_db, _user_obj, project_id, role):
        calls.append((project_id, role))

    monkeypatch.setattr(defects, "assert_project_access", fake_access)

    with pytest.raises(HTTPException) as missing:
        asyncio.run(defects._get_defect(_FakeDB(results=[_Result()]), 11, _user(), defects.ProjectRole.viewer))
    assert missing.value.status_code == 404

    view = _defect_view(case_id=9)
    result = asyncio.run(
        defects._get_defect(_FakeDB(results=[_Result(scalar=view)]), 11, _user(), defects.ProjectRole.editor)
    )
    assert result is view
    assert calls == [(1, defects.ProjectRole.editor)]


def test_ensure_assignee_admin_shortcut_and_member_pass():
    admin_db = _FakeDB(objects={defects.User: SimpleNamespace(is_active=True)})
    asyncio.run(defects._ensure_assignee(admin_db, 1, 8, _user(role=UserRole.admin)))
    assert admin_db.execute_calls == 0

    member_db = _FakeDB(objects={defects.User: SimpleNamespace(is_active=True)}, results=[_Result(scalar=1)])
    asyncio.run(defects._ensure_assignee(member_db, 1, 8, _user()))
    assert member_db.execute_calls == 1


def test_ensure_case_project_missing_case_is_404():
    with pytest.raises(HTTPException) as missing:
        asyncio.run(defects._ensure_case_project(_FakeDB(), 1, 9))
    assert missing.value.status_code == 404


def test_attach_link_rejects_cross_project_context(monkeypatch):
    async def fake_context(*_args, **_kwargs):
        return defects._RunContext(2, None, "其他项目", "failed", "boom", None, {"x": 1})

    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(defects._attach_link(_FakeDB(), _defect_view(), "case", 4, 7))
    assert exc.value.status_code == 400


def test_attach_link_updates_existing_link_and_backfills_case(monkeypatch):
    context = defects._RunContext(1, 9, "登录接口失败", "failed", "boom", None, {"error_message": "boom"})
    existing = SimpleNamespace(id=31, case_id=None, evidence={}, linked_by=None)

    async def fake_context(*_args, **_kwargs):
        return context

    case_calls = []

    async def fake_case_check(_db, project_id, case_id):
        case_calls.append((project_id, case_id))

    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)
    monkeypatch.setattr(defects, "_ensure_case_project", fake_case_check)

    defect = _defect_view(case_id=None)
    defect.last_seen_at = None
    link = asyncio.run(defects._attach_link(_FakeDB(results=[_Result(scalar=existing)]), defect, "case", 4, 7))
    assert link is existing
    assert existing.case_id == 9
    assert existing.evidence == {"error_message": "boom"}
    assert existing.linked_by == 7
    assert defect.case_id == 9
    assert defect.last_seen_at is not None
    assert case_calls == [(1, 9)]


def test_create_defect_with_run_link_persists_and_attaches(monkeypatch):
    _no_access(monkeypatch)
    audit = _ok_audit(monkeypatch)
    attached = []

    async def fake_context(*_args, **_kwargs):
        return defects._RunContext(1, 9, "登录接口失败", "failed", None, None, {"status": "failed"})

    async def fake_duplicate(*_args, **_kwargs):
        return None

    async def fake_attach(_db, _defect, run_type, run_id, linked_by, case_id=None):
        attached.append((run_type, run_id, linked_by, case_id))

    view = _defect_view(case_id=9)

    async def fake_load(*_args, **_kwargs):
        return view

    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)
    monkeypatch.setattr(defects, "_find_duplicate", fake_duplicate)
    monkeypatch.setattr(defects, "_attach_link", fake_attach)
    monkeypatch.setattr(defects, "_load_defect_after_write", fake_load)

    db = _FakeDB(objects={defects.Project: SimpleNamespace(id=1)})
    result = asyncio.run(
        defects.create_defect(
            body=DefectCreate(
                project_id=1,
                title="登录接口失败",
                labels=[" login "],
                run_links=[DefectRunLinkCreate(run_type="case", run_id=4)],
            ),
            db=db,
            user=_user(),
        )
    )
    assert result.created is True
    created = next(value for value in db.added if isinstance(value, Defect))
    assert created.case_id == 9
    assert created.fingerprint
    assert created.last_seen_at is not None
    assert created.labels == ["login"]
    assert attached == [("case", 4, 7, None)]
    assert any(call["action"] == "defect_create" for call in audit)
    assert db.commits == 1


def test_create_defect_duplicate_bumps_occurrence(monkeypatch):
    _no_access(monkeypatch)
    audit = _ok_audit(monkeypatch)
    existing = _defect_view()

    async def fake_context(*_args, **_kwargs):
        return defects._RunContext(1, None, "登录接口失败", "failed", "boom", None, {"error_message": "boom"})

    async def fake_duplicate(*_args, **_kwargs):
        return existing

    async def fake_attach(*_args, **_kwargs):
        return None

    async def fake_load(*_args, **_kwargs):
        return existing

    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)
    monkeypatch.setattr(defects, "_find_duplicate", fake_duplicate)
    monkeypatch.setattr(defects, "_attach_link", fake_attach)
    monkeypatch.setattr(defects, "_load_defect_after_write", fake_load)

    db = _FakeDB(objects={defects.Project: SimpleNamespace(id=1)})
    result = asyncio.run(
        defects.create_defect(body=DefectCreate(project_id=1, title="登录接口失败"), db=db, user=_user())
    )
    assert result.created is False
    assert result.duplicate_of == 11
    assert existing.occurrence_count == 2
    assert db.added == []
    assert any(call["action"] == "defect_duplicate_detected" for call in audit)


def test_create_defect_missing_project_is_404(monkeypatch):
    _no_access(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(defects.create_defect(body=DefectCreate(project_id=1, title="t"), db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 404


def test_create_defect_rejects_cross_project_run_link(monkeypatch):
    _no_access(monkeypatch)

    async def fake_context(*_args, **_kwargs):
        return defects._RunContext(2, None, "其他项目", "failed", "boom", None, {})

    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)
    db = _FakeDB(objects={defects.Project: SimpleNamespace(id=1)})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            defects.create_defect(
                body=DefectCreate(
                    project_id=1,
                    title="t",
                    run_links=[DefectRunLinkCreate(run_type="case", run_id=4)],
                ),
                db=db,
                user=_user(),
            )
        )
    assert exc.value.status_code == 400


def test_create_from_run_rejects_blank_effective_title(monkeypatch):
    _no_access(monkeypatch)

    async def fake_context(*_args, **_kwargs):
        return defects._RunContext(1, None, "原标题", "failed", None, None, {})

    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            defects.create_defect_from_run(
                run_type="case",
                run_id=4,
                body=DefectCreateFromRun(title="   "),
                db=_FakeDB(),
                user=_user(),
            )
        )
    assert exc.value.status_code == 422


def test_get_defect_endpoint_serializes(monkeypatch):
    view = _defect_view()

    async def fake_get(*_args, **_kwargs):
        return view

    monkeypatch.setattr(defects, "_get_defect", fake_get)
    result = asyncio.run(defects.get_defect(defect_id=11, db=_FakeDB(), user=_user()))
    assert result.id == 11
    assert result.title == "登录接口失败"


def test_update_defect_applies_fields_strips_title_and_audits(monkeypatch):
    view = _defect_view()
    audit = _ok_audit(monkeypatch)
    assignee_checks = []

    async def fake_get(*_args, **_kwargs):
        return view

    async def fake_assignee(_db, project_id, assignee_id, _user_obj):
        assignee_checks.append((project_id, assignee_id))

    async def fake_load(*_args, **_kwargs):
        return view

    monkeypatch.setattr(defects, "_get_defect", fake_get)
    monkeypatch.setattr(defects, "_ensure_assignee", fake_assignee)
    monkeypatch.setattr(defects, "_load_defect_after_write", fake_load)

    db = _FakeDB()
    result = asyncio.run(
        defects.update_defect(
            defect_id=11,
            body=DefectUpdate(title="  新标题  ", status="in_progress", assignee_id=8),
            db=db,
            user=_user(),
        )
    )
    assert result.title == "新标题"
    assert view.status == "in_progress"
    assert view.assignee_id == 8
    assert assignee_checks == [(1, 8)]
    assert any(call["action"] == "defect_update" for call in audit)
    assert db.commits == 1


def test_link_defect_run_endpoint_returns_serialized_link(monkeypatch):
    view = _defect_view()
    audit = _ok_audit(monkeypatch)
    link = SimpleNamespace(
        id=31,
        run_type="case",
        run_id=4,
        case_id=None,
        evidence={"a": 1},
        linked_by=7,
        created_at=NOW,
    )

    async def fake_get(*_args, **_kwargs):
        return view

    async def fake_attach(*_args, **_kwargs):
        return link

    monkeypatch.setattr(defects, "_get_defect", fake_get)
    monkeypatch.setattr(defects, "_attach_link", fake_attach)

    result = asyncio.run(
        defects.link_defect_run(
            defect_id=11,
            body=DefectRunLinkCreate(run_type="case", run_id=4),
            db=_FakeDB(),
            user=_user(),
        )
    )
    assert result.id == 31
    assert result.evidence == {"a": 1}
    assert any(call["action"] == "defect_run_link" for call in audit)


def test_unlink_defect_run_404_and_delete(monkeypatch):
    view = _defect_view()

    async def fake_get(*_args, **_kwargs):
        return view

    monkeypatch.setattr(defects, "_get_defect", fake_get)
    db = _FakeDB()
    with pytest.raises(HTTPException) as missing:
        asyncio.run(defects.unlink_defect_run(defect_id=11, link_id=99, db=db, user=_user()))
    assert missing.value.status_code == 404

    audit = _ok_audit(monkeypatch)
    link = SimpleNamespace(id=5, run_type="case", run_id=4)
    view.run_links = [link]
    asyncio.run(defects.unlink_defect_run(defect_id=11, link_id=5, db=db, user=_user()))
    assert db.deleted == [link]
    assert any(call["action"] == "defect_run_unlink" for call in audit)


def test_list_external_links_endpoint(monkeypatch):
    link = _external_link()
    view = _defect_view(external_links=[link])

    async def fake_get(*_args, **_kwargs):
        return view

    monkeypatch.setattr(defects, "_get_defect", fake_get)
    result = asyncio.run(defects.list_defect_external_links(defect_id=11, db=_FakeDB(), user=_user()))
    assert len(result) == 1
    assert result[0].external_key == "ATP-21"


def test_tracker_and_external_link_lookup_guardrails():
    view = _defect_view()
    with pytest.raises(HTTPException) as missing_tracker:
        asyncio.run(defects._get_tracker_for_defect(_FakeDB(), view, 5))
    assert missing_tracker.value.status_code == 404

    other_project = _tracker(project_id=2)
    with pytest.raises(HTTPException) as wrong_project:
        asyncio.run(defects._get_tracker_for_defect(_FakeDB(objects={defects.BugTracker: other_project}), view, 5))
    assert wrong_project.value.status_code == 400

    with pytest.raises(HTTPException) as missing_link:
        asyncio.run(defects._get_external_link(_FakeDB(results=[_Result()]), 11, 21))
    assert missing_link.value.status_code == 404


def test_duplicate_manual_external_link_conflicts(monkeypatch):
    view = _defect_view()
    tracker = _tracker()

    async def fake_get_defect(*_args, **_kwargs):
        return view

    async def fake_tracker(*_args, **_kwargs):
        return tracker

    monkeypatch.setattr(defects, "_get_defect", fake_get_defect)
    monkeypatch.setattr(defects, "_get_tracker_for_defect", fake_tracker)

    db = _FakeDB(results=[_Result(scalar=_external_link(tracker))])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            defects.link_defect_external_issue(
                defect_id=11,
                body=DefectExternalLinkCreate(tracker_id=5, external_key="ATP-21"),
                db=db,
                user=_user(),
            )
        )
    assert exc.value.status_code == 409


def test_create_external_issue_disabled_tracker_conflicts(monkeypatch):
    view = _defect_view()
    disabled = _tracker(enabled=False)

    async def fake_get_defect(*_args, **_kwargs):
        return view

    async def fake_tracker(*_args, **_kwargs):
        return disabled

    monkeypatch.setattr(defects, "_get_defect", fake_get_defect)
    monkeypatch.setattr(defects, "_get_tracker_for_defect", fake_tracker)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            defects.create_defect_external_issue(
                defect_id=11,
                body=DefectExternalCreate(tracker_id=5),
                db=_FakeDB(),
                user=_user(),
            )
        )
    assert exc.value.status_code == 409


def test_create_external_issue_maps_service_failures(monkeypatch):
    view = _defect_view()
    tracker = _tracker()

    async def fake_get_defect(*_args, **_kwargs):
        return view

    async def fake_tracker(*_args, **_kwargs):
        return tracker

    async def fake_duplicate(*_args, **_kwargs):
        return None

    async def boom(**_kwargs):
        raise RuntimeError("jira down")

    monkeypatch.setattr(defects, "_get_defect", fake_get_defect)
    monkeypatch.setattr(defects, "_get_tracker_for_defect", fake_tracker)
    monkeypatch.setattr(defects, "find_duplicate_bug", fake_duplicate)
    monkeypatch.setattr(defects, "create_bug", boom)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            defects.create_defect_external_issue(
                defect_id=11,
                body=DefectExternalCreate(tracker_id=5),
                db=_FakeDB(),
                user=_user(),
            )
        )
    assert exc.value.status_code == 502

    async def empty_bug(**_kwargs):
        return {}

    monkeypatch.setattr(defects, "create_bug", empty_bug)
    with pytest.raises(HTTPException) as empty:
        asyncio.run(
            defects.create_defect_external_issue(
                defect_id=11,
                body=DefectExternalCreate(tracker_id=5),
                db=_FakeDB(),
                user=_user(),
            )
        )
    assert empty.value.status_code == 502


def test_create_external_issue_duplicate_key_conflicts(monkeypatch):
    view = _defect_view()
    tracker = _tracker()

    async def fake_get_defect(*_args, **_kwargs):
        return view

    async def fake_tracker(*_args, **_kwargs):
        return tracker

    async def fake_duplicate(*_args, **_kwargs):
        return None

    async def fake_create(**_kwargs):
        return {"bug_id": "ATP-21"}

    monkeypatch.setattr(defects, "_get_defect", fake_get_defect)
    monkeypatch.setattr(defects, "_get_tracker_for_defect", fake_tracker)
    monkeypatch.setattr(defects, "find_duplicate_bug", fake_duplicate)
    monkeypatch.setattr(defects, "create_bug", fake_create)
    db = _FakeDB(results=[_Result(scalar=_external_link(tracker))])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            defects.create_defect_external_issue(
                defect_id=11,
                body=DefectExternalCreate(tracker_id=5),
                db=db,
                user=_user(),
            )
        )
    assert exc.value.status_code == 409


def test_sync_external_issue_disabled_and_failure_paths(monkeypatch):
    view = _defect_view()
    disabled_link = _external_link(_tracker(enabled=False))

    async def fake_get_defect(*_args, **_kwargs):
        return view

    async def fake_disabled_link(*_args, **_kwargs):
        return disabled_link

    monkeypatch.setattr(defects, "_get_defect", fake_get_defect)
    monkeypatch.setattr(defects, "_get_external_link", fake_disabled_link)
    with pytest.raises(HTTPException) as disabled:
        asyncio.run(
            defects.sync_defect_external_issue(
                defect_id=11,
                link_id=21,
                body=DefectExternalSyncIn(),
                db=_FakeDB(),
                user=_user(),
            )
        )
    assert disabled.value.status_code == 409

    link = _external_link()

    async def fake_link(*_args, **_kwargs):
        return link

    async def boom(**_kwargs):
        raise RuntimeError("status endpoint down")

    monkeypatch.setattr(defects, "_get_external_link", fake_link)
    monkeypatch.setattr(defects, "get_bug_status", boom)
    db = _FakeDB()
    with pytest.raises(HTTPException) as failure:
        asyncio.run(
            defects.sync_defect_external_issue(
                defect_id=11,
                link_id=21,
                body=DefectExternalSyncIn(),
                db=db,
                user=_user(),
            )
        )
    assert failure.value.status_code == 502
    assert failure.value.detail == EXTERNAL_SYNC_ERROR
    assert link.sync_state == "error"
    assert link.last_error == EXTERNAL_SYNC_ERROR
    assert db.commits == 1


def test_unlink_external_issue_removes_link(monkeypatch):
    view = _defect_view()
    link = _external_link()
    audit = _ok_audit(monkeypatch)

    async def fake_get_defect(*_args, **_kwargs):
        return view

    async def fake_get_link(*_args, **_kwargs):
        return link

    monkeypatch.setattr(defects, "_get_defect", fake_get_defect)
    monkeypatch.setattr(defects, "_get_external_link", fake_get_link)
    db = _FakeDB()
    asyncio.run(defects.unlink_defect_external_issue(defect_id=11, link_id=21, db=db, user=_user()))
    assert db.deleted == [link]
    assert any(call["action"] == "defect_external_unlink" for call in audit)


def test_webhook_guards_unknown_disabled_and_bad_json():
    with pytest.raises(HTTPException) as unknown:
        asyncio.run(defects.handle_defect_external_webhook(5, _Request({}), _FakeDB()))
    assert unknown.value.status_code == 404

    disabled = _tracker(enabled=False)
    with pytest.raises(HTTPException) as off:
        asyncio.run(
            defects.handle_defect_external_webhook(5, _Request({}), _FakeDB(objects={defects.BugTracker: disabled}))
        )
    assert off.value.status_code == 409

    with pytest.raises(HTTPException) as bad:
        asyncio.run(
            defects.handle_defect_external_webhook(
                5,
                _Request(error=ValueError("bad body")),
                _FakeDB(objects={defects.BugTracker: _tracker()}),
            )
        )
    assert bad.value.status_code == 400


def test_webhook_unparsed_payload_and_missing_targets():
    tracker = _tracker()

    unparsed = asyncio.run(
        defects.handle_defect_external_webhook(
            5, _Request({"unrelated": True}), _FakeDB(objects={defects.BugTracker: tracker})
        )
    )
    assert unparsed.success is False
    assert unparsed.external_key == ""

    payload = {"issue": {"key": "ATP-21", "fields": {"status": {"name": "Done"}}}}
    no_link = asyncio.run(
        defects.handle_defect_external_webhook(5, _Request(payload), _FakeDB(objects={defects.BugTracker: tracker}))
    )
    assert no_link.success is False
    assert "未找到" in no_link.message

    orphan = _FakeDB(
        objects={defects.BugTracker: tracker, Defect: None},
        results=[_Result(scalar=_external_link(tracker))],
    )
    missing_defect = asyncio.run(defects.handle_defect_external_webhook(5, _Request(payload), orphan))
    assert missing_defect.success is False
    assert "已被删除" in missing_defect.message


def test_push_to_external_requires_enabled_tracker(monkeypatch):
    view = _defect_view()
    link = _external_link(_tracker(enabled=False))

    async def fake_get_defect(*_args, **_kwargs):
        return view

    async def fake_get_link(*_args, **_kwargs):
        return link

    monkeypatch.setattr(defects, "_get_defect", fake_get_defect)
    monkeypatch.setattr(defects, "_get_external_link", fake_get_link)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(defects.push_defect_to_external_issue(defect_id=11, link_id=21, db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 409


def test_safe_helpers_treat_falsy_refs_as_absent():
    assert defects._safe_asset_ref(None) is None
    assert defects._safe_asset_ref("") is None
    assert defects._safe_external_url(None) is None
    assert defects._safe_external_url("") is None


def test_ensure_assignee_rejects_non_member():
    db = _FakeDB(objects={defects.User: SimpleNamespace(is_active=True)}, results=[_Result()])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(defects._ensure_assignee(db, 1, 8, _user()))
    assert exc.value.status_code == 400
    assert "项目成员" in exc.value.detail


def test_ensure_case_project_accepts_same_project_and_rejects_foreign_module():
    case = SimpleNamespace(module_id=4)
    same = _FakeDB(objects={defects.TestCase: case, defects.Module: SimpleNamespace(project_id=1)})
    assert asyncio.run(defects._ensure_case_project(same, 1, 9)) is None

    foreign = _FakeDB(objects={defects.TestCase: case, defects.Module: SimpleNamespace(project_id=2)})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(defects._ensure_case_project(foreign, 1, 9))
    assert exc.value.status_code == 400


def test_find_duplicate_load_and_external_link_happy_paths():
    view = _defect_view()
    hit = asyncio.run(defects._find_duplicate(_FakeDB(results=[_Result(scalar=view)]), 1, "fp"))
    assert hit is view
    assert asyncio.run(defects._find_duplicate(_FakeDB(results=[_Result()]), 1, "fp")) is None

    loaded = asyncio.run(defects._load_defect_after_write(_FakeDB(results=[_Result(scalar=view)]), 11))
    assert loaded is view

    link = _external_link()
    assert asyncio.run(defects._get_external_link(_FakeDB(results=[_Result(scalar=link)]), 11, 21)) is link


def test_attach_link_creates_new_link_and_honors_explicit_case(monkeypatch):
    from app.models.defect import DefectRunLink

    context = defects._RunContext(1, None, "标题", "failed", None, None, {"status": "failed"})

    async def fake_context(*_args, **_kwargs):
        return context

    case_calls = []

    async def fake_case_check(_db, project_id, case_id):
        if case_id is not None:
            case_calls.append((project_id, case_id))

    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)
    monkeypatch.setattr(defects, "_ensure_case_project", fake_case_check)

    defect = _defect_view(case_id=5)
    db = _FakeDB(results=[_Result()])
    link = asyncio.run(defects._attach_link(db, defect, "suite", 9, 7))
    assert isinstance(link, DefectRunLink)
    assert link.case_id is None
    assert link.run_type == "suite"
    assert link.run_id == 9
    assert db.added == [link]
    assert defect.case_id == 5
    assert case_calls == []

    explicit = asyncio.run(defects._attach_link(_FakeDB(results=[_Result()]), _defect_view(), "case", 4, 7, case_id=9))
    assert explicit.case_id == 9
    assert case_calls == [(1, 9), (1, 9)]


def test_list_defects_without_filters_reads_empty_page(monkeypatch):
    monkeypatch.setattr(defects, "scope_to_visible_projects", lambda stmt, *_args, **_kwargs: stmt)
    db = _FakeDB(results=[_Result(scalar=None), _Result(rows=[])])
    result = asyncio.run(
        defects.list_defects(
            project_id=None,
            case_id=None,
            run_type=None,
            run_id=None,
            status_filter=None,
            priority=None,
            severity=None,
            page=1,
            page_size=20,
            db=db,
            user=_user(),
        )
    )
    assert result.total == 0
    assert result.items == []


def test_list_defects_rejects_unknown_run_type(monkeypatch):
    monkeypatch.setattr(defects, "scope_to_visible_projects", lambda stmt, *_args, **_kwargs: stmt)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(defects.list_defects(run_type="bogus", run_id=4, db=_FakeDB(), user=_user()))
    assert exc.value.status_code == 422


def test_create_defect_validates_link_case_scope(monkeypatch):
    _no_access(monkeypatch)
    audit = _ok_audit(monkeypatch)
    case_calls = []

    async def fake_context(*_args, **_kwargs):
        return defects._RunContext(1, 9, "登录接口失败", "failed", None, None, {})

    async def fake_duplicate(*_args, **_kwargs):
        return None

    async def fake_case_check(_db, project_id, case_id):
        if case_id is not None:
            case_calls.append((project_id, case_id))

    async def fake_attach(*_args, **_kwargs):
        return None

    view = _defect_view(case_id=9)

    async def fake_load(*_args, **_kwargs):
        return view

    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)
    monkeypatch.setattr(defects, "_find_duplicate", fake_duplicate)
    monkeypatch.setattr(defects, "_ensure_case_project", fake_case_check)
    monkeypatch.setattr(defects, "_attach_link", fake_attach)
    monkeypatch.setattr(defects, "_load_defect_after_write", fake_load)

    db = _FakeDB(objects={defects.Project: SimpleNamespace(id=1)})
    result = asyncio.run(
        defects.create_defect(
            body=DefectCreate(
                project_id=1,
                title="登录接口失败",
                run_links=[DefectRunLinkCreate(run_type="case", run_id=4, case_id=9)],
            ),
            db=db,
            user=_user(),
        )
    )
    assert result.created is True
    assert case_calls == [(1, 9)]
    assert any(call["action"] == "defect_create" for call in audit)


def test_create_defect_duplicate_with_run_links_reuses_existing(monkeypatch):
    _no_access(monkeypatch)
    audit = _ok_audit(monkeypatch)
    existing = _defect_view()
    attached = []

    async def fake_context(*_args, **_kwargs):
        return defects._RunContext(1, None, "登录接口失败", "failed", "boom", None, {"error_message": "boom"})

    async def fake_duplicate(*_args, **_kwargs):
        return existing

    async def fake_attach(_db, _defect, run_type, run_id, linked_by, case_id=None):
        attached.append((run_type, run_id, linked_by))

    async def fake_load(*_args, **_kwargs):
        return existing

    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)
    monkeypatch.setattr(defects, "_find_duplicate", fake_duplicate)
    monkeypatch.setattr(defects, "_attach_link", fake_attach)
    monkeypatch.setattr(defects, "_load_defect_after_write", fake_load)

    db = _FakeDB(objects={defects.Project: SimpleNamespace(id=1)})
    result = asyncio.run(
        defects.create_defect(
            body=DefectCreate(
                project_id=1,
                title="登录接口失败",
                run_links=[DefectRunLinkCreate(run_type="suite", run_id=6)],
            ),
            db=db,
            user=_user(),
        )
    )
    assert result.created is False
    assert existing.occurrence_count == 2
    assert attached == [("suite", 6, 7)]
    assert any(call["action"] == "defect_duplicate_detected" for call in audit)


def test_update_defect_same_status_is_noop(monkeypatch):
    view = _defect_view()
    audit = _ok_audit(monkeypatch)

    async def fake_get(*_args, **_kwargs):
        return view

    async def fake_load(*_args, **_kwargs):
        return view

    monkeypatch.setattr(defects, "_get_defect", fake_get)
    monkeypatch.setattr(defects, "_load_defect_after_write", fake_load)
    db = _FakeDB()
    result = asyncio.run(defects.update_defect(defect_id=11, body=DefectUpdate(status="open"), db=db, user=_user()))
    assert result.status == "open"
    assert db.commits == 1
    assert any(call["action"] == "defect_update" for call in audit)


def test_sync_external_issue_applies_mapping_or_skips(monkeypatch):
    view = _defect_view()
    link = _external_link()

    async def fake_get_defect(*_args, **_kwargs):
        return view

    async def fake_link(*_args, **_kwargs):
        return link

    async def fake_load(*_args, **_kwargs):
        return view

    async def unmapped(**_kwargs):
        return {"status": "unmapped-state-xyz", "bug_url": None}

    monkeypatch.setattr(defects, "_get_defect", fake_get_defect)
    monkeypatch.setattr(defects, "_get_external_link", fake_link)
    monkeypatch.setattr(defects, "_load_defect_after_write", fake_load)
    monkeypatch.setattr(defects, "get_bug_status", unmapped)
    _ok_audit(monkeypatch)

    result = asyncio.run(
        defects.sync_defect_external_issue(
            defect_id=11, link_id=21, body=DefectExternalSyncIn(), db=_FakeDB(), user=_user()
        )
    )
    assert result.defect_status == "open"
    assert link.sync_state == "synced"
    assert link.external_status == "unmapped-state-xyz"

    async def done(**_kwargs):
        return {"status": "Done", "bug_url": None}

    monkeypatch.setattr(defects, "get_bug_status", done)
    result = asyncio.run(
        defects.sync_defect_external_issue(
            defect_id=11, link_id=21, body=DefectExternalSyncIn(apply_status=False), db=_FakeDB(), user=_user()
        )
    )
    assert result.defect_status == "open"


def test_webhook_unmapped_status_keeps_internal_state(monkeypatch):
    tracker = _tracker()
    link = _external_link(tracker)
    view = _defect_view(status="in_progress")
    _ok_audit(monkeypatch)
    db = _FakeDB(objects={defects.BugTracker: tracker, Defect: view}, results=[_Result(scalar=link)])
    payload = {"issue": {"key": "ATP-21", "fields": {"status": {"name": "unmapped-state-xyz"}}}}
    result = asyncio.run(defects.handle_defect_external_webhook(5, _Request(payload), db))
    assert result.success is True
    assert view.status == "in_progress"
    assert link.sync_state == "synced"
    assert link.external_status == "unmapped-state-xyz"


def test_case_evidence_skips_empty_screenshot_refs():
    run = SimpleNamespace(status="failed", environment="staging", trace_id="t-1", error_message=None)
    case = SimpleNamespace(id=9, name="登录用例")
    steps = [
        SimpleNamespace(step_index=i, name=f"步骤{i}", status="passed", error_message=None, screenshot_url="")
        for i in range(1, 3)
    ]
    evidence = defects._case_evidence(run, case, steps)
    assert evidence["case_id"] == 9
    assert evidence["screenshot_refs"] == []
    assert [item["screenshot_ref"] for item in evidence["steps"]] == [None, None]
