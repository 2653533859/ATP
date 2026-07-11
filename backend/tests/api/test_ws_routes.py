"""ws.py WebSocket 端点单元测试（Q13 补覆盖：此前 0%）。

AsyncSessionLocal / decode_token / get_async_redis 与 WebSocket 全部 fake；
token 校验、run 订阅授权阶梯（admin/触发者/用例创建者/项目成员/项目 owner）、
以及连接握手→pubsub 转发→completed 主动关闭走真实现。
"""

import asyncio
import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 其它测试可能把 app.core.database / redis_client 换成缺字段的 stub；
# 导入 ws 前补齐它模块级 import 的符号，免疫跨文件 sys.modules 污染。
_db_mod = sys.modules.setdefault("app.core.database", types.SimpleNamespace())
for _name in ("AsyncSessionLocal", "get_db"):
    if not hasattr(_db_mod, _name):
        setattr(_db_mod, _name, lambda *a, **kw: None)

_redis_mod = sys.modules.setdefault("app.core.redis_client", types.SimpleNamespace())
for _name in ("get_async_redis", "publish_run_event"):
    if not hasattr(_redis_mod, _name):
        setattr(_redis_mod, _name, lambda *a, **kw: None)

from app.api.v1 import ws as ws_mod  # noqa: E402
from app.models.bootstrap import load_all_models  # noqa: E402
from app.models.user import UserRole  # noqa: E402

load_all_models()


class _Obj(types.SimpleNamespace):
    def __getattr__(self, name):
        return None


class _FakeResult:
    def __init__(self, value=None, rows=None):
        self._value = value
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, objects=None, execute_results=None):
        self.objects = dict(objects or {})
        self.execute_results = list(execute_results or [])

    async def get(self, model, pk):
        return self.objects.get((model.__name__, pk))

    async def execute(self, _query):
        return self.execute_results.pop(0) if self.execute_results else _FakeResult()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _install_session(monkeypatch, db):
    monkeypatch.setattr(ws_mod, "AsyncSessionLocal", lambda: db)


class _FakeWebSocket:
    def __init__(self, token="tok"):
        self.query_params = {"token": token} if token is not None else {}
        self.accepted = False
        self.closed = None
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def close(self, code=1000, reason=""):
        self.closed = (code, reason)

    async def send_text(self, data):
        self.sent.append(data)


# ── _get_ws_user ────────────────────────────────────────────


def test_get_ws_user_rejects_missing_and_bad_tokens(monkeypatch):
    assert asyncio.run(ws_mod._get_ws_user(_FakeWebSocket(token=None))) is None

    def bad_decode(_t):
        raise ws_mod.InvalidTokenError("bad")

    monkeypatch.setattr(ws_mod, "decode_token", bad_decode)
    assert asyncio.run(ws_mod._get_ws_user(_FakeWebSocket(token="x"))) is None


def test_get_ws_user_rejects_non_access_token(monkeypatch):
    monkeypatch.setattr(ws_mod, "decode_token", lambda _t: {"type": "refresh", "sub": "amy"})
    assert asyncio.run(ws_mod._get_ws_user(_FakeWebSocket())) is None


def test_get_ws_user_rejects_missing_or_inactive_user(monkeypatch):
    monkeypatch.setattr(ws_mod, "decode_token", lambda _t: {"type": "access", "sub": "amy"})

    _install_session(monkeypatch, _FakeDB(execute_results=[_FakeResult(value=None)]))
    assert asyncio.run(ws_mod._get_ws_user(_FakeWebSocket())) is None

    inactive = _Obj(id=1, username="amy", is_active=False)
    _install_session(monkeypatch, _FakeDB(execute_results=[_FakeResult(value=inactive)]))
    assert asyncio.run(ws_mod._get_ws_user(_FakeWebSocket())) is None


def test_get_ws_user_returns_active_user(monkeypatch):
    monkeypatch.setattr(ws_mod, "decode_token", lambda _t: {"type": "access", "sub": "amy"})
    user = _Obj(id=7, username="amy", is_active=True)
    _install_session(monkeypatch, _FakeDB(execute_results=[_FakeResult(value=user)]))

    assert asyncio.run(ws_mod._get_ws_user(_FakeWebSocket())) is user


# ── _can_subscribe_run 授权阶梯 ─────────────────────────────


def _run(run_id=10, triggered_by=None, case_id=1):
    return _Obj(id=run_id, triggered_by=triggered_by, case_id=case_id)


def test_can_subscribe_denies_missing_run(monkeypatch):
    _install_session(monkeypatch, _FakeDB())
    assert asyncio.run(ws_mod._can_subscribe_run(10, _Obj(id=1, role=UserRole.viewer))) is False


def test_can_subscribe_admin_always_allowed(monkeypatch):
    _install_session(monkeypatch, _FakeDB({("TestRun", 10): _run()}))
    assert asyncio.run(ws_mod._can_subscribe_run(10, _Obj(id=1, role=UserRole.admin))) is True


def test_can_subscribe_triggerer_allowed(monkeypatch):
    _install_session(monkeypatch, _FakeDB({("TestRun", 10): _run(triggered_by=7)}))
    assert asyncio.run(ws_mod._can_subscribe_run(10, _Obj(id=7, role=UserRole.viewer))) is True


def test_can_subscribe_case_creator_allowed(monkeypatch):
    db = _FakeDB(
        {("TestRun", 10): _run(triggered_by=99), ("TestCase", 1): _Obj(id=1, creator_id=7, module_id=2)}
    )
    _install_session(monkeypatch, db)
    assert asyncio.run(ws_mod._can_subscribe_run(10, _Obj(id=7, role=UserRole.viewer))) is True


def test_can_subscribe_project_member_allowed(monkeypatch):
    db = _FakeDB(
        {
            ("TestRun", 10): _run(triggered_by=99),
            ("TestCase", 1): _Obj(id=1, creator_id=99, module_id=2),
            ("Module", 2): _Obj(id=2, project_id=5),
        },
        execute_results=[_FakeResult(value=123)],  # membership 命中
    )
    _install_session(monkeypatch, db)
    assert asyncio.run(ws_mod._can_subscribe_run(10, _Obj(id=7, role=UserRole.viewer))) is True


def test_can_subscribe_project_owner_allowed(monkeypatch):
    db = _FakeDB(
        {
            ("TestRun", 10): _run(triggered_by=99),
            ("TestCase", 1): _Obj(id=1, creator_id=99, module_id=2),
            ("Module", 2): _Obj(id=2, project_id=5),
            ("Project", 5): _Obj(id=5, owner_id=7),
        },
        execute_results=[_FakeResult(value=None)],  # 非成员
    )
    _install_session(monkeypatch, db)
    assert asyncio.run(ws_mod._can_subscribe_run(10, _Obj(id=7, role=UserRole.viewer))) is True


def test_can_subscribe_denies_unrelated_user(monkeypatch):
    db = _FakeDB(
        {
            ("TestRun", 10): _run(triggered_by=99),
            ("TestCase", 1): _Obj(id=1, creator_id=99, module_id=2),
            ("Module", 2): _Obj(id=2, project_id=5),
            ("Project", 5): _Obj(id=5, owner_id=99),
        },
        execute_results=[_FakeResult(value=None)],
    )
    _install_session(monkeypatch, db)
    assert asyncio.run(ws_mod._can_subscribe_run(10, _Obj(id=7, role=UserRole.viewer))) is False


def test_can_subscribe_denies_when_case_or_module_missing(monkeypatch):
    # run 存在但 case 缺失 → 拒绝
    _install_session(monkeypatch, _FakeDB({("TestRun", 10): _run(triggered_by=99)}))
    assert asyncio.run(ws_mod._can_subscribe_run(10, _Obj(id=7, role=UserRole.viewer))) is False


# ── ws_run_events 握手与转发 ────────────────────────────────


class _FakePubSub:
    def __init__(self, messages):
        self.messages = list(messages)
        self.subscribed = []
        self.unsubscribed = []

    async def subscribe(self, channel):
        self.subscribed.append(channel)

    async def unsubscribe(self, channel):
        self.unsubscribed.append(channel)

    async def get_message(self, ignore_subscribe_messages=True, timeout=0.1):
        return self.messages.pop(0) if self.messages else None


class _FakeRedis:
    def __init__(self, pubsub):
        self._pubsub = pubsub
        self.closed = False

    def pubsub(self):
        return self._pubsub

    async def aclose(self):
        self.closed = True


def test_ws_run_events_closes_unauthorized(monkeypatch):
    monkeypatch.setattr(ws_mod, "_get_ws_user", _async_return(None))
    socket = _FakeWebSocket()

    asyncio.run(ws_mod.ws_run_events(socket, 10))

    assert socket.accepted is False
    assert socket.closed[0] == 1008 and socket.closed[1] == "Unauthorized"


def test_ws_run_events_closes_forbidden(monkeypatch):
    monkeypatch.setattr(ws_mod, "_get_ws_user", _async_return(_Obj(id=1)))
    monkeypatch.setattr(ws_mod, "_can_subscribe_run", _async_return(False))
    socket = _FakeWebSocket()

    asyncio.run(ws_mod.ws_run_events(socket, 10))

    assert socket.accepted is False
    assert socket.closed[0] == 1008 and socket.closed[1] == "Forbidden"


def test_ws_run_events_streams_until_completed(monkeypatch):
    monkeypatch.setattr(ws_mod, "_get_ws_user", _async_return(_Obj(id=1)))
    monkeypatch.setattr(ws_mod, "_can_subscribe_run", _async_return(True))

    step_msg = {"type": "message", "data": json.dumps({"type": "step_result", "run_id": 10})}
    done_msg = {"type": "message", "data": json.dumps({"type": "completed", "run_id": 10})}
    pubsub = _FakePubSub([step_msg, done_msg])
    redis = _FakeRedis(pubsub)
    monkeypatch.setattr(ws_mod, "get_async_redis", lambda: redis)

    async def fast_sleep(_s):
        return None

    monkeypatch.setattr(ws_mod.asyncio, "sleep", fast_sleep)
    socket = _FakeWebSocket()

    asyncio.run(ws_mod.ws_run_events(socket, 10))

    assert socket.accepted is True
    assert len(socket.sent) == 2  # step + completed 都转发
    assert pubsub.subscribed == ["atp:run:10"]
    assert pubsub.unsubscribed == ["atp:run:10"]  # finally 清理
    assert redis.closed is True
    assert socket.closed is not None


def _async_return(value):
    async def _fn(*_a, **_kw):
        return value

    return _fn
