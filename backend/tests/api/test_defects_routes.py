"""Regression coverage for the internal defect and failed-run evidence API."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import defects
from app.models.bootstrap import load_all_models
from app.models.defect import Defect
from app.schemas.defect import DefectCreate, DefectCreateFromRun, DefectUpdate


NOW = datetime.now(timezone.utc)
load_all_models()


def _user(user_id: int = 7):
    return SimpleNamespace(id=user_id, username="engineer", role="engineer")


def _defect_view(defect_id: int = 11, *, status: str = "open", case_id: int | None = None):
    return SimpleNamespace(
        id=defect_id,
        project_id=1,
        case_id=case_id,
        title="登录接口失败",
        description="HTTP 500",
        status=status,
        priority="P2",
        severity="major",
        fingerprint="fingerprint",
        resolution=None,
        labels=[],
        occurrence_count=1,
        last_seen_at=NOW,
        creator_id=7,
        assignee_id=None,
        created_at=NOW,
        updated_at=NOW,
        run_links=[],
    )


class _FakeDB:
    def __init__(self, project=None):
        self.project = project or SimpleNamespace(id=1)
        self.added = []
        self.committed = False

    async def get(self, model, _id):
        if getattr(model, "__name__", "") == "Project":
            return self.project
        return None

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if isinstance(value, Defect) and value.id is None:
                value.id = 11

    async def commit(self):
        self.committed = True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Authorization: Bearer super-secret", "Authorization=[REDACTED]"),
        ("cookie=session=abc; password=secret", "cookie=[REDACTED]; password=[REDACTED]"),
    ],
)
def test_evidence_text_redacts_credentials(raw, expected):
    assert defects._safe_text(raw) == expected


def test_asset_reference_drops_presigned_query_and_fragment():
    assert defects._safe_asset_ref("https://minio.example/object.png?X-Amz-Signature=secret#part") == (
        "https://minio.example/object.png"
    )


def test_nested_evidence_is_redacted_and_bounded():
    evidence = defects._safe_json({"case_run_ids": [{"error": "token=secret"}]})
    assert evidence == {"case_run_ids": [{"error": "token=[REDACTED]"}]}
    assert defects._safe_json({"authorization": "Bearer secret", "nested": {"api_key": "secret"}}) == {
        "authorization": "[REDACTED]",
        "nested": {"api_key": "[REDACTED]"},
    }


def test_schema_trims_title_and_rejects_blank_title():
    assert DefectCreate(project_id=1, title="  crash  ").title == "crash"
    with pytest.raises(ValueError):
        DefectCreate(project_id=1, title="   ")


def test_status_transition_rejects_reopening_an_open_defect(monkeypatch):
    async def fake_get_defect(*_args, **_kwargs):
        return _defect_view(status="open")

    async def fake_access(*_args, **_kwargs):
        return None

    async def fake_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(defects, "_get_defect", fake_get_defect)
    monkeypatch.setattr(defects, "assert_project_access", fake_access)
    monkeypatch.setattr(defects, "write_audit_log", fake_audit)

    with pytest.raises(Exception) as exc:
        import asyncio

        asyncio.run(
            defects.update_defect(
                defect_id=11,
                body=DefectUpdate(status="reopened"),
                db=_FakeDB(),
                user=_user(),
            )
        )
    assert getattr(exc.value, "status_code", None) == 409


def test_create_from_run_rejects_cross_project_run(monkeypatch):
    from fastapi import HTTPException

    async def fake_access(_db, _user, project_id, _role):
        if project_id == 2:
            raise HTTPException(status_code=403, detail="No access to this project")

    async def fake_context(*_args, **_kwargs):
        return defects._RunContext(
            project_id=2,
            case_id=None,
            title="其他项目失败",
            status="failed",
            error_message="boom",
            trace_id=None,
            evidence={"error_message": "boom"},
        )

    monkeypatch.setattr(defects, "assert_project_access", fake_access)
    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)

    import asyncio

    with pytest.raises(Exception) as exc:
        asyncio.run(
            defects.create_defect_from_run(
                run_type="case",
                run_id=4,
                body=DefectCreateFromRun(),
                db=_FakeDB(),
                user=_user(),
            )
        )
    # The project comes from the run context; the route must authorize that scope.
    assert getattr(exc.value, "status_code", None) == 403


def test_create_from_run_rejects_passed_run(monkeypatch):
    async def fake_context(*_args, **_kwargs):
        return defects._RunContext(1, None, "已通过", "passed", None, None, {})

    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)

    import asyncio

    with pytest.raises(Exception) as exc:
        asyncio.run(
            defects.create_defect_from_run(
                run_type="case",
                run_id=4,
                body=DefectCreateFromRun(),
                db=_FakeDB(),
                user=_user(),
            )
        )
    assert getattr(exc.value, "status_code", None) == 409


def test_create_internal_defect_from_run_persists_sanitized_context(monkeypatch):
    context = defects._RunContext(
        project_id=1,
        case_id=9,
        title="登录接口失败",
        status="failed",
        error_message="Authorization: Bearer secret",
        trace_id="trace-1",
        evidence={"error_message": "Authorization=[REDACTED]", "trace_id": "trace-1"},
    )
    db = _FakeDB()

    async def fake_access(*_args, **_kwargs):
        return None

    async def fake_context(*_args, **_kwargs):
        return context

    async def fake_duplicate(*_args, **_kwargs):
        return None

    async def fake_attach(*_args, **_kwargs):
        return None

    async def fake_audit(*_args, **_kwargs):
        return None

    async def fake_load(*_args, **_kwargs):
        return _defect_view(case_id=9)

    monkeypatch.setattr(defects, "assert_project_access", fake_access)
    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)
    monkeypatch.setattr(defects, "_find_duplicate", fake_duplicate)
    monkeypatch.setattr(defects, "_attach_link", fake_attach)
    monkeypatch.setattr(defects, "write_audit_log", fake_audit)
    monkeypatch.setattr(defects, "_load_defect_after_write", fake_load)

    import asyncio

    result = asyncio.run(
        defects.create_defect_from_run(
            run_type="case",
            run_id=4,
            body=DefectCreateFromRun(),
            db=db,
            user=_user(),
        )
    )
    assert result.created is True
    assert result.defect.title == "登录接口失败"
    assert result.defect.run_links == []  # the persistence helper is isolated in this unit test
    created = next(value for value in db.added if isinstance(value, Defect))
    assert created.case_id == 9
    assert created.description == "Authorization=[REDACTED]"


def test_duplicate_run_returns_existing_defect_and_does_not_create_new_row(monkeypatch):
    existing = _defect_view()
    db = _FakeDB()

    async def fake_access(*_args, **_kwargs):
        return None

    async def fake_context(*_args, **_kwargs):
        return defects._RunContext(1, None, "登录接口失败", "failed", "boom", None, {"error_message": "boom"})

    async def fake_duplicate(*_args, **_kwargs):
        return existing

    async def fake_attach(*_args, **_kwargs):
        return None

    async def fake_audit(*_args, **_kwargs):
        return None

    async def fake_load(*_args, **_kwargs):
        return existing

    monkeypatch.setattr(defects, "assert_project_access", fake_access)
    monkeypatch.setattr(defects, "_resolve_run_context", fake_context)
    monkeypatch.setattr(defects, "_find_duplicate", fake_duplicate)
    monkeypatch.setattr(defects, "_attach_link", fake_attach)
    monkeypatch.setattr(defects, "write_audit_log", fake_audit)
    monkeypatch.setattr(defects, "_load_defect_after_write", fake_load)

    import asyncio

    result = asyncio.run(
        defects.create_defect_from_run(
            run_type="case",
            run_id=4,
            body=DefectCreateFromRun(),
            db=db,
            user=_user(),
        )
    )
    assert result.created is False
    assert result.duplicate_of == existing.id
    assert db.added == []
    assert existing.occurrence_count == 2


def test_migration_registers_both_internal_defect_tables(repo_file):
    migration = repo_file("backend/alembic/versions/20260824_0060_add_internal_defects.py")
    assert 'op.create_table(\n        "defects"' in migration
    assert 'op.create_table(\n        "defect_run_links"' in migration
    assert "uq_defect_run_links_defect_run" in migration
