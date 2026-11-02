"""web_recording_transport.py 覆盖率补测：错误路径、状态映射与路由归属校验。

只覆盖既有 test_web_recording_transport.py 未触及的异常/边界分支：
Redis 工厂缺失与 RuntimeError 包装、注册中心读取失败、心跳写入失败、
会话路由读/写/清理/刷新失败、命令通道超时与无效响应、_transport_error 状态映射、
start 的 busy/not_ready 重试耗尽与元数据保存失败回滚、_route 归属校验、
get/screenshot/stop 的 not_found 清理与非 dict 快照分支、default_worker_id 回退。
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import types

import pytest
from redis.exceptions import RedisError

from app.services import web_recording_transport as transport


class _FakeRedis:
    """最小 Redis 异步替身：支持按操作注入异常并记录写入。"""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.deleted: list[str] = []
        self.expirations: dict[str, int | None] = {}
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.rpush_calls: list[tuple[str, str]] = []
        self.closed = False

        self.scan_keys: list[str] = []
        self.scan_error: Exception | None = None
        self.mget_result: list[str | None] = []
        self.get_error: Exception | None = None
        self.set_error: Exception | None = None
        self.delete_error: Exception | None = None
        self.expire_error: Exception | None = None
        self.expire_result: bool | None = True
        self.rpush_error: Exception | None = None
        self.blpop_error: Exception | None = None
        self.blpop_result: tuple[str, str] | None = None

    async def scan_iter(self, match: str | None = None):
        if self.scan_error is not None:
            raise self.scan_error
        prefix = (match or "").removesuffix("*")
        for key in self.scan_keys:
            if key.startswith(prefix):
                yield key

    async def mget(self, keys):
        return list(self.mget_result)

    async def get(self, key: str):
        if self.get_error is not None:
            raise self.get_error
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        if self.set_error is not None:
            raise self.set_error
        self.values[key] = value
        self.set_calls.append((key, value, ex))
        self.expirations[key] = ex
        return True

    async def delete(self, *keys: str):
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.extend(keys)
        for key in keys:
            self.values.pop(key, None)
        return len(keys)

    async def expire(self, key: str, ttl: int):
        if self.expire_error is not None:
            raise self.expire_error
        self.expirations[key] = ttl
        return self.expire_result

    async def rpush(self, key: str, value: str):
        if self.rpush_error is not None:
            raise self.rpush_error
        self.rpush_calls.append((key, value))
        return 1

    async def blpop(self, key: str, timeout: float | None = None):
        if self.blpop_error is not None:
            raise self.blpop_error
        return self.blpop_result

    async def aclose(self):
        self.closed = True


def _record_closes(monkeypatch) -> list:
    """把 _close_redis 换成记录器，返回被关闭的客户端列表。"""
    closed: list = []

    async def _fake_close(client):
        closed.append(client)

    monkeypatch.setattr(transport, "_close_redis", _fake_close)
    return closed


def _patch_command_redis(monkeypatch, redis: _FakeRedis) -> None:
    """send_recording_command 会以 socket_timeout 关键字调用工厂。"""

    def _factory(_db=2, **_kwargs):
        return redis

    monkeypatch.setattr(transport, "get_async_redis", _factory)


def _patch_manager_route(monkeypatch, metadata, response):
    """替换管理器依赖的会话路由与命令通道，返回 (deleted, calls)。"""
    deleted: list[str] = []
    calls: list[tuple[str, str]] = []

    async def _load(_session_id):
        return metadata

    async def _touch(_session_id):
        return None

    async def _delete(session_id):
        deleted.append(session_id)

    async def _send(worker_id, action, **payload):
        calls.append((worker_id, action))
        return response

    monkeypatch.setattr(transport, "load_session_metadata", _load)
    monkeypatch.setattr(transport, "touch_session_metadata", _touch)
    monkeypatch.setattr(transport, "delete_session_metadata", _delete)
    monkeypatch.setattr(transport, "send_recording_command", _send)
    return deleted, calls


def test_get_async_redis_without_socket_timeout(monkeypatch):
    calls: list[tuple] = []

    def factory(db, **kwargs):
        calls.append((db, kwargs))
        return "client"

    monkeypatch.setattr(transport, "_redis_client", types.SimpleNamespace(get_async_redis=factory))
    assert transport.get_async_redis(2) == "client"
    assert calls == [(2, {})]


def test_get_async_redis_with_socket_timeout(monkeypatch):
    calls: list[tuple] = []

    def factory(db, **kwargs):
        calls.append((db, kwargs))
        return "client"

    monkeypatch.setattr(transport, "_redis_client", types.SimpleNamespace(get_async_redis=factory))
    assert transport.get_async_redis(2, socket_timeout=7) == "client"
    assert calls == [(2, {"socket_timeout": 7})]


def test_get_async_redis_missing_factory(monkeypatch):
    monkeypatch.setattr(transport, "_redis_client", types.SimpleNamespace())
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        transport.get_async_redis()
    assert excinfo.value.detail == "Web 录制 Redis 客户端不可用"
    assert excinfo.value.status_code == 503


def test_get_async_redis_runtime_error_wrapped(monkeypatch):
    def factory(*_args, **_kwargs):
        raise RuntimeError("local mode")

    monkeypatch.setattr(transport, "_redis_client", types.SimpleNamespace(get_async_redis=factory))
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        transport.get_async_redis()
    assert excinfo.value.detail == "Web 录制 Redis 客户端不可用"


def test_close_redis_prefers_module_close(monkeypatch):
    calls: list = []

    async def _fake_close(client):
        calls.append(client)

    monkeypatch.setattr(transport, "_redis_client", types.SimpleNamespace(close_async_redis=_fake_close))
    client = object()
    asyncio.run(transport._close_redis(client))
    assert calls == [client]


def test_close_redis_falls_back_to_aclose(monkeypatch):
    monkeypatch.setattr(transport, "_redis_client", types.SimpleNamespace())
    client = _FakeRedis()
    asyncio.run(transport._close_redis(client))
    assert client.closed is True


def test_close_redis_without_aclose_is_noop(monkeypatch):
    monkeypatch.setattr(transport, "_redis_client", types.SimpleNamespace())
    asyncio.run(transport._close_redis(object()))


def test_prefix_falls_back_to_default(monkeypatch):
    monkeypatch.setattr(transport.settings, "WEB_RECORDER_WORKER_QUEUE_PREFIX", "   ")
    assert transport.worker_key("w1") == "atp:web-recording:commands:workers:w1"
    assert transport.worker_queue_key("w1") == "atp:web-recording:commands:w1"
    assert transport.response_key("r1") == "atp:web-recording:commands:replies:r1"
    assert transport.session_key("s1") == "atp:web-recording:commands:sessions:s1"


def test_list_recording_workers_empty_scan(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    assert asyncio.run(transport.list_recording_workers()) == []
    assert closed == [redis]


def test_list_recording_workers_skips_blank_and_malformed(monkeypatch):
    redis = _FakeRedis()
    redis.scan_keys = [transport.worker_key(name) for name in ("a", "b", "c", "d", "e")]
    redis.mget_result = [
        "",
        "not-json",
        json.dumps(["list"]),
        json.dumps({"worker_id": "   "}),
        json.dumps({"worker_id": "w1", "active_sessions": 0, "capacity": 1}),
    ]
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    workers = asyncio.run(transport.list_recording_workers())
    assert workers == [{"worker_id": "w1", "active_sessions": 0, "capacity": 1}]
    assert closed == [redis]


def test_list_recording_workers_registry_unavailable(monkeypatch):
    redis = _FakeRedis()
    redis.scan_error = RedisError("down")
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.list_recording_workers())
    assert excinfo.value.detail == "录制 Worker 注册中心不可用"
    assert closed == [redis]


def test_available_workers_skips_invalid_counters_and_ids():
    workers = [
        {"worker_id": "bad-active", "active_sessions": "x", "capacity": 2},
        {"worker_id": "bad-capacity", "active_sessions": 0, "capacity": object()},
        {"worker_id": "   ", "active_sessions": 0, "capacity": 1},
        {"worker_id": None, "active_sessions": 0, "capacity": 1},
        {"worker_id": "full", "active_sessions": 3, "capacity": 2},
        {"worker_id": "idle-b", "active_sessions": 0, "capacity": 1},
        {"worker_id": "idle-a", "active_sessions": 0, "capacity": 1},
    ]
    result = transport._available_workers(workers)
    assert [item["worker_id"] for item in result] == ["idle-a", "idle-b"]


def test_choose_recording_worker_empty_registry(monkeypatch):
    monkeypatch.setattr(transport, "list_recording_workers", lambda: asyncio.sleep(0, result=[]))
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.choose_recording_worker())
    assert excinfo.value.detail == "没有可用的 Web 录制 Worker，请先启动独立录制 Worker"
    assert excinfo.value.status_code == 503


def test_register_recording_worker_writes_heartbeat(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(transport.settings, "WEB_RECORDER_WORKER_TTL_SECONDS", 30)
    asyncio.run(transport.register_recording_worker("w1", active_sessions=-4, capacity=0, client=redis))
    assert redis.closed is False  # 注入 client 时由调用方负责关闭
    key, raw, ex = redis.set_calls[0]
    assert key == transport.worker_key("w1")
    assert ex == 30
    payload = json.loads(raw)
    assert payload["worker_id"] == "w1"
    assert payload["active_sessions"] == 0
    assert payload["capacity"] == 1
    assert payload["pid"] == os.getpid()
    assert payload["hostname"] == socket.gethostname()
    assert isinstance(payload["updated_at"], float)


def test_register_recording_worker_owned_client_closed_and_error(monkeypatch):
    redis = _FakeRedis()
    redis.set_error = RedisError("down")
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.register_recording_worker("w1", active_sessions=0, capacity=1))
    assert excinfo.value.detail == "无法写入 Web 录制 Worker 心跳"
    assert closed == [redis]


def test_unregister_recording_worker_injected_client(monkeypatch):
    redis = _FakeRedis()
    asyncio.run(transport.unregister_recording_worker("w1", client=redis))
    assert redis.deleted == [transport.worker_key("w1")]
    assert redis.closed is False


def test_unregister_recording_worker_swallows_redis_error(monkeypatch):
    redis = _FakeRedis()
    redis.delete_error = RedisError("down")
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    asyncio.run(transport.unregister_recording_worker("w1"))
    assert closed == [redis]


def test_save_session_metadata_happy_payload(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    monkeypatch.setattr(transport.settings, "WEB_RECORDER_SESSION_TTL_SECONDS", 10)
    asyncio.run(transport.save_session_metadata("s1", owner_id=1, project_id=2, worker_id="w1"))
    key, raw, ex = redis.set_calls[0]
    assert key == transport.session_key("s1")
    assert ex == 60
    assert json.loads(raw) == {"session_id": "s1", "owner_id": 1, "project_id": 2, "worker_id": "w1"}


def test_save_session_metadata_error_wrapped(monkeypatch):
    redis = _FakeRedis()
    redis.set_error = RedisError("down")
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.save_session_metadata("s1", owner_id=1, project_id=2, worker_id="w1"))
    assert excinfo.value.detail == "无法保存 Web 录制会话路由"
    assert closed == [redis]


def test_save_session_result_error_wrapped(monkeypatch):
    redis = _FakeRedis()
    redis.set_error = RedisError("down")
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.save_session_result("s1", owner_id=1, project_id=2, worker_id="w1", snapshot={"a": 1}))
    assert excinfo.value.detail == "无法保存 Web 录制最终报告"
    assert closed == [redis]


def test_load_session_metadata_missing_returns_none(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    assert asyncio.run(transport.load_session_metadata("s1")) is None
    assert closed == [redis]


def test_load_session_metadata_non_dict_returns_none(monkeypatch):
    redis = _FakeRedis()
    redis.values[transport.session_key("s1")] = json.dumps(["list"])
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    _record_closes(monkeypatch)
    assert asyncio.run(transport.load_session_metadata("s1")) is None


def test_load_session_metadata_invalid_json_returns_none(monkeypatch):
    redis = _FakeRedis()
    redis.values[transport.session_key("s1")] = "{not-json"
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    _record_closes(monkeypatch)
    assert asyncio.run(transport.load_session_metadata("s1")) is None


def test_load_session_metadata_redis_error_wrapped(monkeypatch):
    redis = _FakeRedis()
    redis.get_error = RedisError("down")
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.load_session_metadata("s1"))
    assert excinfo.value.detail == "无法读取 Web 录制会话路由"
    assert closed == [redis]


def test_delete_session_metadata_happy(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    asyncio.run(transport.delete_session_metadata("s1"))
    assert redis.deleted == [transport.session_key("s1")]
    assert closed == [redis]


def test_delete_session_metadata_error_wrapped(monkeypatch):
    redis = _FakeRedis()
    redis.delete_error = RedisError("down")
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.delete_session_metadata("s1"))
    assert excinfo.value.detail == "无法清理 Web 录制会话路由"
    assert closed == [redis]


def test_touch_session_metadata_refresh(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    monkeypatch.setattr(transport.settings, "WEB_RECORDER_SESSION_TTL_SECONDS", 120)
    closed = _record_closes(monkeypatch)
    asyncio.run(transport.touch_session_metadata("s1"))
    assert redis.expirations[transport.session_key("s1")] == 120
    assert closed == [redis]


def test_touch_session_metadata_expired_404(monkeypatch):
    redis = _FakeRedis()
    redis.expire_result = False
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.touch_session_metadata("s1"))
    assert excinfo.value.detail == "录制会话已过期"
    assert excinfo.value.status_code == 404
    assert closed == [redis]


def test_touch_session_metadata_error_wrapped(monkeypatch):
    redis = _FakeRedis()
    redis.expire_error = RedisError("down")
    monkeypatch.setattr(transport, "get_async_redis", lambda: redis)
    closed = _record_closes(monkeypatch)
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.touch_session_metadata("s1"))
    assert excinfo.value.detail == "无法刷新 Web 录制会话路由"
    assert closed == [redis]


def test_send_command_timeout(monkeypatch):
    redis = _FakeRedis()
    redis.blpop_error = asyncio.TimeoutError()
    _patch_command_redis(monkeypatch, redis)
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.send_recording_command("w1", "start"))
    assert excinfo.value.detail == "Web 录制 Worker 响应超时"
    assert redis.rpush_calls and redis.rpush_calls[0][0] == transport.worker_queue_key("w1")
    assert redis.deleted and redis.deleted[0].startswith(f"{transport._prefix()}:replies:")


def test_send_command_missing_result(monkeypatch):
    redis = _FakeRedis()
    redis.blpop_result = None
    _patch_command_redis(monkeypatch, redis)
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.send_recording_command("w1", "snapshot"))
    assert excinfo.value.detail == "Web 录制 Worker 未返回结果"


def test_send_command_invalid_json(monkeypatch):
    redis = _FakeRedis()
    redis.blpop_result = ("reply-key", "{broken")
    _patch_command_redis(monkeypatch, redis)
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.send_recording_command("w1", "snapshot"))
    assert excinfo.value.detail == "Web 录制 Worker 返回了无效响应"


def test_send_command_non_dict_payload(monkeypatch):
    redis = _FakeRedis()
    redis.blpop_result = ("reply-key", json.dumps(["not", "an", "object"]))
    _patch_command_redis(monkeypatch, redis)
    result = asyncio.run(transport.send_recording_command("w1", "snapshot"))
    assert result == {"ok": False, "error": "无效响应"}


def test_send_command_channel_error(monkeypatch):
    redis = _FakeRedis()
    redis.rpush_error = RedisError("down")
    _patch_command_redis(monkeypatch, redis)
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(transport.send_recording_command("w1", "snapshot"))
    assert excinfo.value.detail == "Web 录制 Worker 通道不可用"


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("not_found", 404),
        ("busy", 409),
        ("not_ready", 409),
        ("invalid", 400),
        ("start_failed", 400),
        ("worker_error", 503),
        ("", 503),
        (None, 503),
    ],
)
def test_transport_error_status_mapping(code, status):
    response = {} if code is None else {"code": code}
    error = transport._transport_error(response)
    assert error.status_code == status
    assert error.detail == "Web 录制 Worker 执行失败"


def test_transport_error_prefers_response_message():
    error = transport._transport_error({"code": "busy", "error": "worker 忙"}, fallback="备用文案")
    assert error.detail == "worker 忙"
    assert error.status_code == 409
    fallback_error = transport._transport_error({"error": ""}, fallback="备用文案")
    assert fallback_error.detail == "备用文案"
    assert fallback_error.status_code == 503


def test_manager_start_non_retryable_raises_mapped(monkeypatch):
    async def _choose():
        return {"worker_id": "w1"}

    async def _send(_worker_id, _action, **_payload):
        return {"ok": False, "code": "invalid", "error": "参数错误"}

    async def _trap():
        raise AssertionError("不可重试分支不应再次获取 Worker 列表")

    monkeypatch.setattr(transport, "choose_recording_worker", _choose)
    monkeypatch.setattr(transport, "send_recording_command", _send)
    monkeypatch.setattr(transport, "list_recording_workers", _trap)
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.start({"project_id": 1}, owner_id=7))
    assert excinfo.value.detail == "参数错误"
    assert excinfo.value.status_code == 400


def test_manager_start_busy_candidates_exhausted(monkeypatch):
    async def _choose():
        return {"worker_id": "w1"}

    async def _list():
        return [{"worker_id": "w1", "active_sessions": 0, "capacity": 1}]

    async def _send(_worker_id, _action, **_payload):
        return {"ok": False, "code": "busy", "error": "容量已满"}

    monkeypatch.setattr(transport, "choose_recording_worker", _choose)
    monkeypatch.setattr(transport, "list_recording_workers", _list)
    monkeypatch.setattr(transport, "send_recording_command", _send)
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.start({"project_id": 1}, owner_id=7))
    assert excinfo.value.detail == "容量已满"
    assert excinfo.value.status_code == 409


def test_manager_start_metadata_save_failure_stops_worker(monkeypatch):
    async def _choose():
        return {"worker_id": "w1"}

    calls: list[tuple[str, str]] = []

    async def _send(worker_id, action, **_payload):
        calls.append((worker_id, action))
        if action == "start":
            return {"ok": True, "snapshot": {"session_id": "s1"}}
        return {"ok": True}

    async def _save(*_args, **_kwargs):
        raise transport.WebRecordingTransportError("无法保存 Web 录制会话路由")

    monkeypatch.setattr(transport, "choose_recording_worker", _choose)
    monkeypatch.setattr(transport, "send_recording_command", _send)
    monkeypatch.setattr(transport, "save_session_metadata", _save)
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.start({"project_id": 1}, owner_id=7))
    assert excinfo.value.detail == "无法保存 Web 录制会话路由"
    assert calls == [("w1", "start"), ("w1", "stop")]


def test_route_missing_metadata_404(monkeypatch):
    async def _load(_session_id):
        return None

    monkeypatch.setattr(transport, "load_session_metadata", _load)
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager._route("s1", owner_id=7))
    assert excinfo.value.detail == "录制会话不存在"
    assert excinfo.value.status_code == 404


@pytest.mark.parametrize("owner_value", ["not-an-int", None, [], {}])
def test_route_invalid_owner_404(monkeypatch, owner_value):
    async def _load(_session_id):
        return {"owner_id": owner_value, "worker_id": "w1"}

    monkeypatch.setattr(transport, "load_session_metadata", _load)
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager._route("s1", owner_id=7))
    assert excinfo.value.status_code == 404


def test_route_owner_mismatch_404(monkeypatch):
    async def _load(_session_id):
        return {"owner_id": 8, "worker_id": "w1"}

    monkeypatch.setattr(transport, "load_session_metadata", _load)
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager._route("s1", owner_id=7))
    assert excinfo.value.status_code == 404


def test_route_blank_worker_id_503(monkeypatch):
    async def _load(_session_id):
        return {"owner_id": 7, "worker_id": "   "}

    monkeypatch.setattr(transport, "load_session_metadata", _load)
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager._route("s1", owner_id=7))
    assert excinfo.value.detail == "录制会话路由无效"
    assert excinfo.value.status_code == 503


def test_get_not_found_cleans_route(monkeypatch):
    deleted, calls = _patch_manager_route(
        monkeypatch,
        {"owner_id": 7, "worker_id": "w1", "project_id": 1},
        {"ok": False, "code": "not_found", "error": "会话不存在"},
    )
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.get("s1", owner_id=7))
    assert excinfo.value.detail == "会话不存在"
    assert excinfo.value.status_code == 404
    assert deleted == ["s1"]
    assert calls == [("w1", "snapshot")]


def test_get_unknown_failure_keeps_route_and_uses_fallback(monkeypatch):
    deleted, _calls = _patch_manager_route(
        monkeypatch,
        {"owner_id": 7, "worker_id": "w1", "project_id": 1},
        {"ok": False, "code": "worker_error"},
    )
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.get("s1", owner_id=7))
    assert excinfo.value.detail == "无法读取录制会话"
    assert excinfo.value.status_code == 503
    assert deleted == []


def test_get_non_dict_snapshot_503(monkeypatch):
    _patch_manager_route(
        monkeypatch,
        {"owner_id": 7, "worker_id": "w1", "project_id": 1},
        {"ok": True, "snapshot": ["bad"]},
    )
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.get("s1", owner_id=7))
    assert excinfo.value.detail == "录制会话状态无效"
    assert excinfo.value.status_code == 503


def test_screenshot_finished_session_409(monkeypatch):
    _patch_manager_route(
        monkeypatch,
        {"owner_id": 7, "worker_id": "w1", "project_id": 1, "final_snapshot": {"a": 1}},
        {"ok": True},
    )
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.screenshot("s1", owner_id=7))
    assert excinfo.value.detail == "录制会话已结束，无法继续截图"
    assert excinfo.value.status_code == 409


def test_screenshot_not_found_cleans_route(monkeypatch):
    deleted, _calls = _patch_manager_route(
        monkeypatch,
        {"owner_id": 7, "worker_id": "w1", "project_id": 1},
        {"ok": False, "code": "not_found"},
    )
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.screenshot("s1", owner_id=7))
    assert excinfo.value.detail == "无法截取录制页面"
    assert excinfo.value.status_code == 404
    assert deleted == ["s1"]


def test_screenshot_unknown_failure_keeps_route(monkeypatch):
    deleted, _calls = _patch_manager_route(
        monkeypatch,
        {"owner_id": 7, "worker_id": "w1", "project_id": 1},
        {"ok": False, "code": "busy", "error": "忙"},
    )
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.screenshot("s1", owner_id=7))
    assert excinfo.value.detail == "忙"
    assert excinfo.value.status_code == 409
    assert deleted == []


def test_screenshot_invalid_base64(monkeypatch):
    _patch_manager_route(
        monkeypatch,
        {"owner_id": 7, "worker_id": "w1", "project_id": 1},
        {"ok": True, "data": "not*base64"},
    )
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.screenshot("s1", owner_id=7))
    assert excinfo.value.detail == "录制 Worker 返回了无效截图"
    assert excinfo.value.status_code == 503


def test_stop_returns_cached_final_snapshot(monkeypatch):
    _deleted, calls = _patch_manager_route(
        monkeypatch,
        {"owner_id": 7, "worker_id": "w1", "project_id": 1, "final_snapshot": {"done": True}},
        {"ok": True},
    )
    manager = transport.RemoteWebRecordingManager()
    assert asyncio.run(manager.stop("s1", owner_id=7)) == {"done": True}
    assert calls == []


def test_stop_not_found_cleans_route(monkeypatch):
    deleted, _calls = _patch_manager_route(
        monkeypatch,
        {"owner_id": 7, "worker_id": "w1", "project_id": 1},
        {"ok": False, "code": "not_found"},
    )
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.stop("s1", owner_id=7))
    assert excinfo.value.detail == "无法停止录制会话"
    assert excinfo.value.status_code == 404
    assert deleted == ["s1"]


def test_stop_unknown_failure_keeps_route(monkeypatch):
    deleted, _calls = _patch_manager_route(
        monkeypatch,
        {"owner_id": 7, "worker_id": "w1", "project_id": 1},
        {"ok": False, "code": "invalid", "error": "非法参数"},
    )
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.stop("s1", owner_id=7))
    assert excinfo.value.detail == "非法参数"
    assert excinfo.value.status_code == 400
    assert deleted == []


def test_stop_non_dict_snapshot_503(monkeypatch):
    _patch_manager_route(
        monkeypatch,
        {"owner_id": 7, "worker_id": "w1", "project_id": 1},
        {"ok": True, "snapshot": "bad"},
    )
    manager = transport.RemoteWebRecordingManager()
    with pytest.raises(transport.WebRecordingTransportError) as excinfo:
        asyncio.run(manager.stop("s1", owner_id=7))
    assert excinfo.value.detail == "停止录制未返回会话状态"
    assert excinfo.value.status_code == 503


def test_default_worker_id_prefers_configuration(monkeypatch):
    monkeypatch.setattr(transport.settings, "WEB_RECORDER_WORKER_ID", " configured-worker ")
    assert transport.default_worker_id() == "configured-worker"


def test_default_worker_id_fallback_format(monkeypatch):
    monkeypatch.setattr(transport.settings, "WEB_RECORDER_WORKER_ID", "  ")
    value = transport.default_worker_id()
    assert value.startswith(f"{socket.gethostname()}-{os.getpid()}-")
    token = value.rsplit("-", 1)[1]
    assert len(token) == 8
    int(token, 16)
