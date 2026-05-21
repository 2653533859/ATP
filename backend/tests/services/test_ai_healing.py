"""P3.A ai_healing 单测：prompt 构造 + apply_healing_hook 决策 + run_diagnosis 三态。"""
import asyncio
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.bootstrap import load_all_models

load_all_models()

from app.services import ai_healing
from app.models.case import RunStatus


# ── apply_healing_hook ─────────────────────────────────────────
class _StepStub:
    def __init__(self, status):
        self.status = status
        self.healing_status = None


def test_apply_healing_hook_skips_when_step_passed():
    step = _StepStub(RunStatus.passed)
    assert ai_healing.apply_healing_hook(step) is False
    assert step.healing_status is None


def test_apply_healing_hook_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_ENABLED", False)
    step = _StepStub(RunStatus.failed)
    assert ai_healing.apply_healing_hook(step) is False
    assert step.healing_status == "skipped"


def test_apply_healing_hook_marks_pending_when_enabled(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_ENABLED", True)
    step = _StepStub(RunStatus.error)
    assert ai_healing.apply_healing_hook(step) is True
    assert step.healing_status == "pending"


# ── build_healing_prompt ───────────────────────────────────────
def test_build_healing_prompt_includes_all_sections():
    prompt = ai_healing.build_healing_prompt(
        case_type="api",
        case_name="login flow",
        step_name="POST /login",
        error_message="status_code expected 200 got 401",
        request_data={"method": "POST", "url": "/login"},
        response_data={"status_code": 401, "body": "unauthorized"},
        run_summary={"passed": 0, "failed": 1},
    )
    assert "用例类型: api" in prompt
    assert "login flow" in prompt
    assert "POST /login" in prompt
    assert "401" in prompt
    assert "运行摘要" in prompt
    assert "200 字以内" in prompt


def test_build_healing_prompt_truncates_long_fields():
    big = "x" * 5000
    prompt = ai_healing.build_healing_prompt(
        case_type="web",
        case_name="huge",
        step_name="step",
        error_message=big,
        request_data=None,
        response_data=None,
    )
    assert "truncated" in prompt
    assert len(prompt) < 6000


# ── run_diagnosis: skipped 路径（无 ai_llm_config）──────────────
def _make_async_db(objects: dict[type, dict[int, object]]):
    """轻量假 db：get 按 (cls, id) 查 dict。"""

    class FakeDB:
        async def get(self, cls, pk):
            return objects.get(cls, {}).get(pk)

        async def commit(self):
            pass

    return FakeDB()


def test_run_diagnosis_marks_skipped_when_project_lacks_llm_config(monkeypatch):
    from app.models.case import StepResult, TestRun, TestCase
    from app.models.project import Module, Project

    step = StepResult(
        id=1, run_id=10, step_index=0, name="step",
        status=RunStatus.failed, error_message="boom",
    )
    run = TestRun(id=10, case_id=100)
    case = TestCase(id=100, name="case", module_id=200)
    case.case_type = types.SimpleNamespace(value="api")
    module = Module(id=200, name="m", project_id=300)
    project = Project(id=300, name="p")
    project.ai_llm_config_id = None

    db = _make_async_db({StepResult: {1: step}, TestRun: {10: run},
                         TestCase: {100: case}, Module: {200: module}, Project: {300: project}})

    published = []

    async def fake_publish(rid, payload):
        published.append((rid, payload))

    import app.core.redis_client as redis_mod
    monkeypatch.setattr(redis_mod, "publish_run_event", fake_publish)

    asyncio.run(ai_healing.run_diagnosis(db, 1))

    assert step.healing_status == "skipped"
    assert step.healing_at is not None
    assert published and published[0][1]["status"] == "skipped"


def test_run_diagnosis_is_idempotent_on_done(monkeypatch):
    from app.models.case import StepResult

    step = StepResult(id=2)
    step.healing_status = "done"
    step.healing_suggestion = "already analysed"

    db = _make_async_db({StepResult: {2: step}})

    # 任何 LLM 调用都不应发生
    def boom(*_a, **_kw):
        raise AssertionError("LLM should not be called")

    import app.services.ai_case.llm_client as llm_mod
    monkeypatch.setattr(llm_mod, "call_llm", boom)

    asyncio.run(ai_healing.run_diagnosis(db, 2))
    assert step.healing_suggestion == "already analysed"  # 未被覆盖


# ── 二迭代：缓存 + 日上限 ──────────────────────────────────────
def _build_full_db(step):
    """构造能让 run_diagnosis 走到缓存判定的完整 fake db。"""
    from app.models.ai_llm_config import AILLMConfig
    from app.models.case import StepResult, TestRun, TestCase
    from app.models.project import Module, Project

    run = TestRun(id=step.run_id, case_id=100)
    case = TestCase(id=100, name="case", module_id=200)
    case.case_type = types.SimpleNamespace(value="api")
    module = Module(id=200, name="m", project_id=300)
    project = Project(id=300, name="p")
    project.ai_llm_config_id = 400
    llm_cfg = AILLMConfig(id=400, provider="openai", model_name="gpt-4", api_key_encrypted="x")
    llm_cfg.enabled = True

    return _make_async_db({
        StepResult: {step.id: step},
        TestRun: {step.run_id: run},
        TestCase: {100: case},
        Module: {200: module},
        Project: {300: project},
        AILLMConfig: {400: llm_cfg},
    })


def test_cache_key_is_deterministic_for_same_inputs():
    a = ai_healing._make_cache_key("api", "step1", "boom because X", 401)
    b = ai_healing._make_cache_key("api", "step1", "boom because X", 401)
    assert a == b
    assert a.startswith("ai_healing:cache:")


def test_cache_key_differs_when_error_or_status_differs():
    base = ai_healing._make_cache_key("api", "step1", "err A", 401)
    assert base != ai_healing._make_cache_key("api", "step1", "err B", 401)
    assert base != ai_healing._make_cache_key("api", "step1", "err A", 500)
    assert base != ai_healing._make_cache_key("web", "step1", "err A", 401)


def test_run_diagnosis_uses_cache_and_skips_llm(monkeypatch):
    from app.models.case import StepResult
    import app.services.ai_case.llm_client as llm_mod

    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_CACHE_TTL_SECONDS", 3600)
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_DAILY_LIMIT", 100)

    step = StepResult(
        id=10, run_id=11, step_index=0, name="GET /x",
        status=RunStatus.failed, error_message="boom",
    )
    db = _build_full_db(step)

    async def fake_get(_key):
        return "cached fix: tweak X"  # 替身已解包到字符串

    async def fake_set(*_a, **_kw):
        raise AssertionError("should not write cache on hit")

    def llm_boom(*_a, **_kw):
        raise AssertionError("LLM must not be called on cache hit")

    monkeypatch.setattr(ai_healing, "_get_cached_suggestion", fake_get)
    monkeypatch.setattr(ai_healing, "_write_cached_suggestion", fake_set)
    monkeypatch.setattr(llm_mod, "call_llm", llm_boom)

    published: list = []

    async def fake_publish(rid, payload):
        published.append(payload)

    import app.core.redis_client as redis_mod
    monkeypatch.setattr(redis_mod, "publish_run_event", fake_publish)

    asyncio.run(ai_healing.run_diagnosis(db, 10))

    assert step.healing_status == "done"
    assert step.healing_suggestion == "cached fix: tweak X"
    assert published and published[0]["cache_hit"] is True


def test_run_diagnosis_writes_cache_after_llm_success(monkeypatch):
    from app.models.case import StepResult
    import app.services.ai_case.llm_client as llm_mod

    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_CACHE_TTL_SECONDS", 3600)
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_DAILY_LIMIT", 0)  # 不限

    step = StepResult(
        id=11, run_id=12, step_index=0, name="step",
        status=RunStatus.failed, error_message="bad",
    )
    db = _build_full_db(step)

    # 解密直接放行
    import app.core.encryption as enc
    monkeypatch.setattr(enc, "decrypt", lambda _: "fake-api-key")

    async def fake_get(_key):
        return None  # 未命中

    writes: list[tuple[str, str]] = []

    async def fake_set(key, text):
        writes.append((key, text))

    monkeypatch.setattr(ai_healing, "_get_cached_suggestion", fake_get)
    monkeypatch.setattr(ai_healing, "_write_cached_suggestion", fake_set)

    async def fake_llm(_req):
        return types.SimpleNamespace(text="fresh suggestion from LLM")

    monkeypatch.setattr(llm_mod, "call_llm", fake_llm)

    import app.core.redis_client as redis_mod
    monkeypatch.setattr(redis_mod, "publish_run_event", lambda *_a, **_kw: _async_noop())

    asyncio.run(ai_healing.run_diagnosis(db, 11))

    assert step.healing_status == "done"
    assert step.healing_suggestion == "fresh suggestion from LLM"
    assert writes and writes[0][1] == "fresh suggestion from LLM"


async def _async_noop(*_a, **_kw):
    return None


def test_run_diagnosis_skipped_when_daily_limit_exceeded(monkeypatch):
    from app.models.case import StepResult
    import app.services.ai_case.llm_client as llm_mod

    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_CACHE_TTL_SECONDS", 0)  # 关缓存
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_DAILY_LIMIT", 5)

    step = StepResult(
        id=20, run_id=21, step_index=0, name="step",
        status=RunStatus.failed, error_message="bad",
    )
    db = _build_full_db(step)

    async def at_limit():
        return False  # 模拟超限

    monkeypatch.setattr(ai_healing, "_check_and_incr_daily_limit", at_limit)

    def boom(*_a, **_kw):
        raise AssertionError("LLM must not be called when over limit")

    monkeypatch.setattr(llm_mod, "call_llm", boom)

    published: list = []

    async def fake_publish(rid, payload):
        published.append(payload)

    import app.core.redis_client as redis_mod
    monkeypatch.setattr(redis_mod, "publish_run_event", fake_publish)

    asyncio.run(ai_healing.run_diagnosis(db, 20))

    assert step.healing_status == "skipped"
    assert step.healing_suggestion == "daily-limit-reached"
    assert published and published[0]["status"] == "skipped"


def test_daily_limit_zero_means_no_limit(monkeypatch):
    """AI_HEALING_DAILY_LIMIT=0 时不查 Redis 直接放行。"""
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_DAILY_LIMIT", 0)

    # 即使 Redis 模块缺 get_async_redis（被前置测试 stub 成精简版），也不应触发任何调用
    import app.core.redis_client as redis_mod

    def boom(*_a, **_kw):
        raise AssertionError("Redis must not be touched when limit=0")

    monkeypatch.setattr(redis_mod, "get_async_redis", boom, raising=False)

    allowed = asyncio.run(ai_healing._check_and_incr_daily_limit())
    assert allowed is True


# ── iter3 多 step 综合诊断 ─────────────────────────────────────
class _RunStub:
    def __init__(self, summary=None):
        self.id = 7000
        self.case_id = 100
        self.result_summary = summary


def test_apply_run_healing_hook_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_ENABLED", False)
    run = _RunStub()
    assert ai_healing.apply_run_healing_hook(run, 5) is False
    assert run.result_summary is None


def test_apply_run_healing_hook_skips_when_too_few_failures(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_ENABLED", True)
    run = _RunStub()
    assert ai_healing.apply_run_healing_hook(run, 1) is False
    assert run.result_summary is None


def test_apply_run_healing_hook_marks_pending_when_threshold_met(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_ENABLED", True)
    run = _RunStub(summary={"video_url": "vid"})
    assert ai_healing.apply_run_healing_hook(run, 2) is True
    assert run.result_summary["healing"]["status"] == "pending"
    assert run.result_summary["video_url"] == "vid"  # 不覆盖原字段


def test_run_cache_key_is_order_independent():
    a = ai_healing._make_run_cache_key("api", ["hash-1", "hash-2", "hash-3"])
    b = ai_healing._make_run_cache_key("api", ["hash-3", "hash-1", "hash-2"])
    assert a == b


def test_build_run_healing_prompt_lists_all_failed_steps():
    from app.models.case import StepResult

    steps = [
        StepResult(id=1, step_index=0, name="登录", error_message="401"),
        StepResult(id=2, step_index=1, name="查询", error_message="timeout"),
    ]
    prompt = ai_healing.build_run_healing_prompt(
        case_type="api", case_name="冒烟", failed_steps=steps,
    )
    assert "失败步骤数: 2" in prompt
    assert "登录" in prompt and "查询" in prompt
    assert "401" in prompt and "timeout" in prompt
    assert "300 字以内" in prompt
