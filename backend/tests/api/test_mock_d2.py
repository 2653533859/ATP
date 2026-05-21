"""D.2 Mock 版本管理 + 录制回放回归测试。"""
import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 用 setdefault stub 底层依赖（与 test_mock_server.py 兼容），不替换 mock_server 本身
_db_stub = sys.modules.setdefault(
    "app.core.database",
    types.SimpleNamespace(get_db=lambda: None, AsyncSessionLocal=lambda *a, **k: None),
)
# 若前面其他测试已 stub 但缺字段，则补齐
if not hasattr(_db_stub, "AsyncSessionLocal"):
    _db_stub.AsyncSessionLocal = lambda *a, **k: None
if not hasattr(_db_stub, "get_db"):
    _db_stub.get_db = lambda: None
sys.modules.setdefault(
    "app.core.redis_client",
    types.SimpleNamespace(
        get_json_cache=lambda *a, **kw: None,
        set_json_cache=lambda *a, **kw: None,
        delete_json_cache=lambda *a, **kw: None,
        delete_json_cache_pattern=lambda *a, **kw: None,
        publish_run_event=lambda *a, **kw: None,
        get_async_redis=lambda *a, **kw: None,
    ),
)
sys.modules.setdefault(
    "app.api.deps",
    types.SimpleNamespace(
        get_current_user=lambda: None,
        require_engineer=lambda: None,
        require_admin=lambda: None,
    ),
)

from app.api.v1 import mock_rules as mr
from app.models.bootstrap import load_all_models

# 必须在 import 与实例化任何 mapped class 前完成全量加载
load_all_models()

from app.models.mock import MockMethod, MockRule
from app.models.mock_snapshot import MockRuleSnapshot
from app.schemas.mock import (
    MockRulePromoteSampleRequest,
    MockRuleUpdate,
)


# 让 mr.invalidate_mock_cache 在测试中变 no-op（mr 已 from import 了原函数到自己命名空间）
async def _noop_invalidate(_pid):
    return None


mr.invalidate_mock_cache = _noop_invalidate


def _now():
    return datetime.now(timezone.utc)


def _make_rule(rule_id: int = 7, **overrides) -> MockRule:
    rule = MockRule(
        id=rule_id,
        name="login mock",
        project_id=3,
        method=MockMethod.POST,
        path="/api/login",
        status_code=200,
        response_headers={"Content-Type": "application/json"},
        response_body='{"token":"abc"}',
        match_conditions={"query": {}, "headers": {}, "body": {}},
        delay_ms=0,
        is_enabled=True,
        render_template=False,
        record_requests=True,
        version=3,
        recorded_samples=[
            {
                "timestamp": "2026-05-21T01:02:03+00:00",
                "request": {
                    "query": {"src": "ios"},
                    "headers": {},
                    "body": {"user": "alice"},
                },
                "response": {
                    "status_code": 201,
                    "headers": {"X-Trace": "t1"},
                    "body": '{"id":1}',
                },
            }
        ],
        creator_id=9,
    )
    rule.created_at = _now()
    rule.updated_at = _now()
    for k, v in overrides.items():
        setattr(rule, k, v)
    return rule


class _FakeDB:
    def __init__(self, rule: MockRule, snapshot: MockRuleSnapshot | None = None):
        self.rule = rule
        self.snapshot = snapshot
        self.added: list = []

    async def get(self, model, pk):
        name = getattr(model, "__name__", "")
        if name == "MockRule" and pk == self.rule.id:
            return self.rule
        if name == "MockRuleSnapshot":
            return self.snapshot if (self.snapshot and self.snapshot.id == pk) else None
        return None

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, MockRuleSnapshot) and not obj.id:
            obj.id = 1000 + len(self.added)
        if isinstance(obj, MockRule) and not obj.id:
            obj.id = 2000 + len(self.added)
        if not getattr(obj, "created_at", None):
            obj.created_at = _now()
        if not getattr(obj, "updated_at", None):
            obj.updated_at = _now()

    async def flush(self):
        for obj in self.added:
            if isinstance(obj, MockRuleSnapshot) and not obj.created_at:
                obj.created_at = _now()
                obj.updated_at = _now()

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None


def test_serialize_rule_captures_full_payload():
    rule = _make_rule()
    payload = mr._serialize_rule(rule)
    assert payload["method"] == "POST"
    assert payload["path"] == "/api/login"
    assert payload["status_code"] == 200
    assert payload["response_headers"]["Content-Type"] == "application/json"
    assert payload["version"] == 3


def test_update_mock_rule_writes_snapshot_and_bumps_version():
    load_all_models()
    rule = _make_rule()
    db = _FakeDB(rule)

    body = MockRuleUpdate(response_body='{"token":"xyz"}', delay_ms=100)
    result = asyncio.run(
        mr.update_mock_rule(
            rule_id=rule.id,
            body=body,
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    # 至少有一个 snapshot
    snaps = [o for o in db.added if isinstance(o, MockRuleSnapshot)]
    assert len(snaps) == 1
    assert snaps[0].snapshot_data["response_body"] == '{"token":"abc"}'  # 旧值
    assert snaps[0].version == 3  # 旧版本号
    assert snaps[0].note == "auto on update"

    # 规则字段已变更，版本自增
    assert rule.response_body == '{"token":"xyz"}'
    assert rule.delay_ms == 100
    assert rule.version == 4
    assert result.version == 4


def test_rollback_mock_rule_restores_snapshot_and_bumps_version():
    load_all_models()
    rule = _make_rule()
    # 模拟一个历史快照：旧状态 200/abc
    snap = MockRuleSnapshot(
        id=42,
        rule_id=rule.id,
        version=2,
        snapshot_data={
            "name": "login mock",
            "method": "POST",
            "path": "/api/login",
            "status_code": 500,
            "response_headers": {"X-Legacy": "1"},
            "response_body": '{"err":"legacy"}',
            "match_conditions": {"query": {}, "headers": {}, "body": {}},
            "delay_ms": 10,
            "is_enabled": False,
            "render_template": True,
            "record_requests": False,
        },
        note="auto on update",
        changed_by=9,
    )
    snap.created_at = _now()
    snap.updated_at = _now()
    db = _FakeDB(rule, snapshot=snap)

    result = asyncio.run(
        mr.rollback_mock_rule(
            rule_id=rule.id,
            snapshot_id=42,
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    # 回滚前已写入一份"当前状态"快照
    snaps = [o for o in db.added if isinstance(o, MockRuleSnapshot)]
    assert len(snaps) == 1
    assert snaps[0].note.startswith("before rollback to v2")

    # 规则字段已恢复
    assert rule.status_code == 500
    assert rule.response_body == '{"err":"legacy"}'
    assert rule.is_enabled is False
    assert rule.render_template is True
    assert rule.version == 4  # 3 → 自增 → 4
    assert result.status_code == 500


def test_promote_recorded_sample_creates_new_rule_with_captured_response():
    load_all_models()
    rule = _make_rule()
    db = _FakeDB(rule)

    result = asyncio.run(
        mr.promote_recorded_sample(
            rule_id=rule.id,
            body=MockRulePromoteSampleRequest(sample_index=0, name="from-record"),
            db=db,
            current_user=types.SimpleNamespace(id=9),
        )
    )

    new_rules = [o for o in db.added if isinstance(o, MockRule)]
    assert len(new_rules) == 1
    new_rule = new_rules[0]
    assert new_rule.name == "from-record"
    assert new_rule.project_id == rule.project_id
    assert new_rule.status_code == 201
    assert new_rule.response_body == '{"id":1}'
    assert new_rule.response_headers == {"X-Trace": "t1"}
    assert new_rule.match_conditions["query"] == {"src": "ios"}
    assert new_rule.match_conditions["body"] == {"user": "alice"}
    assert new_rule.is_enabled is True
    assert result.name == "from-record"


def test_promote_recorded_sample_rejects_out_of_range_index():
    load_all_models()
    rule = _make_rule()
    db = _FakeDB(rule)

    from fastapi import HTTPException

    try:
        asyncio.run(
            mr.promote_recorded_sample(
                rule_id=rule.id,
                body=MockRulePromoteSampleRequest(sample_index=99),
                db=db,
                current_user=types.SimpleNamespace(id=9),
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "超出" in exc.detail
        return
    raise AssertionError("应抛 HTTPException 400")
