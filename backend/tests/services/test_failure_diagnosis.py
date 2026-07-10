"""failure_diagnosis 单元测试：规则分类/修复建议/prompt 组装走真实现，
generate_failure_diagnosis 只 fake DB 与 LLM 调用边界。"""

import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.bootstrap import load_all_models

load_all_models()

from app.models.case import RunStatus  # noqa: E402
from app.services import failure_diagnosis as fd  # noqa: E402


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


def _step(idx=0, name="步骤", status=RunStatus.failed, error=None, response=None, screenshot=None, request=None):
    return _Obj(
        step_index=idx,
        name=name,
        status=status,
        error_message=error,
        response_data=response,
        request_data=request,
        screenshot_url=screenshot,
    )


# ── 纯函数 ──────────────────────────────────────────────────


def test_truncate_handles_none_dict_and_long_text():
    assert fd._truncate(None) == ""
    assert fd._truncate({"a": 1}) == '{"a": 1}'
    long = fd._truncate("x" * 2000, limit=10)
    assert long.startswith("xxxxxxxxxx") and long.endswith("...(truncated)")


def test_guess_category_covers_each_failure_family():
    assert "断言" in fd._guess_category("Expected 200 actual 500", False)
    assert "超时" in fd._guess_category("request timed out", False)
    assert "网络" in fd._guess_category("connection refused", False)
    assert "鉴权" in fd._guess_category("401 unauthorized", False)
    assert "不存在" in fd._guess_category("404 not found", False)
    assert "截图" in fd._guess_category("mystery", True)
    assert "日志" in fd._guess_category("mystery", False)


def test_extract_status_code_shapes():
    assert fd._extract_status_code({"status_code": 500}) == 500
    assert fd._extract_status_code({"status": "404"}) == 404
    assert fd._extract_status_code({"code": "abc"}) is None
    assert fd._extract_status_code("not-a-dict") is None


def test_build_repair_suggestions_maps_failure_kinds():
    steps = [
        _step(0, "断言", error="assert expected!=actual"),
        _step(1, "鉴权", response={"status_code": 401}),
        _step(2, "数据", response={"status_code": 404}),
        _step(3, "环境", response={"status_code": 503}),
        _step(4, "其他", error="weird"),
        _step(5, "超出上限", error="ignored"),
    ]

    suggestions = fd.build_repair_suggestions(steps)

    kinds = [s["suggestion_type"] for s in suggestions]
    assert kinds == ["update_assertion", "update_request", "update_request", "investigate_environment", "update_step"]
    assert len(suggestions) == 5  # 上限 5 条
    assert suggestions[1]["evidence"].startswith("status_code=401")
    assert suggestions[0]["confidence"] == 0.78


def test_build_rule_diagnosis_for_pass_and_failure():
    healthy = _Obj(status=RunStatus.passed, steps=[], error_message=None)
    assert "暂无需要诊断" in fd.build_rule_diagnosis(healthy, [])

    run = _Obj(status=RunStatus.failed, error_message=None)
    steps = [_step(2, "登录", error="connection reset", screenshot="s3://x.png")]
    text = fd.build_rule_diagnosis(run, steps)
    assert "网络" in text
    assert "#3 登录" in text
    assert "关联截图 1 张" in text
    assert "connection reset" in text


def test_build_failure_diagnosis_prompt_includes_context_blocks():
    run = _Obj(id=9, status=RunStatus.failed, error_message="run boom")
    case = _Obj(name="下单", case_type=types.SimpleNamespace(value="api"))
    steps = [_step(0, "提交", error="500", request={"m": "POST"}, response={"status_code": 500})]

    prompt = fd.build_failure_diagnosis_prompt(case=case, run=run, failed_steps=steps, fallback_summary="规则摘要")

    assert "run_id: 9" in prompt
    assert "case_type: api" in prompt
    assert "## 失败步骤 #1 提交" in prompt
    assert "规则摘要" in prompt


# ── generate_failure_diagnosis ─────────────────────────────


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    def __init__(self, run=None, objects=None):
        self.run = run
        self.objects = dict(objects or {})
        self.commits = 0

    async def execute(self, _query):
        return _FakeResult(self.run)

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    async def commit(self):
        self.commits += 1


def _failed_run():
    return _Obj(
        id=31,
        case_id=7,
        status=RunStatus.failed,
        error_message="boom",
        steps=[_step(0, "登录", error="assert mismatch")],
        result_summary=None,
    )


def test_generate_failure_diagnosis_returns_none_for_missing_run():
    assert asyncio.run(fd.generate_failure_diagnosis(_FakeDB(run=None), 404)) is None


def test_generate_failure_diagnosis_rule_source_without_llm_config(monkeypatch):
    run = _failed_run()
    db = _FakeDB(run=run, objects={})  # case 缺失 → 无 project → 走规则

    payload = asyncio.run(fd.generate_failure_diagnosis(db, 31))

    assert payload["source"] == "rule"
    assert payload["status"] == "done"
    assert payload["failed_step_count"] == 1
    assert payload["repair_suggestions"][0]["suggestion_type"] == "update_assertion"
    assert run.result_summary["failure_diagnosis"] is payload
    assert db.commits == 1


def _llm_ready_db(run, config_enabled=True):
    case = _Obj(id=7, name="下单", case_type=types.SimpleNamespace(value="api"), module_id=2)
    module = _Obj(id=2, project_id=5)
    project = _Obj(id=5, ai_llm_config_id=11)
    config = _Obj(
        id=11,
        enabled=config_enabled,
        provider="openai-compatible",
        api_key_encrypted="enc",
        model_name="gpt-x",
        endpoint="https://llm",
    )
    return _FakeDB(
        run=run,
        objects={
            ("TestCase", 7): case,
            ("Module", 2): module,
            ("Project", 5): project,
            ("AILLMConfig", 11): config,
        },
    )


def _install_llm(monkeypatch, *, text="LLM 诊断结论", raise_error=None, limit_ok=True):
    async def call_llm(request):
        if raise_error:
            raise raise_error
        return types.SimpleNamespace(text=text)

    monkeypatch.setitem(
        sys.modules,
        "app.services.ai_case.llm_client",
        types.SimpleNamespace(LLMRequest=lambda **kw: types.SimpleNamespace(**kw), call_llm=call_llm),
    )
    monkeypatch.setitem(sys.modules, "app.core.encryption", types.SimpleNamespace(decrypt=lambda v: "plain"))

    async def check_limit(config, capability):
        return limit_ok

    monkeypatch.setattr(fd, "check_and_incr_daily_limit", check_limit)
    monkeypatch.setattr(fd.settings, "AI_HEALING_ENABLED", True)


def test_generate_failure_diagnosis_prefers_llm_text(monkeypatch):
    run = _failed_run()
    db = _llm_ready_db(run)
    _install_llm(monkeypatch, text="根因：断言过期")

    payload = asyncio.run(fd.generate_failure_diagnosis(db, 31))

    assert payload["source"] == "llm"
    assert payload["summary"] == "根因：断言过期"


def test_generate_failure_diagnosis_falls_back_when_llm_fails(monkeypatch):
    run = _failed_run()
    db = _llm_ready_db(run)
    _install_llm(monkeypatch, raise_error=RuntimeError("llm down"))
    monkeypatch.setattr(fd, "fallback_enabled", lambda _config: True)

    payload = asyncio.run(fd.generate_failure_diagnosis(db, 31))

    assert payload["source"] == "rule_fallback"
    assert "最可能原因" in payload["summary"]


def test_generate_failure_diagnosis_reports_llm_error_when_fallback_disabled(monkeypatch):
    run = _failed_run()
    db = _llm_ready_db(run)
    _install_llm(monkeypatch, raise_error=RuntimeError("llm down"))
    monkeypatch.setattr(fd, "fallback_enabled", lambda _config: False)

    payload = asyncio.run(fd.generate_failure_diagnosis(db, 31))

    assert payload["source"] == "rule_fallback"
    assert "LLM 调用失败" in payload["summary"]


def test_generate_failure_diagnosis_daily_limit_counts_as_failure(monkeypatch):
    run = _failed_run()
    db = _llm_ready_db(run)
    _install_llm(monkeypatch, limit_ok=False)
    monkeypatch.setattr(fd, "fallback_enabled", lambda _config: True)

    payload = asyncio.run(fd.generate_failure_diagnosis(db, 31))

    assert payload["source"] == "rule_fallback"


def test_generate_failure_diagnosis_skips_healthy_run():
    run = _Obj(id=32, case_id=7, status=RunStatus.passed, error_message=None, steps=[], result_summary={"k": 1})
    db = _FakeDB(run=run, objects={})

    payload = asyncio.run(fd.generate_failure_diagnosis(db, 32))

    assert payload["status"] == "skipped"
    assert run.result_summary["k"] == 1  # 既有 summary 字段保留
