"""ai_healing run 级综合诊断与缓存/限额/截图 helper 的单元测试。

与 test_ai_healing.py（step 级 run_diagnosis 三态）互补；本文件聚焦
iter3 的 run_diagnosis_for_run、缓存键、日限额与 vision 输入装载。
"""

import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.models.bootstrap import load_all_models

load_all_models()

import app.core.encryption as encryption_module  # noqa: E402

from app.models.case import RunStatus  # noqa: E402
from app.services import ai_healing  # noqa: E402


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, objects=None, step_rows=None):
        self.objects = dict(objects or {})
        self.step_rows = list(step_rows or [])
        self.commits = 0

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    async def execute(self, _query):
        return _FakeResult(self.step_rows)

    async def commit(self):
        self.commits += 1


# ── 缓存键与缓存读写 ────────────────────────────────────────


def test_make_cache_key_distinguishes_error_signatures():
    base = ai_healing._make_cache_key("api", "登录", "assert a==b", 500)
    assert base == ai_healing._make_cache_key("api", "登录", "assert a==b", 500)
    assert base != ai_healing._make_cache_key("api", "登录", "assert a==b", 404)
    assert base != ai_healing._make_cache_key("web", "登录", "assert a==b", 500)


def test_make_run_cache_key_is_order_insensitive():
    a = ai_healing._make_run_cache_key("api", ["h2", "h1"])
    b = ai_healing._make_run_cache_key("api", ["h1", "h2"])
    assert a == b


def test_cached_suggestion_roundtrip_and_disabled_ttl(monkeypatch):
    store: dict = {}

    async def get_json_cache(key):
        return store.get(key)

    async def set_json_cache(key, value, ttl_seconds=None):
        store[key] = value

    monkeypatch.setattr(sys.modules["app.core.redis_client"], "get_json_cache", get_json_cache, raising=False)
    monkeypatch.setattr(sys.modules["app.core.redis_client"], "set_json_cache", set_json_cache, raising=False)

    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_CACHE_TTL_SECONDS", 600)
    asyncio.run(ai_healing._write_cached_suggestion("k1", "建议"))
    assert asyncio.run(ai_healing._get_cached_suggestion("k1")) == "建议"

    store["bad"] = "not-a-dict"
    assert asyncio.run(ai_healing._get_cached_suggestion("bad")) is None

    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_CACHE_TTL_SECONDS", 0)
    assert asyncio.run(ai_healing._get_cached_suggestion("k1")) is None
    asyncio.run(ai_healing._write_cached_suggestion("k2", "x"))
    assert "k2" not in store


def test_cached_suggestion_swallows_redis_errors(monkeypatch):
    async def broken(*_a, **_kw):
        raise RuntimeError("redis down")

    monkeypatch.setattr(sys.modules["app.core.redis_client"], "get_json_cache", broken, raising=False)
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_CACHE_TTL_SECONDS", 600)

    assert asyncio.run(ai_healing._get_cached_suggestion("k")) is None


# ── 日限额 ──────────────────────────────────────────────────


class _FakeRedis:
    def __init__(self, value):
        self.value = value
        self.expired = []

    async def incr(self, _key):
        return self.value

    async def expire(self, key, ttl):
        self.expired.append((key, ttl))


def _install_redis(monkeypatch, redis):
    async def close_async_redis(_r):
        return None

    monkeypatch.setattr(sys.modules["app.core.redis_client"], "get_async_redis", lambda: redis, raising=False)
    monkeypatch.setattr(sys.modules["app.core.redis_client"], "close_async_redis", close_async_redis, raising=False)


def test_daily_limit_zero_means_unlimited(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_DAILY_LIMIT", 0)
    assert asyncio.run(ai_healing._check_and_incr_daily_limit()) is True


def test_daily_limit_first_call_sets_expire_and_allows(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_DAILY_LIMIT", 5)
    redis = _FakeRedis(value=1)
    _install_redis(monkeypatch, redis)

    assert asyncio.run(ai_healing._check_and_incr_daily_limit()) is True
    assert len(redis.expired) == 1


def test_daily_limit_blocks_when_exceeded_and_degrades_on_error(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_DAILY_LIMIT", 5)
    _install_redis(monkeypatch, _FakeRedis(value=6))
    assert asyncio.run(ai_healing._check_and_incr_daily_limit()) is False

    monkeypatch.setattr(
        sys.modules["app.core.redis_client"],
        "get_async_redis",
        lambda: (_ for _ in ()).throw(RuntimeError("down")),
        raising=False,
    )
    assert asyncio.run(ai_healing._check_and_incr_daily_limit()) is True


def test_vision_daily_limit_mirrors_text_limit(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_VISION_DAILY_LIMIT", 0)
    assert asyncio.run(ai_healing._check_and_incr_vision_daily_limit()) is True

    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_VISION_DAILY_LIMIT", 2)
    _install_redis(monkeypatch, _FakeRedis(value=3))
    assert asyncio.run(ai_healing._check_and_incr_vision_daily_limit()) is False


# ── 截图装载 ────────────────────────────────────────────────


def test_guess_image_media_type():
    assert ai_healing._guess_image_media_type("a.JPG") == "image/jpeg"
    assert ai_healing._guess_image_media_type("b.webp") == "image/webp"
    assert ai_healing._guess_image_media_type("c.png") == "image/png"


def test_load_screenshot_image_for_llm(monkeypatch):
    assert asyncio.run(ai_healing._load_screenshot_image_for_llm(None)) is None

    import app.core.object_refs as object_refs

    monkeypatch.setattr(object_refs, "extract_object_name", lambda url: None)
    assert asyncio.run(ai_healing._load_screenshot_image_for_llm("http://x/none.png")) is None

    monkeypatch.setattr(object_refs, "extract_object_name", lambda url: "shots/a.jpg")
    monkeypatch.setattr(sys.modules["app.core.minio_client"], "read_bytes", lambda name: b"img", raising=False)
    payload = asyncio.run(ai_healing._load_screenshot_image_for_llm("http://x/a.jpg"))
    assert payload == ("aW1n", "image/jpeg")

    monkeypatch.setattr(sys.modules["app.core.minio_client"], "read_bytes", lambda name: b"", raising=False)
    assert asyncio.run(ai_healing._load_screenshot_image_for_llm("http://x/a.jpg")) is None


# ── run 级 hook 与入队 ──────────────────────────────────────


def test_apply_run_healing_hook_threshold_and_pending_state(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_ENABLED", False)
    assert ai_healing.apply_run_healing_hook(_Obj(result_summary={}), 3) is False

    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_ENABLED", True)
    assert ai_healing.apply_run_healing_hook(_Obj(result_summary={}), 1) is False

    run = _Obj(result_summary={"total": 3})
    assert ai_healing.apply_run_healing_hook(run, 2) is True
    assert run.result_summary["healing"]["status"] == "pending"
    assert run.result_summary["total"] == 3


def test_enqueue_helpers_swallow_broker_failures(monkeypatch):
    broken = types.SimpleNamespace(
        diagnose_step_failure=types.SimpleNamespace(delay=lambda *_a: (_ for _ in ()).throw(RuntimeError("broker"))),
        diagnose_run_failure=types.SimpleNamespace(delay=lambda *_a: (_ for _ in ()).throw(RuntimeError("broker"))),
    )
    monkeypatch.setitem(sys.modules, "app.worker.tasks_healing", broken)

    ai_healing.enqueue_diagnosis(1)
    ai_healing.enqueue_run_diagnosis(2)


def test_maybe_enqueue_run_healing_triggers_only_above_threshold(monkeypatch):
    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_ENABLED", True)
    enqueued = []
    monkeypatch.setattr(ai_healing, "enqueue_run_diagnosis", lambda run_id: enqueued.append(run_id))

    run = _Obj(id=9, result_summary={})
    db = _FakeDB(step_rows=[1])  # 仅 1 个失败 step
    asyncio.run(ai_healing.maybe_enqueue_run_healing(db, run))
    assert enqueued == [] and db.commits == 0

    db = _FakeDB(step_rows=[1, 2])
    asyncio.run(ai_healing.maybe_enqueue_run_healing(db, run))
    assert enqueued == [9] and db.commits == 1

    monkeypatch.setattr(ai_healing.settings, "AI_HEALING_ENABLED", False)
    asyncio.run(ai_healing.maybe_enqueue_run_healing(_FakeDB(step_rows=[1, 2]), run))
    assert enqueued == [9]


# ── run_diagnosis_for_run 全三态 ────────────────────────────


def _failed_steps():
    return [
        _Obj(
            id=1,
            step_index=0,
            name="登录",
            status=RunStatus.failed,
            error_message="err-a",
            response_data={"status_code": 500},
        ),
        _Obj(id=2, step_index=1, name="下单", status=RunStatus.error, error_message="err-b", response_data=None),
    ]


def _run_obj(summary=None):
    return _Obj(id=40, case_id=7, result_summary=summary or {})


def _healing_db(run, *, steps=None, config_enabled=True, with_config=True):
    case = _Obj(id=7, name="下单链路", case_type=types.SimpleNamespace(value="api"), module_id=2)
    module = _Obj(id=2, project_id=5)
    project = _Obj(id=5, ai_llm_config_id=11 if with_config else None)
    config = _Obj(
        id=11,
        enabled=config_enabled,
        provider="openai-compatible",
        api_key_encrypted="enc",
        model_name="m",
        endpoint="https://llm",
        default_params=None,
    )
    return _FakeDB(
        objects={
            ("TestRun", 40): run,
            ("TestCase", 7): case,
            ("Module", 2): module,
            ("Project", 5): project,
            ("AILLMConfig", 11): config,
        },
        step_rows=steps if steps is not None else _failed_steps(),
    )


def _install_llm(monkeypatch, *, text="综合诊断", raise_error=None, decrypt_error=None, cached=None, limit_ok=True):
    async def call_llm(request):
        if raise_error:
            raise raise_error
        return types.SimpleNamespace(text=text)

    monkeypatch.setitem(
        sys.modules,
        "app.services.ai_case.llm_client",
        types.SimpleNamespace(LLMRequest=lambda **kw: types.SimpleNamespace(**kw), call_llm=call_llm),
    )

    def decrypt(_v):
        if decrypt_error:
            raise decrypt_error
        return "plain"

    monkeypatch.setattr(encryption_module, "decrypt", decrypt, raising=False)

    async def get_cached(_key):
        return cached

    written = {}

    async def write_cached(key, suggestion):
        written[key] = suggestion

    monkeypatch.setattr(ai_healing, "_get_cached_suggestion", get_cached)
    monkeypatch.setattr(ai_healing, "_write_cached_suggestion", write_cached)

    async def check_limit():
        return limit_ok

    monkeypatch.setattr(ai_healing, "_check_and_incr_daily_limit", check_limit)

    published = []

    async def publish(run_id, payload):
        published.append(payload)

    monkeypatch.setattr(sys.modules["app.core.redis_client"], "publish_run_event", publish, raising=False)
    return written, published


def test_run_diagnosis_for_run_early_returns(monkeypatch):
    _install_llm(monkeypatch)
    asyncio.run(ai_healing.run_diagnosis_for_run(_FakeDB(), 404))  # run 不存在

    run = _run_obj(summary={"healing": {"status": "done"}})
    db = _healing_db(run)
    asyncio.run(ai_healing.run_diagnosis_for_run(db, 40))  # 幂等
    assert db.commits == 0


def test_run_diagnosis_for_run_marks_failed_when_case_missing(monkeypatch):
    _install_llm(monkeypatch)
    run = _run_obj()
    db = _healing_db(run)
    del db.objects[("TestCase", 7)]

    asyncio.run(ai_healing.run_diagnosis_for_run(db, 40))

    assert run.result_summary["healing"]["status"] == "failed"
    assert "case 已删除" in run.result_summary["healing"]["suggestion"]


def test_run_diagnosis_for_run_skips_without_llm_config(monkeypatch):
    _, published = _install_llm(monkeypatch)
    run = _run_obj()
    db = _healing_db(run, with_config=False)

    asyncio.run(ai_healing.run_diagnosis_for_run(db, 40))

    assert run.result_summary["healing"]["status"] == "skipped"
    assert published[-1]["type"] == "run_healing_suggestion"


def test_run_diagnosis_for_run_skips_when_failed_steps_below_threshold(monkeypatch):
    _install_llm(monkeypatch)
    run = _run_obj()
    db = _healing_db(run, steps=[_failed_steps()[0]])

    asyncio.run(ai_healing.run_diagnosis_for_run(db, 40))

    assert run.result_summary["healing"]["status"] == "skipped"


def test_run_diagnosis_for_run_uses_cache_hit(monkeypatch):
    _, published = _install_llm(monkeypatch, cached="缓存结论")
    run = _run_obj()
    db = _healing_db(run)

    asyncio.run(ai_healing.run_diagnosis_for_run(db, 40))

    healing = run.result_summary["healing"]
    assert healing == {"status": "done", "suggestion": "缓存结论", "at": healing["at"], "cache_hit": True}
    assert published[-1]["cache_hit"] is True


def test_run_diagnosis_for_run_respects_daily_limit(monkeypatch):
    _install_llm(monkeypatch, limit_ok=False)
    run = _run_obj()
    db = _healing_db(run)

    asyncio.run(ai_healing.run_diagnosis_for_run(db, 40))

    assert run.result_summary["healing"]["status"] == "skipped"
    assert run.result_summary["healing"]["suggestion"] == "daily-limit-reached"


def test_run_diagnosis_for_run_fails_on_decrypt_error(monkeypatch):
    _install_llm(monkeypatch, decrypt_error=RuntimeError("bad key"))
    run = _run_obj()
    db = _healing_db(run)

    asyncio.run(ai_healing.run_diagnosis_for_run(db, 40))

    assert run.result_summary["healing"]["status"] == "failed"
    assert "解密失败" in run.result_summary["healing"]["suggestion"]


def test_run_diagnosis_for_run_success_writes_cache(monkeypatch):
    written, published = _install_llm(monkeypatch, text="共性根因：环境")
    run = _run_obj()
    db = _healing_db(run)

    asyncio.run(ai_healing.run_diagnosis_for_run(db, 40))

    assert run.result_summary["healing"]["status"] == "done"
    assert run.result_summary["healing"]["suggestion"] == "共性根因：环境"
    assert list(written.values()) == ["共性根因：环境"]
    assert published[-1]["status"] == "done"


def test_run_diagnosis_for_run_marks_llm_failure(monkeypatch):
    _install_llm(monkeypatch, raise_error=RuntimeError("llm down"))
    run = _run_obj()
    db = _healing_db(run)

    asyncio.run(ai_healing.run_diagnosis_for_run(db, 40))

    assert run.result_summary["healing"]["status"] == "failed"
    assert "LLM 调用失败" in run.result_summary["healing"]["suggestion"]


def test_build_run_healing_prompt_lists_steps():
    prompt = ai_healing.build_run_healing_prompt(
        case_type="api", case_name="下单", failed_steps=_failed_steps(), run_summary={"total": 3}
    )

    assert "# 失败步骤数: 2" in prompt
    assert "## 步骤 #1 登录" in prompt
    assert "## 步骤 #2 下单" in prompt
    assert "运行摘要" in prompt
