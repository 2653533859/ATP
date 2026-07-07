"""P3.C audit service 单测：write_audit_log(project_id=...) 写字段；异常吞掉。"""

import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules.setdefault(
    "app.core.redis_client",
    types.SimpleNamespace(
        get_json_cache=lambda *a, **kw: None,
        set_json_cache=lambda *a, **kw: None,
        delete_json_cache=lambda *a, **kw: None,
        publish_run_event=lambda *a, **kw: None,
    ),
)

from app.models.audit import AuditLog
from app.models.bootstrap import load_all_models
from app.services.audit import write_audit_log

load_all_models()


class _FakeDB:
    def __init__(self):
        self.added: list = []
        self.flushed = 0

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed += 1


def test_write_audit_log_persists_project_id():
    db = _FakeDB()
    asyncio.run(
        write_audit_log(
            db,
            action="access_denied",
            resource_type="project",
            resource_id=12,
            user_id=7,
            username="alice",
            detail="min_role=owner, actual=editor",
            project_id=12,
        )
    )
    assert len(db.added) == 1
    log: AuditLog = db.added[0]
    assert log.action == "access_denied"
    assert log.project_id == 12
    assert log.user_id == 7
    assert log.detail.startswith("min_role=owner")


def test_write_audit_log_swallows_exception():
    class _Boom:
        def add(self, _obj):
            raise RuntimeError("boom")

        async def flush(self):
            return None

    # 不应抛
    asyncio.run(
        write_audit_log(
            _Boom(),  # type: ignore[arg-type]
            action="x",
            resource_type="y",
        )
    )
