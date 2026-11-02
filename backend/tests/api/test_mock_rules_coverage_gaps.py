"""补齐 mock_rules.py 的未覆盖分支：AI 生成异常映射、CRUD 成功/404 路径、快照分页与回滚边界。"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.v1 import mock_rules, mock_server
from app.models.bootstrap import load_all_models
from app.models.mock import MockMethod, MockRule
from app.models.mock_snapshot import MockRuleSnapshot
from app.models.user_project import ProjectRole
from app.schemas.mock import (
    MockAIGenerateIn,
    MockRuleCreate,
    MockRulePromoteSampleRequest,
    MockRuleUpdate,
    MockRulesImportRequest,
)

load_all_models()

_NOW = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
_UNSET = object()


class _Rows:
    """db.execute 返回值替身：只实现 scalars().all() 链。"""

    def __init__(self, rows=None):
        self._rows = list(rows or [])

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


class _FakeDB:
    """极简异步会话：get 按模型名走预置映射，execute 顺序弹结果，写操作只记录。"""

    def __init__(self, objects=None, results=None, scalar_value=None, commit_error=None):
        self.objects = dict(objects or {})
        self.results = list(results or [])
        self.scalar_value = scalar_value
        self.commit_error = commit_error
        self.added = []
        self.deleted = []
        self.commits = 0
        self.rollbacks = 0

    async def get(self, model, ident):
        value = self.objects.get(getattr(model, "__name__", model))
        return value(ident) if callable(value) else value

    async def execute(self, _statement):
        return self.results.pop(0) if self.results else _Rows()

    async def scalar(self, _statement):
        return self.scalar_value

    def add(self, value):
        self.added.append(value)

    async def delete(self, value):
        self.deleted.append(value)

    async def commit(self):
        if self.commit_error is not None:
            raise self.commit_error
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def flush(self):
        return None

    async def refresh(self, value):
        if getattr(value, "id", None) is None:
            value.id = 901


def _make_rule(rule_id: int = 21, **overrides) -> MockRule:
    rule = MockRule(
        id=rule_id,
        name="sample rule",
        project_id=5,
        method=MockMethod.GET,
        path="/api/sample",
        status_code=200,
        response_headers={"Content-Type": "application/json"},
        response_body='{"ok":true}',
        match_conditions={"query": {}, "headers": {}, "body": {}},
        delay_ms=0,
        is_enabled=True,
        render_template=False,
        record_requests=False,
        version=2,
        recorded_samples=[],
        creator_id=7,
    )
    rule.created_at = _NOW
    rule.updated_at = _NOW
    for key, value in overrides.items():
        setattr(rule, key, value)
    return rule


def _make_snapshot(
    snapshot_id: int = 31,
    rule_id: int = 21,
    version: int = 1,
    snapshot_data=_UNSET,
) -> MockRuleSnapshot:
    snapshot = MockRuleSnapshot(
        id=snapshot_id,
        rule_id=rule_id,
        version=version,
        snapshot_data={} if snapshot_data is _UNSET else snapshot_data,
        note=None,
        changed_by=7,
    )
    snapshot.created_at = _NOW
    snapshot.updated_at = _NOW
    return snapshot


def _record_invalidate(monkeypatch) -> list:
    calls: list[int] = []

    async def fake_invalidate(project_id: int):
        calls.append(project_id)

    monkeypatch.setattr(mock_rules, "invalidate_mock_cache", fake_invalidate)
    return calls


def _record_assert_project_access(monkeypatch) -> list:
    calls: list = []

    async def fake_assert(_db, _user, project_id, role):
        calls.append((project_id, role))

    monkeypatch.setattr(mock_rules, "assert_project_access", fake_assert)
    return calls


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://llm.local/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=request, response=response)


# ── AI 生成（/mock-rules/ai-generate）────────────────────────────


def test_ai_generate_404_when_project_missing():
    db = _FakeDB()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mock_rules.generate_mock_rules_with_ai(
                body=MockAIGenerateIn(project_id=5),
                db=db,
                current_user=SimpleNamespace(id=7),
            )
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "项目不存在"


def test_ai_generate_400_when_project_has_no_llm_config():
    db = _FakeDB(objects={"Project": SimpleNamespace(id=5, ai_llm_config_id=None)})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mock_rules.generate_mock_rules_with_ai(
                body=MockAIGenerateIn(project_id=5),
                db=db,
                current_user=SimpleNamespace(id=7),
            )
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "项目未配置 AI 模型"


def test_ai_generate_dedupes_rule_ids_and_rejects_missing_reference():
    rules = {8: _make_rule(rule_id=8)}
    db = _FakeDB(
        objects={
            "Project": SimpleNamespace(id=5, ai_llm_config_id=11),
            "MockRule": lambda rule_id: rules.get(rule_id),
        }
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mock_rules.generate_mock_rules_with_ai(
                body=MockAIGenerateIn(project_id=5, rule_ids=[8, 8, 9]),
                db=db,
                current_user=SimpleNamespace(id=7),
            )
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "参考 Mock 规则不存在"


def test_ai_generate_400_when_reference_rule_from_other_project():
    db = _FakeDB(
        objects={
            "Project": SimpleNamespace(id=5, ai_llm_config_id=11),
            "MockRule": lambda rule_id: _make_rule(rule_id=rule_id, project_id=99),
        }
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mock_rules.generate_mock_rules_with_ai(
                body=MockAIGenerateIn(project_id=5, rule_ids=[8]),
                db=db,
                current_user=SimpleNamespace(id=7),
            )
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "参考 Mock 规则不属于当前项目"


def test_ai_generate_400_when_llm_config_missing():
    db = _FakeDB(objects={"Project": SimpleNamespace(id=5, ai_llm_config_id=11)})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mock_rules.generate_mock_rules_with_ai(
                body=MockAIGenerateIn(project_id=5),
                db=db,
                current_user=SimpleNamespace(id=7),
            )
        )
    assert exc.value.status_code == 400
    assert exc.value.detail == "项目关联的 AI 配置不存在"


@pytest.mark.parametrize(
    ("exc_factory", "expected_status", "expected_detail"),
    [
        pytest.param(lambda: httpx.TimeoutException("timeout"), 504, "LLM 请求超时", id="timeout"),
        pytest.param(lambda: _http_status_error(503), 502, "LLM 调用失败: 503", id="status-error"),
        pytest.param(lambda: httpx.RequestError("network down"), 502, "LLM 网络请求失败", id="request-error"),
        pytest.param(lambda: ValueError("bad payload"), 400, "bad payload", id="value-error"),
    ],
)
def test_ai_generate_maps_llm_failures_to_http_status(monkeypatch, exc_factory, expected_status, expected_detail):
    async def fake_generate(**_kwargs):
        raise exc_factory()

    monkeypatch.setattr(mock_rules, "generate_mock_rule_drafts", fake_generate)
    db = _FakeDB(
        objects={
            "Project": SimpleNamespace(id=5, ai_llm_config_id=11),
            "AILLMConfig": SimpleNamespace(id=11),
        }
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mock_rules.generate_mock_rules_with_ai(
                body=MockAIGenerateIn(project_id=5),
                db=db,
                current_user=SimpleNamespace(id=7),
            )
        )
    assert exc.value.status_code == expected_status
    assert exc.value.detail == expected_detail


# ── 规则 CRUD ────────────────────────────────────────────────────


def test_create_mock_rule_success_invalidates_cache(monkeypatch):
    invalidations = _record_invalidate(monkeypatch)
    db = _FakeDB(objects={"Project": SimpleNamespace(id=5)})
    body = MockRuleCreate(name="created", project_id=5, method=MockMethod.POST, path="v1/pay")

    rule = asyncio.run(mock_rules.create_mock_rule(body=body, db=db, current_user=SimpleNamespace(id=7)))

    assert db.commits == 1
    assert rule.id == 901
    assert rule.name == "created"
    assert rule.path == "/v1/pay"
    assert rule.creator_id == 7
    assert invalidations == [5]


def test_create_mock_rule_integrity_error_rolls_back_and_maps_404():
    error = IntegrityError("INSERT INTO mock_rules", {}, Exception("foreign key violation"))
    db = _FakeDB(objects={"Project": SimpleNamespace(id=5)}, commit_error=error)
    body = MockRuleCreate(name="dup", project_id=5, method=MockMethod.GET, path="/dup")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(mock_rules.create_mock_rule(body=body, db=db, current_user=SimpleNamespace(id=7)))

    assert exc.value.status_code == 404
    assert exc.value.detail == "项目不存在"
    assert db.rollbacks == 1


def test_import_mock_rules_404_when_project_missing():
    db = _FakeDB()
    body = MockRulesImportRequest(project_id=5, rules=[])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(mock_rules.import_mock_rules(body=body, db=db, current_user=SimpleNamespace(id=7)))

    assert exc.value.status_code == 404
    assert db.commits == 0


def test_export_mock_rules_returns_project_rules():
    rules = [_make_rule(rule_id=51), _make_rule(rule_id=50)]
    db = _FakeDB(results=[_Rows(rules)])

    result = asyncio.run(mock_rules.export_mock_rules(project_id=5, db=db, _=None))

    assert result.project_id == 5
    assert [rule.id for rule in result.rules] == [51, 50]


def test_list_mock_rules_without_project_filter_skips_access_check(monkeypatch):
    calls = _record_assert_project_access(monkeypatch)
    rule = _make_rule(rule_id=61)
    db = _FakeDB(results=[_Rows([rule])])

    result = asyncio.run(mock_rules.list_mock_rules(project_id=None, db=db, user=SimpleNamespace(id=7, role=None)))

    assert result == [rule]
    assert calls == []


def test_list_mock_rules_with_project_filter_checks_access(monkeypatch):
    calls = _record_assert_project_access(monkeypatch)
    rule = _make_rule(rule_id=62)
    db = _FakeDB(results=[_Rows([rule])])

    result = asyncio.run(mock_rules.list_mock_rules(project_id=5, db=db, user=SimpleNamespace(id=7, role=None)))

    assert result == [rule]
    assert calls == [(5, ProjectRole.viewer)]


def test_list_mock_logs_returns_recorded_entries():
    project_id = 987654
    entry = {
        "method": "GET",
        "path": "/api/sample",
        "matched": True,
        "rule_name": "sample rule",
        "status_code": 200,
        "timestamp": "2026-11-02T10:00:00+00:00",
    }
    mock_server._get_logs(project_id).appendleft(entry)

    assert asyncio.run(mock_rules.list_mock_logs(project_id=project_id, _=None)) == [entry]
    assert asyncio.run(mock_rules.list_mock_logs(project_id=987655, _=None)) == []


def test_get_mock_rule_404_when_missing():
    db = _FakeDB()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(mock_rules.get_mock_rule(rule_id=404, db=db, user=SimpleNamespace(id=7)))

    assert exc.value.status_code == 404
    assert exc.value.detail == "Mock 规则不存在"


def test_get_mock_rule_returns_rule():
    rule = _make_rule(rule_id=71)
    db = _FakeDB(objects={"MockRule": rule})

    result = asyncio.run(mock_rules.get_mock_rule(rule_id=71, db=db, user=SimpleNamespace(id=7)))

    assert result is rule


def test_update_mock_rule_404_when_missing():
    db = _FakeDB()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mock_rules.update_mock_rule(rule_id=404, body=MockRuleUpdate(), db=db, current_user=SimpleNamespace(id=7))
        )

    assert exc.value.status_code == 404


def test_update_mock_rule_with_empty_payload_skips_snapshot(monkeypatch):
    invalidations = _record_invalidate(monkeypatch)
    rule = _make_rule(rule_id=72, version=2)
    db = _FakeDB(objects={"MockRule": rule})

    result = asyncio.run(
        mock_rules.update_mock_rule(rule_id=72, body=MockRuleUpdate(), db=db, current_user=SimpleNamespace(id=7))
    )

    assert result is rule
    assert rule.version == 2
    assert [obj for obj in db.added if isinstance(obj, MockRuleSnapshot)] == []
    assert db.commits == 1
    assert invalidations == [rule.project_id]


def test_delete_mock_rule_404_when_missing():
    db = _FakeDB()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(mock_rules.delete_mock_rule(rule_id=404, db=db, user=SimpleNamespace(id=7)))

    assert exc.value.status_code == 404


def test_delete_mock_rule_removes_and_invalidates(monkeypatch):
    invalidations = _record_invalidate(monkeypatch)
    rule = _make_rule(rule_id=73)
    db = _FakeDB(objects={"MockRule": rule})

    asyncio.run(mock_rules.delete_mock_rule(rule_id=73, db=db, user=SimpleNamespace(id=7)))

    assert db.deleted == [rule]
    assert db.commits == 1
    assert invalidations == [rule.project_id]


# ── 版本快照 / 回滚 / 录制转正式 ─────────────────────────────────


def test_list_snapshots_404_when_rule_missing():
    db = _FakeDB()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mock_rules.list_mock_rule_snapshots(rule_id=404, page=1, page_size=20, db=db, user=SimpleNamespace(id=7))
        )

    assert exc.value.status_code == 404


def test_list_snapshots_paginates_with_zero_total():
    rule = _make_rule(rule_id=74)
    snapshots = [_make_snapshot(snapshot_id=31, rule_id=74, version=2), _make_snapshot(snapshot_id=30, rule_id=74)]
    db = _FakeDB(objects={"MockRule": rule}, scalar_value=None, results=[_Rows(snapshots)])

    result = asyncio.run(
        mock_rules.list_mock_rule_snapshots(rule_id=74, page=2, page_size=10, db=db, user=SimpleNamespace(id=7))
    )

    assert result.total == 0
    assert result.page == 2
    assert result.page_size == 10
    assert [item.version for item in result.items] == [2, 1]


def test_list_snapshots_reports_total_count():
    rule = _make_rule(rule_id=75)
    db = _FakeDB(objects={"MockRule": rule}, scalar_value=4, results=[_Rows([])])

    result = asyncio.run(
        mock_rules.list_mock_rule_snapshots(rule_id=75, page=1, page_size=20, db=db, user=SimpleNamespace(id=7))
    )

    assert result.total == 4
    assert result.items == []


def test_rollback_404_when_rule_missing():
    db = _FakeDB()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mock_rules.rollback_mock_rule(rule_id=404, snapshot_id=1, db=db, current_user=SimpleNamespace(id=7))
        )

    assert exc.value.status_code == 404


def test_rollback_404_when_snapshot_missing():
    rule = _make_rule(rule_id=76)
    db = _FakeDB(objects={"MockRule": rule})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(mock_rules.rollback_mock_rule(rule_id=76, snapshot_id=1, db=db, current_user=SimpleNamespace(id=7)))

    assert exc.value.status_code == 404
    assert exc.value.detail == "快照不存在"


def test_rollback_404_when_snapshot_belongs_to_other_rule():
    rule = _make_rule(rule_id=77)
    snapshot = _make_snapshot(snapshot_id=41, rule_id=78)
    db = _FakeDB(objects={"MockRule": rule, "MockRuleSnapshot": snapshot})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mock_rules.rollback_mock_rule(rule_id=77, snapshot_id=41, db=db, current_user=SimpleNamespace(id=7))
        )

    assert exc.value.status_code == 404


def test_rollback_with_empty_snapshot_data_applies_defaults(monkeypatch):
    invalidations = _record_invalidate(monkeypatch)
    rule = _make_rule(rule_id=79, version=3)
    snapshot = _make_snapshot(snapshot_id=42, rule_id=79, version=1, snapshot_data=None)
    db = _FakeDB(objects={"MockRule": rule, "MockRuleSnapshot": snapshot})

    result = asyncio.run(
        mock_rules.rollback_mock_rule(rule_id=79, snapshot_id=42, db=db, current_user=SimpleNamespace(id=7))
    )

    # 快照缺少字段时保持原值 / 回落到默认值
    assert rule.method == MockMethod.GET
    assert rule.path == "/api/sample"
    assert rule.name == "sample rule"
    assert rule.status_code == 200
    assert rule.response_headers == {}
    assert rule.response_body is None
    assert rule.match_conditions == {}
    assert rule.delay_ms == 0
    assert rule.is_enabled is True
    assert rule.render_template is False
    assert rule.record_requests is False
    assert rule.version == 4

    persisted = [obj for obj in db.added if isinstance(obj, MockRuleSnapshot)]
    assert len(persisted) == 1
    assert persisted[0].note == "before rollback to v1"
    assert invalidations == [rule.project_id]
    assert result is rule


def test_promote_recorded_sample_404_when_rule_missing():
    db = _FakeDB()
    body = MockRulePromoteSampleRequest(sample_index=0)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            mock_rules.promote_recorded_sample(rule_id=404, body=body, db=db, current_user=SimpleNamespace(id=7))
        )

    assert exc.value.status_code == 404
