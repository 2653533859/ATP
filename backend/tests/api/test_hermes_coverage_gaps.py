"""补齐 api/v1/hermes.py 的未覆盖分支：模型规划降级、LLM 兜底、草稿确认各类资源、
会话/反馈边界与只读工具异常路径。"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm.exc import StaleDataError
from starlette.requests import Request

from app.api.v1 import hermes
from app.models.bootstrap import load_all_models
from app.models.defect import Defect, DefectRunLink
from app.models.knowledge import KnowledgeEntry
from app.schemas.hermes import HermesDraftConfirmIn, HermesFeedbackIn, HermesQueryIn
from app.schemas.hermes_orchestration import HermesOrchestrationIn
from app.schemas.hermes_tools import HermesToolCallIn
from app.services.hermes import HermesHistoryContext, HermesRankedSource
from app.services.hermes_orchestration import HermesOrchestrationPlan

load_all_models()

NOW = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
USER = SimpleNamespace(id=7, username="engineer")


class _Result:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def scalars(self):
        return self


class _FakeDB:
    """极简异步会话：get 走模型名映射，execute 顺序消费预置结果。"""

    def __init__(self, objects=None, results=None):
        self.objects = dict(objects or {})
        self.results = list(results or [])
        self.added = []
        self.statements = []

    async def get(self, model, ident):
        value = self.objects.get(getattr(model, "__name__", ""))
        return value(ident) if callable(value) else value

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0) if self.results else _Result()

    async def scalar(self, _statement):
        return None

    def add(self, item):
        if getattr(item, "id", None) is None:
            item.id = 100 + len(self.added)
        self.added.append(item)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None

    async def refresh(self, _item):
        return None


class _PlannerDB:
    """仅供 _try_model_tool_plan 使用的投影/模型配置查询桩。"""

    def __init__(self, project=None, config=None):
        self.project = project
        self.config = config

    async def get(self, model, ident):
        name = getattr(model, "__name__", "")
        if name == "Project":
            return self.project
        if name == "AILLMConfig":
            return self.config
        return None


def _request():
    return Request({"type": "http", "client": ("127.0.0.1", 4173)})


def _session(**kwargs):
    values = {
        "id": 5,
        "project_id": 1,
        "user_id": 7,
        "messages": [],
        "drafts": [],
        "metrics": {},
        "context_filters": {},
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def _install_confirm_stubs(monkeypatch, session):
    async def allow_access(*_args):
        return None

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)
    monkeypatch.setattr(hermes, "_owned_session", AsyncMock(return_value=session))
    monkeypatch.setattr(hermes, "_commit_hermes_state", AsyncMock())


def _confirm(draft_id, db):
    return asyncio.run(
        hermes.confirm_hermes_draft(
            5,
            HermesDraftConfirmIn(project_id=1, draft_id=draft_id, confirmation="CONFIRM"),
            db,
            USER,
        )
    )


def _ranked_source():
    return HermesRankedSource(
        source_type="knowledge",
        source_id=2,
        project_id=1,
        title="登录排查手册",
        excerpt="摘要",
        source_ref="SOP-LOGIN",
        path="/knowledge?project_id=1&knowledge_id=2",
        match_terms=("登录",),
        match_score=3,
        updated_at=NOW,
    )


# ==================== 1. 模型规划器的降级路径 ====================


def test_try_model_tool_plan_falls_back_when_config_missing_or_disabled():
    project = SimpleNamespace(id=1, ai_llm_config_id=8)

    plan, decision = asyncio.run(hermes._try_model_tool_plan(_PlannerDB(project, None), 1, "盘点失败执行"))
    assert plan.status == "no_match"
    assert decision.validation == "unavailable"
    assert decision.fallback_reason == "project_model_unavailable"

    disabled = SimpleNamespace(id=8, enabled=False, model_name="planner-model")
    plan_disabled, decision_disabled = asyncio.run(
        hermes._try_model_tool_plan(_PlannerDB(project, disabled), 1, "盘点失败执行")
    )
    assert plan_disabled.status == "no_match"
    assert decision_disabled.fallback_reason == "project_model_unavailable"


def test_try_model_tool_plan_returns_daily_limit_fallback(monkeypatch):
    async def deny_limit(**_kwargs):
        return False

    monkeypatch.setattr(hermes, "check_and_incr_daily_limit", deny_limit)
    project = SimpleNamespace(id=1, ai_llm_config_id=8)
    config = SimpleNamespace(id=8, enabled=True, model_name="planner-model")

    plan, decision = asyncio.run(hermes._try_model_tool_plan(_PlannerDB(project, config), 1, "盘点失败执行"))

    assert plan.status == "no_match"
    assert decision.validation == "unavailable"
    assert decision.fallback_reason == "daily_limit_reached"
    assert decision.model_name == "planner-model"


def test_try_model_tool_plan_marks_model_call_failure(monkeypatch):
    async def allow_limit(**_kwargs):
        return True

    async def fail_call(_request):
        raise RuntimeError("provider down")

    monkeypatch.setattr(hermes, "check_and_incr_daily_limit", allow_limit)
    monkeypatch.setattr(hermes, "call_llm", fail_call)
    monkeypatch.setattr(hermes, "decrypt", lambda _value: "decrypted-key")

    project = SimpleNamespace(id=1, ai_llm_config_id=8)
    config = SimpleNamespace(
        id=8,
        enabled=True,
        model_name="planner-model",
        provider="openai_compatible",
        api_key_encrypted="enc",
        endpoint=None,
        default_params={},
    )

    plan, decision = asyncio.run(
        hermes._try_model_tool_plan(_PlannerDB(project, config), 1, "帮我盘点近期不成功的执行")
    )

    assert plan.status == "no_match"
    assert decision.validation == "failed"
    assert decision.fallback_reason == "model_call_failed"
    assert decision.model_calls == 1


# ==================== 2. 只读工具执行的异常路径 ====================


def test_execute_hermes_tool_rejects_invalid_arguments(monkeypatch):
    async def allow_access(*_args):
        return None

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            hermes.execute_hermes_tool(
                HermesToolCallIn(project_id=1, conversation_id="hermes-session-1", tool="run_detail"),
                SimpleNamespace(),
                SimpleNamespace(),
                USER,
            )
        )

    assert exc.value.status_code == 422
    assert exc.value.detail == "工具参数无效"


class _AuditDB:
    def __init__(self):
        self.rollback_count = 0
        self.commit_count = 0
        self.refresh_count = 0

    async def rollback(self):
        self.rollback_count += 1

    async def commit(self):
        self.commit_count += 1

    async def refresh(self, _item):
        self.refresh_count += 1


def test_execute_hermes_tool_masks_tool_runtime_errors(monkeypatch):
    audit_calls = []

    async def allow_access(*_args):
        return None

    async def fail_execute(*_args):
        raise RuntimeError("query blew up")

    async def record_audit(_db, **kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)
    monkeypatch.setattr(hermes, "execute_read_tool", fail_execute)
    monkeypatch.setattr(hermes, "write_audit_log", record_audit)

    db = _AuditDB()
    result = asyncio.run(
        hermes.execute_hermes_tool(
            HermesToolCallIn(project_id=1, conversation_id="hermes-session-1", tool="failed_tasks"),
            _request(),
            db,
            USER,
        )
    )

    assert result.status == "error"
    assert result.message == "工具执行失败"
    assert result.data == {}
    assert db.rollback_count == 1
    assert db.commit_count == 1
    assert db.refresh_count == 1
    assert audit_calls and "status=error" in audit_calls[0]["detail"]


# ==================== 3. 编排入口的会话上下文边界 ====================


class _SessionDB:
    def __init__(self, session):
        self.session = session

    async def get(self, model, ident):
        if getattr(model, "__name__", "") == "HermesSession":
            return self.session
        return None

    async def commit(self):
        return None


def test_orchestrate_ignores_session_it_does_not_own(monkeypatch):
    async def allow_access(*_args):
        return None

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)

    result = asyncio.run(
        hermes.orchestrate_hermes(
            HermesOrchestrationIn(project_id=1, query="取消当前查询", conversation_id="hermes-gaps-1", session_id=5),
            SimpleNamespace(),
            _SessionDB(None),
            USER,
        )
    )

    assert result.status == "no_match"
    assert result.session_id is None
    assert result.planner.validation == "not_attempted"


def test_orchestrate_skips_pending_lookup_without_pending_state(monkeypatch):
    async def allow_access(*_args):
        return None

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)
    session = _session(context_filters={"conversation_id": "hermes-gaps-2"})

    result = asyncio.run(
        hermes.orchestrate_hermes(
            HermesOrchestrationIn(project_id=1, query="取消当前查询", conversation_id="hermes-gaps-2", session_id=5),
            SimpleNamespace(),
            _SessionDB(session),
            USER,
        )
    )

    assert result.status == "no_match"
    assert result.session_id is None


# ==================== 4. LLM 回答的兜底与配额 ====================


def test_llm_answer_returns_none_without_enabled_config():
    project = SimpleNamespace(id=1, ai_llm_config_id=5)
    history = HermesHistoryContext(turns=(), chars=0, omitted=0)

    missing_db = _FakeDB(objects={"AILLMConfig": None})
    assert asyncio.run(hermes._llm_answer(missing_db, project, "登录", [_ranked_source()], history)) is None

    disabled_db = _FakeDB(objects={"AILLMConfig": SimpleNamespace(id=5, enabled=False)})
    assert asyncio.run(hermes._llm_answer(disabled_db, project, "登录", [_ranked_source()], history)) is None


def test_llm_answer_returns_none_when_daily_limit_reached(monkeypatch):
    async def deny_limit(**_kwargs):
        return False

    monkeypatch.setattr(hermes, "check_and_incr_daily_limit", deny_limit)
    project = SimpleNamespace(id=1, ai_llm_config_id=5)
    config = SimpleNamespace(
        id=5, enabled=True, provider="ollama", api_key_encrypted="", model_name="m", endpoint=None, default_params={}
    )
    history = HermesHistoryContext(turns=(), chars=0, omitted=0)

    assert (
        asyncio.run(
            hermes._llm_answer(_FakeDB(objects={"AILLMConfig": config}), project, "登录", [_ranked_source()], history)
        )
        is None
    )


def test_chat_llm_answer_skips_disabled_project_config():
    project = SimpleNamespace(id=1, ai_llm_config_id=5)
    db = _FakeDB(objects={"AILLMConfig": SimpleNamespace(id=5, enabled=False)})

    assert asyncio.run(hermes._chat_llm_answer(db, project, "你好", [])) is None


def test_chat_llm_answer_respects_daily_limit(monkeypatch):
    async def deny_limit(**_kwargs):
        return False

    monkeypatch.setattr(hermes, "check_and_incr_daily_limit", deny_limit)
    project = SimpleNamespace(id=1, ai_llm_config_id=5)
    config = SimpleNamespace(
        id=5, enabled=True, provider="ollama", api_key_encrypted="", model_name="m", endpoint=None, default_params={}
    )

    assert (
        asyncio.run(
            hermes._chat_llm_answer(_FakeDB(objects={"AILLMConfig": config}), project, "你好", [("user", "在吗")])
        )
        is None
    )


def test_chat_llm_answer_builds_history_labels(monkeypatch):
    async def allow_limit(**_kwargs):
        return True

    async def fake_call(_request):
        return SimpleNamespace(text="你好呀，我是 Hermes")

    monkeypatch.setattr(hermes, "check_and_incr_daily_limit", allow_limit)
    monkeypatch.setattr(hermes, "call_llm", fake_call)
    project = SimpleNamespace(id=1, ai_llm_config_id=5)
    config = SimpleNamespace(
        id=5, enabled=True, provider="ollama", api_key_encrypted="", model_name="m", endpoint=None, default_params={}
    )

    answer = asyncio.run(
        hermes._chat_llm_answer(
            _FakeDB(objects={"AILLMConfig": config}), project, "在吗", [("user", "你好"), ("assistant", "在的")]
        )
    )

    assert answer == "你好呀，我是 Hermes"


def test_chat_llm_answer_returns_none_on_provider_error(monkeypatch):
    async def allow_limit(**_kwargs):
        return True

    async def fail_call(_request):
        raise RuntimeError("provider down")

    monkeypatch.setattr(hermes, "check_and_incr_daily_limit", allow_limit)
    monkeypatch.setattr(hermes, "call_llm", fail_call)
    project = SimpleNamespace(id=1, ai_llm_config_id=5)
    config = SimpleNamespace(
        id=5, enabled=True, provider="ollama", api_key_encrypted="", model_name="m", endpoint=None, default_params={}
    )

    assert asyncio.run(hermes._chat_llm_answer(_FakeDB(objects={"AILLMConfig": config}), project, "在吗", [])) is None


# ==================== 5. 数值与评估指标的安全边界 ====================


def test_safe_increment_and_metric_float_boundaries():
    assert hermes._safe_increment("abc", 1) == 1
    assert hermes._safe_increment(-4, 2) == 2
    assert hermes._safe_increment(True, 1) == 2
    assert hermes._safe_metric_float(5) == 5.0
    assert hermes._safe_metric_float("2.5") == 2.5
    assert hermes._safe_metric_float("abc") == 0
    assert hermes._safe_metric_float(True) == 0
    assert hermes._safe_metric_float(float("nan")) == 0
    assert hermes._safe_metric_float(-3) == 0


def test_record_evaluation_metrics_ignores_foreign_or_scoresless_payloads():
    session = SimpleNamespace(metrics={})

    hermes._record_evaluation_metrics(
        session,
        {
            "set_id": "other-set",
            "set_version": "x",
            "case_id": "grounded-evidence",
            "scores": {"refusal_correctness": True},
        },
    )
    assert "evaluation_results" not in session.metrics

    hermes._record_evaluation_metrics(
        session,
        {
            "set_id": hermes.HERMES_EVALUATION_SET_ID,
            "set_version": hermes.HERMES_EVALUATION_SET_VERSION,
            "case_id": "grounded-evidence",
            "scores": {"tool_selection": True},
        },
    )
    assert "evaluation_results" not in session.metrics


# ==================== 6. 会话读取的所有权校验 ====================


def test_get_or_create_session_rejects_unowned_session_id():
    body = HermesQueryIn(project_id=1, query="登录", session_id=99)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(hermes._get_or_create_session(_FakeDB(objects={"HermesSession": None}), USER, body))

    assert exc.value.status_code == 404


def test_owned_session_rejects_cross_project_access():
    session = SimpleNamespace(id=5, project_id=2, user_id=7)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(hermes._owned_session(_FakeDB(objects={"HermesSession": session}), USER, 5, 1))

    assert exc.value.status_code == 404


# ==================== 7. 问答端点的兜底项目与时间过滤 ====================


def test_query_hermes_chat_mode_resolves_missing_project_and_uses_history(monkeypatch):
    async def allow_access(*_args):
        return None

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)
    project = SimpleNamespace(id=1, ai_llm_config_id=None)
    db = _FakeDB(objects={"Project": project})

    result = asyncio.run(
        hermes.query_hermes(
            HermesQueryIn(
                query="你好，随便聊聊",
                chat_mode=True,
                history=[{"role": "user", "content": "昨天聊了什么"}],
            ),
            db,
            USER,
        )
    )

    assert result.project_id == 1
    assert result.mode == "free_chat"
    assert result.history_used == 1
    assert "尚未配置可用的大语言模型" in result.answer
    assert db.added and db.added[0].project_id == 1


def test_query_hermes_applies_updated_bounds_to_requirement_and_case_queries(monkeypatch):
    async def allow_access(*_args):
        return None

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)
    project = SimpleNamespace(id=1, name="核心项目", ai_llm_config_id=None)
    db = _FakeDB(objects={"Project": project}, results=[_Result([]), _Result([])])

    result = asyncio.run(
        hermes.query_hermes(
            HermesQueryIn(
                project_id=1,
                query="退款范围说明",
                source_types=["requirement", "case"],
                updated_from="2026-08-01",
                updated_to="2026-08-31",
            ),
            db,
            USER,
        )
    )

    assert result.mode == "no_results"
    assert len(db.statements) == 2
    joined = " ".join(str(statement) for statement in db.statements)
    assert "updated_at" in joined


def test_list_hermes_sessions_returns_user_scoped_sessions(monkeypatch):
    async def allow_access(*_args):
        return None

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)
    db = _FakeDB(results=[_Result([])])

    result = asyncio.run(hermes.list_hermes_sessions(1, db, USER))

    assert result == []
    assert "hermes_sessions.updated_at desc" in str(db.statements[0]).lower()


# ==================== 8. 套件建议的格式校验 ====================


def test_selected_suite_ids_enforces_shape_and_uniqueness():
    assert hermes._selected_suite_ids({}) == []

    with pytest.raises(HTTPException) as invalid_shape:
        hermes._selected_suite_ids({"suiteSuggestions": "bad"})
    assert invalid_shape.value.status_code == 422

    with pytest.raises(HTTPException):
        hermes._selected_suite_ids({"suiteSuggestions": [{"id": index + 1, "selected": True} for index in range(17)]})

    with pytest.raises(HTTPException):
        hermes._selected_suite_ids({"suiteSuggestions": [{"id": True, "selected": True}]})

    with pytest.raises(HTTPException):
        hermes._selected_suite_ids({"suiteSuggestions": [{"id": 0, "selected": True}]})

    with pytest.raises(HTTPException) as duplicate:
        hermes._selected_suite_ids({"suiteSuggestions": [{"id": 3, "selected": True}, {"id": 3, "selected": True}]})
    assert duplicate.value.status_code == 422

    assert hermes._selected_suite_ids(
        {"suiteSuggestions": [{"id": 12, "selected": True}, {"id": 13, "selected": False}, "junk"]}
    ) == [12]


def test_validated_draft_suite_items_short_circuits_without_suggestions():
    assert asyncio.run(hermes._validated_draft_suite_items(SimpleNamespace(), 1, {})) == []


# ==================== 9. 草稿确认的状态守卫与资源落地 ====================


def test_confirm_draft_rejects_unknown_draft_id(monkeypatch):
    session = _session(
        drafts=[{"id": "other", "draft_type": "record", "status": "pending_confirmation", "payload": {}}]
    )
    _install_confirm_stubs(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        _confirm("missing", _FakeDB())

    assert exc.value.status_code == 409
    assert exc.value.detail == "Hermes 草稿不存在"


def test_confirm_draft_rejects_handled_status(monkeypatch):
    session = _session(drafts=[{"id": "d-handled", "draft_type": "record", "status": "rejected", "payload": {}}])
    _install_confirm_stubs(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        _confirm("d-handled", _FakeDB())

    assert exc.value.status_code == 409
    assert exc.value.detail == "Hermes 草稿已处理或不可确认"


def test_confirm_defect_draft_validates_title_and_links_run(monkeypatch):
    session = _session(
        drafts=[
            {
                "id": "d-title",
                "draft_type": "defect",
                "status": "pending_confirmation",
                "payload": {"content": "缺少标题"},
            },
            {
                "id": "d-run",
                "draft_type": "defect",
                "status": "pending_confirmation",
                "payload": {
                    "title": "登录偶现 500",
                    "content": "超时排查",
                    "priority": "P0",
                    "severity": "critical",
                    "run_id": 99,
                },
            },
            {
                "id": "d-plain",
                "draft_type": "defect",
                "status": "pending_confirmation",
                "payload": {"title": "未关联运行的缺陷"},
            },
        ]
    )
    _install_confirm_stubs(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        _confirm("d-title", _FakeDB())
    assert exc.value.status_code == 422
    assert exc.value.detail == "缺陷草稿缺少标题"
    assert session.drafts[0]["status"] == "pending_confirmation"

    db = _FakeDB()
    result = _confirm("d-run", db)
    defect = next(item for item in db.added if isinstance(item, Defect))
    link = next(item for item in db.added if isinstance(item, DefectRunLink))
    assert result["resource_type"] == "defect"
    assert result["resource_id"] == defect.id
    assert defect.priority == "P0"
    assert defect.severity == "critical"
    assert link.defect_id == defect.id
    assert link.run_type == "case"
    assert link.run_id == 99
    assert session.drafts[1]["status"] == "confirmed"

    db_plain = _FakeDB()
    result_plain = _confirm("d-plain", db_plain)
    assert result_plain["resource_type"] == "defect"
    assert not any(isinstance(item, DefectRunLink) for item in db_plain.added)


def test_confirm_knowledge_draft_validates_title_and_content(monkeypatch):
    session = _session(
        drafts=[
            {
                "id": "k-title",
                "draft_type": "knowledge",
                "status": "pending_confirmation",
                "payload": {"content": "有内容"},
            },
            {
                "id": "k-content",
                "draft_type": "knowledge",
                "status": "pending_confirmation",
                "payload": {"title": "规范"},
            },
            {
                "id": "k-ok",
                "draft_type": "knowledge",
                "status": "pending_confirmation",
                "payload": {
                    "title": "连接池优化规范",
                    "content": "参数建议",
                    "source_type": "solution",
                    "tags": ["数据库"],
                },
            },
        ]
    )
    _install_confirm_stubs(monkeypatch, session)

    with pytest.raises(HTTPException) as title_exc:
        _confirm("k-title", _FakeDB())
    assert title_exc.value.status_code == 422
    assert title_exc.value.detail == "知识草稿缺少标题"

    with pytest.raises(HTTPException) as content_exc:
        _confirm("k-content", _FakeDB())
    assert content_exc.value.status_code == 422
    assert content_exc.value.detail == "知识草稿缺少内容"

    db = _FakeDB()
    result = _confirm("k-ok", db)
    entry = next(item for item in db.added if isinstance(item, KnowledgeEntry))
    assert result["resource_type"] == "knowledge"
    assert result["resource_id"] == entry.id
    assert entry.source_type == "solution"
    assert entry.tags == ["数据库"]
    assert entry.status == "draft"
    assert session.drafts[2]["status"] == "confirmed"


def test_confirm_record_draft_handles_missing_target_and_unversioned_payload(monkeypatch):
    case = SimpleNamespace(id=201, module_id=10, config={"original": True}, updated_at=None)
    module = SimpleNamespace(id=10, project_id=1)
    session = _session(
        drafts=[
            {"id": "r-nocase", "draft_type": "repair", "status": "pending_confirmation", "payload": {}},
            {"id": "r-missing", "draft_type": "record", "status": "pending_confirmation", "payload": {"case_id": 999}},
            {"id": "r-ok", "draft_type": "record", "status": "pending_confirmation", "payload": {"case_id": 201}},
        ]
    )
    _install_confirm_stubs(monkeypatch, session)

    with pytest.raises(HTTPException) as missing_case:
        _confirm("r-nocase", _FakeDB())
    assert missing_case.value.status_code == 422
    assert missing_case.value.detail == "用例草稿缺少用例编号"

    objects = {"TestCase": lambda ident: case if ident == 201 else None, "Module": module}
    with pytest.raises(HTTPException) as gone:
        _confirm("r-missing", _FakeDB(objects=objects))
    assert gone.value.status_code == 404
    assert gone.value.detail == "目标用例不存在"

    db = _FakeDB(objects=objects)
    result = _confirm("r-ok", db)
    assert result["resource_type"] == "case"
    assert result["resource_id"] == 201
    assert case.config == {"original": True}
    assert session.drafts[2]["status"] == "confirmed"


def test_confirm_test_plan_draft_requires_name(monkeypatch):
    session = _session(
        drafts=[{"id": "p-noname", "draft_type": "test_plan", "status": "pending_confirmation", "payload": {}}]
    )
    _install_confirm_stubs(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        _confirm("p-noname", _FakeDB())

    assert exc.value.status_code == 422
    assert exc.value.detail == "测试计划草稿缺少名称"


# ==================== 10. 反馈接口的消息守卫 ====================


def test_submit_feedback_rejects_out_of_range_index_and_control_messages(monkeypatch):
    async def allow_access(*_args):
        return None

    session = _session()
    monkeypatch.setattr(hermes, "assert_project_access", allow_access)
    monkeypatch.setattr(hermes, "_owned_session", AsyncMock(return_value=session))
    monkeypatch.setattr(hermes, "_commit_hermes_state", AsyncMock())

    with pytest.raises(HTTPException) as stale:
        asyncio.run(
            hermes.submit_hermes_feedback(
                5,
                HermesFeedbackIn(project_id=1, message_index=0, message_id="a" * 32, rating="helpful"),
                _FakeDB(),
                USER,
            )
        )
    assert stale.value.status_code == 409

    session.messages = [
        {"role": "assistant", "message_id": "b" * 32, "kind": "orchestration_clarification", "content": "请补充编号"}
    ]
    with pytest.raises(HTTPException) as control:
        asyncio.run(
            hermes.submit_hermes_feedback(
                5,
                HermesFeedbackIn(project_id=1, message_index=0, message_id="b" * 32, rating="helpful"),
                _FakeDB(),
                USER,
            )
        )
    assert control.value.status_code == 422
    assert control.value.detail == "只能评价 Hermes 助手消息"


# ==================== 11. 会话提交冲突映射 ====================


class _StaleCommitDB:
    """commit 阶段抛出 StaleDataError 的会话桩，用于校验乐观锁冲突映射。"""

    def __init__(self):
        self.rollback_count = 0

    async def commit(self):
        raise StaleDataError("session state version conflict")

    async def rollback(self):
        self.rollback_count += 1


def test_commit_hermes_state_maps_stale_transition_to_conflict():
    db = _StaleCommitDB()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(hermes._commit_hermes_state(db))

    assert exc.value.status_code == 409
    assert "其他请求中更新" in exc.value.detail
    assert db.rollback_count == 1


# ==================== 12. 规划无 pending 时的陈旧待补充清理 ====================


def test_orchestrate_clears_stale_pending_when_no_pending_is_produced(monkeypatch):
    """needs_input 规划未携带 pending 时，应清理会话中陈旧的待补充快照。"""

    async def allow_access(*_args):
        return None

    def plan_without_pending(_query):
        return HermesOrchestrationPlan(status="needs_input", clarification="请补充要排查的目标编号。")

    monkeypatch.setattr(hermes, "assert_project_access", allow_access)
    monkeypatch.setattr(hermes, "hermes_evaluation_case", lambda *_args: None)
    monkeypatch.setattr(hermes, "plan_read_tools", plan_without_pending)
    session = _session(
        context_filters={
            "conversation_id": "hermes-gaps-3",
            "pending_orchestration": {"tool": "run_detail", "arguments": {"run_id": 9}},
        }
    )

    result = asyncio.run(
        hermes.orchestrate_hermes(
            HermesOrchestrationIn(project_id=1, query="继续排查问题", conversation_id="hermes-gaps-3", session_id=5),
            SimpleNamespace(),
            _SessionDB(session),
            USER,
        )
    )

    assert result.status == "needs_input"
    assert result.session_id == 5
    assert result.message_index == 1
    assert "请补充要排查的目标编号" in result.clarification
    assert "pending_orchestration" not in session.context_filters
    assert session.context_filters["conversation_id"] == "hermes-gaps-3"
