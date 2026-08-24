"""Regression coverage for internal-to-external defect mappings."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.routing import APIRoute

from app.api.v1 import defects
from app.api.deps import require_engineer
from app.models.bootstrap import load_all_models
from app.models.bug_tracker import TrackerType
from app.models.defect_external import DefectExternalLink
from app.schemas.defect import DefectExternalCreate, DefectExternalLinkCreate, DefectExternalSyncIn
from app.services.defect_external import build_external_defect_description, map_external_status

load_all_models()


NOW = datetime(2026, 8, 24, 14, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, scalar=None):
        self.scalar = scalar

    def scalar_one_or_none(self):
        return self.scalar


class _DB:
    def __init__(self, tracker=None):
        self.tracker = tracker
        self.added = []
        self.commits = 0

    async def get(self, model, _id):
        if model.__name__ == "BugTracker":
            return self.tracker
        return None

    async def execute(self, _statement):
        return _Result()

    def add(self, value):
        self.added.append(value)
        if isinstance(value, DefectExternalLink):
            value.id = 21

    async def commit(self):
        self.commits += 1


def _user():
    return SimpleNamespace(id=7, username="engineer", role="engineer")


def _defect():
    return SimpleNamespace(
        id=11,
        project_id=1,
        title="登录失败",
        description="Authorization: Bearer secret",
        priority="P1",
        severity="major",
        labels=["login"],
        status="open",
        external_links=[],
    )


def _tracker():
    return SimpleNamespace(
        id=5,
        project_id=1,
        name="项目 Jira",
        tracker_type=TrackerType.jira,
        config={},
        field_mapping={},
        is_enabled=True,
    )


def _link(tracker=None):
    return SimpleNamespace(
        id=21,
        defect_id=11,
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


def test_external_status_mapping_and_redaction():
    assert map_external_status("In Progress") == "in_progress"
    assert map_external_status("Done") == "resolved"
    assert map_external_status("closed") == "closed"
    assert map_external_status("unknown vendor state") is None
    description = build_external_defect_description(_defect())
    assert "Authorization=[REDACTED]" in description
    assert "Bearer secret" not in description
    json_defect = _defect()
    json_defect.description = '{"token":"secret"}'
    assert "secret" not in build_external_defect_description(json_defect)
    assert defects._safe_external_url("javascript:alert(1)") is None


def test_manual_external_link_is_project_scoped_and_persisted(monkeypatch):
    defect = _defect()
    tracker = _tracker()
    link = _link(tracker)
    db = _DB(tracker)

    async def fake_get_defect(*_args, **_kwargs):
        return defect

    async def fake_get_link(*_args, **_kwargs):
        return link

    async def fake_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(defects, "_get_defect", fake_get_defect)
    monkeypatch.setattr(defects, "_get_external_link", fake_get_link)
    monkeypatch.setattr(defects, "write_audit_log", fake_audit)

    result = asyncio.run(
        defects.link_defect_external_issue(
            defect_id=11,
            body=DefectExternalLinkCreate(
                tracker_id=5,
                external_key="ATP-21",
                external_url="https://jira.example/browse/ATP-21?token=secret",
                external_title="登录失败",
            ),
            db=db,
            user=_user(),
        )
    )

    assert result.external_key == "ATP-21"
    created = next(value for value in db.added if isinstance(value, DefectExternalLink))
    assert created.external_url == "https://jira.example/browse/ATP-21"
    assert db.commits == 1


def test_create_external_issue_reuses_tracker_service(monkeypatch):
    defect = _defect()
    tracker = _tracker()
    link = _link(tracker)
    db = _DB(tracker)
    calls = {}

    async def fake_get_defect(*_args, **_kwargs):
        return defect

    async def fake_get_link(*_args, **_kwargs):
        return link

    async def fake_duplicate(*_args, **_kwargs):
        return None

    async def fake_create(**kwargs):
        calls.update(kwargs)
        return {"bug_id": "ATP-21", "bug_url": "https://jira.example/browse/ATP-21", "title": "登录失败"}

    async def fake_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(defects, "_get_defect", fake_get_defect)
    monkeypatch.setattr(defects, "_get_external_link", fake_get_link)
    monkeypatch.setattr(defects, "find_duplicate_bug", fake_duplicate)
    monkeypatch.setattr(defects, "create_bug", fake_create)
    monkeypatch.setattr(defects, "write_audit_log", fake_audit)

    result = asyncio.run(
        defects.create_defect_external_issue(
            defect_id=11,
            body=DefectExternalCreate(tracker_id=5),
            db=db,
            user=_user(),
        )
    )

    assert result.external_key == "ATP-21"
    assert calls["tracker_type"] == "jira"
    assert "Bearer secret" not in calls["description"]


def test_sync_external_issue_applies_mapped_status(monkeypatch):
    defect = _defect()
    tracker = _tracker()
    link = _link(tracker)
    db = _DB(tracker)

    async def fake_get_defect(*_args, **_kwargs):
        return defect

    async def fake_get_link(*_args, **_kwargs):
        return link

    async def fake_status(*_args, **_kwargs):
        return {"bug_id": "ATP-21", "status": "Done", "bug_url": link.external_url}

    async def fake_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(defects, "_get_defect", fake_get_defect)
    monkeypatch.setattr(defects, "_get_external_link", fake_get_link)
    monkeypatch.setattr(defects, "get_bug_status", fake_status)
    monkeypatch.setattr(defects, "write_audit_log", fake_audit)

    result = asyncio.run(
        defects.sync_defect_external_issue(
            defect_id=11,
            link_id=21,
            body=DefectExternalSyncIn(),
            db=db,
            user=_user(),
        )
    )

    assert result.defect_status == "resolved"
    assert defect.status == "resolved"
    assert link.external_status == "Done"
    assert link.sync_state == "synced"
    assert db.commits == 1


def test_external_links_migration_has_project_mapping_constraints(repo_file):
    migration = repo_file("backend/alembic/versions/20260824_0061_add_defect_external_links.py")
    assert 'op.create_table(\n        "defect_external_links"' in migration
    assert "uq_defect_external_links_key" in migration
    assert 'sa.ForeignKeyConstraint(["tracker_id"], ["bug_trackers.id"]' in migration


def test_external_mutations_require_engineer_role():
    mutation_paths = {
        "/defects/{defect_id}/external-links",
        "/defects/{defect_id}/external-links/create",
        "/defects/{defect_id}/external-links/{link_id}/sync",
        "/defects/{defect_id}/external-links/{link_id}",
    }
    routes = {
        route.path: route
        for route in defects.router.routes
        if isinstance(route, APIRoute) and route.path in mutation_paths
    }

    assert set(routes) == mutation_paths
    for route in routes.values():
        assert any(dependency.call is require_engineer for dependency in route.dependant.dependencies)
