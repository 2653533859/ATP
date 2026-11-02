"""cases/preview.py 未覆盖分支补测：用例编辑器的「发送一次请求」预览端点。

基线（test_cases*.py 合并测量）：preview.py 28%，缺 72 行、36 个分支全缺，
缺行集中在 _validate_preview_url / _validate_fields / preview_api_request。
本文件用 fake DB、fake httpx.AsyncClient 与 monkeypatch 直调被测函数，
不依赖真实 PG/Redis/MinIO/网络，可独立运行。
"""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.api.v1.cases import preview as pv
from app.models.bootstrap import load_all_models
from app.models.project import Project
from app.models.user_project import ProjectRole

load_all_models()

USER = SimpleNamespace(id=5)


@pytest.fixture(autouse=True)
def _no_dns(monkeypatch):
    """默认关闭本地模式并把公网 URL 校验替换为恒等透传，杜绝真实 DNS/网络。"""

    monkeypatch.setattr(pv.settings, "ATP_LOCAL_MODE", False)
    monkeypatch.setattr(pv, "validate_public_http_url", lambda value: value)


class _FakeDB:
    """极简异步会话：get 只服务 Project 查询，返回预置项目或 None。"""

    def __init__(self, project=None):
        self.project = project
        self.get_calls = []

    async def get(self, model, ident):
        self.get_calls.append((model, ident))
        return self.project


class _FakeResponse:
    """httpx.Response 替身：按序产出字节块，携带状态/头部/编码信息。"""

    def __init__(self, chunks=(), status_code=200, reason_phrase="OK", headers=None, encoding="utf-8"):
        self.status_code = status_code
        self.reason_phrase = reason_phrase
        self.headers = dict(headers) if headers is not None else {"content-type": "text/plain"}
        self.encoding = encoding
        self._chunks = list(chunks)

    async def aiter_bytes(self, chunk_size=65536):
        for chunk in self._chunks:
            yield chunk


class _FakeStream:
    """client.stream(...) 的异步上下文替身：可返回响应或注入连接异常。"""

    def __init__(self, response, error):
        self._response = response
        self._error = error

    async def __aenter__(self):
        if self._error is not None:
            raise self._error
        return self._response

    async def __aexit__(self, *_exc):
        return False


def _install_client(monkeypatch, *, response=None, error=None):
    """把 preview 模块引用的 httpx.AsyncClient 换成可注入响应/异常的替身。"""

    class _Client:
        init_kwargs = None
        stream_calls = []

        def __init__(self, **kwargs):
            type(self).init_kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        def stream(self, method, url, **kwargs):
            type(self).stream_calls.append((method, url, kwargs))
            return _FakeStream(response, error)

    monkeypatch.setattr(pv.httpx, "AsyncClient", _Client)
    return _Client


def _patch_access(monkeypatch, *, error=None):
    """替换项目访问断言；返回记录 (db, user, project_id, min_role) 的列表。"""

    recorded = []

    async def fake_assert(db, user, project_id, min_role):
        recorded.append((db, user, project_id, min_role))
        if error is not None:
            raise error

    monkeypatch.setattr(pv, "assert_project_access", fake_assert)
    return recorded


def _patch_build_kwargs(monkeypatch, *, extra=None):
    """替换请求参数构造函数；返回记录调用实参的列表。"""

    recorded = []

    async def fake_build(step, context, *, headers, params, cookies, project_id):
        recorded.append(
            {
                "step": step,
                "context": context,
                "headers": headers,
                "params": params,
                "cookies": cookies,
                "project_id": project_id,
            }
        )
        return dict(extra or {}), object()

    monkeypatch.setattr(pv, "_build_request_kwargs", fake_build)
    return recorded


def _preview_body(**overrides):
    payload = {"url": "https://example.com/a"}
    payload.update(overrides)
    return pv.ApiRequestPreviewIn(**payload)


def _project_db():
    return _FakeDB(SimpleNamespace(id=1))


def _call(body, db, project_id=1):
    """显式传入 db/user 直调端点：不走 Depends，避免默认对象陷阱。"""

    return asyncio.run(pv.preview_api_request(project_id=project_id, body=body, db=db, user=USER))


# ── _validate_preview_url ─────────────────────────────────────────


def test_validate_preview_url_public_mode_delegates(monkeypatch):
    recorded = []

    def fake_public(value):
        recorded.append(value)
        return "https://normalized.example/api"

    monkeypatch.setattr(pv, "validate_public_http_url", fake_public)
    assert pv._validate_preview_url("https://normalized.example/api") == "https://normalized.example/api"
    assert recorded == ["https://normalized.example/api"]


def test_validate_preview_url_local_mode_strips_whitespace(monkeypatch):
    monkeypatch.setattr(pv.settings, "ATP_LOCAL_MODE", True)
    assert pv._validate_preview_url("  https://example.com/a?b=1  ") == "https://example.com/a?b=1"


@pytest.mark.parametrize("value", ["ftp://example.com/file", "https:///missing-host", "https://", "just-text"])
def test_validate_preview_url_local_mode_rejects_bad_scheme_or_host(monkeypatch, value):
    monkeypatch.setattr(pv.settings, "ATP_LOCAL_MODE", True)
    with pytest.raises(ValueError, match="http 或 https"):
        pv._validate_preview_url(value)


def test_validate_preview_url_local_mode_rejects_credentials(monkeypatch):
    monkeypatch.setattr(pv.settings, "ATP_LOCAL_MODE", True)
    with pytest.raises(ValueError, match="用户名或密码"):
        pv._validate_preview_url("https://user:pass@example.com/x")


# ── _validate_fields ──────────────────────────────────────────────


def test_validate_fields_accepts_boundary_limits():
    body = _preview_body(
        headers={f"h{i}": "v" for i in range(100)},
        multipart=[{"name": f"f{i}"} for i in range(50)],
    )
    assert pv._validate_fields(body) is None


def test_validate_fields_rejects_too_many_headers():
    body = _preview_body(headers={f"h{i}": "v" for i in range(101)})
    with pytest.raises(ValueError, match="超出预览限制"):
        pv._validate_fields(body)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"params": {"k" * 257: "v"}}, id="key-too-long"),
        pytest.param({"cookies": {"k": "v" * 8193}}, id="value-too-long"),
    ],
)
def test_validate_fields_rejects_oversized_key_or_value(overrides):
    with pytest.raises(ValueError, match="超出预览限制"):
        pv._validate_fields(_preview_body(**overrides))


def test_validate_fields_rejects_too_many_multipart():
    body = _preview_body(multipart=[{"name": f"f{i}"} for i in range(51)])
    with pytest.raises(ValueError, match="multipart 字段过多"):
        pv._validate_fields(body)


# ── preview_api_request：访问控制与前置校验 ───────────────────────


def test_preview_rejects_when_access_assertion_fails(monkeypatch):
    db = _project_db()
    recorded = _patch_access(monkeypatch, error=HTTPException(status_code=403, detail="无权限"))
    _install_client(monkeypatch, response=_FakeResponse())

    with pytest.raises(HTTPException) as exc_info:
        _call(_preview_body(), db)

    assert exc_info.value.status_code == 403
    assert recorded[0][0] is db
    assert recorded[0][1:] == (USER, 1, ProjectRole.editor)
    assert db.get_calls == []


def test_preview_404_when_project_missing(monkeypatch):
    db = _FakeDB(None)
    _patch_access(monkeypatch)
    _install_client(monkeypatch, response=_FakeResponse())

    with pytest.raises(HTTPException) as exc_info:
        _call(_preview_body(), db)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "项目不存在"
    assert db.get_calls == [(Project, 1)]


def test_preview_field_limit_violation_422(monkeypatch):
    _patch_access(monkeypatch)
    _install_client(monkeypatch, response=_FakeResponse())
    body = _preview_body(headers={f"h{i}": "v" for i in range(101)})

    with pytest.raises(HTTPException) as exc_info:
        _call(body, _project_db())

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "请求头、参数或 Cookie 超出预览限制"


def test_preview_invalid_url_422(monkeypatch):
    monkeypatch.setattr(pv.settings, "ATP_LOCAL_MODE", True)
    _patch_access(monkeypatch)
    _install_client(monkeypatch, response=_FakeResponse())
    body = _preview_body(url="ftp://example.com/file")

    with pytest.raises(HTTPException) as exc_info:
        _call(body, _project_db())

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "地址必须是 http 或 https URL"


def test_preview_unsupported_auth_type_422(monkeypatch):
    _patch_access(monkeypatch)
    _install_client(monkeypatch, response=_FakeResponse())
    body = _preview_body(auth={"type": "saml"})

    with pytest.raises(HTTPException) as exc_info:
        _call(body, _project_db())

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "不支持的认证方式"


# ── preview_api_request：认证分支 ─────────────────────────────────


def test_preview_bearer_auth_success(monkeypatch):
    _patch_access(monkeypatch)
    build_calls = _patch_build_kwargs(monkeypatch, extra={"headers": {"X-Extra": "1"}})
    client_cls = _install_client(
        monkeypatch,
        response=_FakeResponse(
            chunks=[b'{"ok": true}'],
            status_code=201,
            reason_phrase="Created",
            headers={"content-type": "Application/JSON; charset=utf-8", "x-trace": "t1"},
        ),
    )
    body = _preview_body(
        method="POST",
        headers={"X-Base": "v"},
        params={"a": "1"},
        cookies={"c": "d"},
        body_type="json",
        body={"x": 1},
        auth={"type": "bearer", "token": "tk-1"},
    )

    out = _call(body, _project_db())

    assert out.status_code == 201
    assert out.reason == "Created"
    assert out.size_bytes == len(b'{"ok": true}')
    assert out.truncated is False
    assert out.headers == {"content-type": "Application/JSON; charset=utf-8", "x-trace": "t1"}
    assert out.body == '{"ok": true}'
    assert out.duration_ms >= 0
    assert build_calls[0]["project_id"] == 1
    assert build_calls[0]["headers"] == {"X-Base": "v", "Authorization": "Bearer tk-1"}
    assert build_calls[0]["params"] == {"a": "1"}
    assert build_calls[0]["cookies"] == {"c": "d"}
    assert build_calls[0]["step"]["method"] == "POST"
    assert client_cls.init_kwargs == {"timeout": 30, "follow_redirects": False}
    method, url, kwargs = client_cls.stream_calls[0]
    assert (method, url) == ("POST", "https://example.com/a")
    assert kwargs == {"headers": {"X-Extra": "1"}}


def test_preview_basic_auth_sets_httpx_auth(monkeypatch):
    _patch_access(monkeypatch)
    _patch_build_kwargs(monkeypatch, extra={"headers": {}})
    client_cls = _install_client(monkeypatch, response=_FakeResponse(chunks=[b"ok"]))

    out = _call(_preview_body(auth={"type": "basic", "username": "u", "password": "p"}), _project_db())

    assert out.body == "ok"
    _, _, kwargs = client_cls.stream_calls[0]
    assert kwargs["auth"] == ("u", "p")


def test_preview_digest_auth_uses_digest_builder(monkeypatch):
    _patch_access(monkeypatch)
    _patch_build_kwargs(monkeypatch, extra={})
    sentinel = object()
    recorded = []

    def fake_digest(auth_config, render):
        recorded.append((auth_config, render))
        return sentinel

    monkeypatch.setattr(pv, "build_digest_auth", fake_digest)
    client_cls = _install_client(monkeypatch, response=_FakeResponse(chunks=[b"ok"]))
    auth = {"type": "digest", "username": "u", "password": "p"}

    _call(_preview_body(auth=auth), _project_db())

    assert recorded == [(auth, str)]
    _, _, kwargs = client_cls.stream_calls[0]
    assert kwargs["auth"] is sentinel


def test_preview_apikey_blank_header_rejected(monkeypatch):
    _patch_access(monkeypatch)
    _patch_build_kwargs(monkeypatch)
    _install_client(monkeypatch, response=_FakeResponse())
    body = _preview_body(auth={"type": "apikey", "header": "   ", "value": "v"})

    with pytest.raises(HTTPException) as exc_info:
        _call(body, _project_db())

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "API Key 请求头不能为空"


@pytest.mark.parametrize(
    ("auth", "expected"),
    [
        pytest.param({"type": "apikey", "value": "v1"}, {"X-API-Key": "v1"}, id="default-header"),
        pytest.param({"type": "apikey", "header": "X-Token", "value": "v2"}, {"X-Token": "v2"}, id="custom-header"),
    ],
)
def test_preview_apikey_header_injection(monkeypatch, auth, expected):
    _patch_access(monkeypatch)
    build_calls = _patch_build_kwargs(monkeypatch)
    _install_client(monkeypatch, response=_FakeResponse(chunks=[b"ok"]))

    _call(_preview_body(auth=auth), _project_db())

    assert build_calls[0]["headers"] == expected


def test_preview_oauth2_client_credentials(monkeypatch):
    monkeypatch.setattr(pv.settings, "ATP_LOCAL_MODE", True)
    _patch_access(monkeypatch)
    build_calls = _patch_build_kwargs(monkeypatch)
    token_calls = []

    async def fake_resolve(auth_config, render, timeout, cache):
        token_calls.append((auth_config, render, timeout, cache))
        return "Bearer issued-token"

    monkeypatch.setattr(pv, "resolve_oauth2_client_credentials_token", fake_resolve)
    _install_client(monkeypatch, response=_FakeResponse(chunks=[b"ok"]))
    auth = {
        "type": "oauth2_client_credentials",
        "token_url": "https://auth.example.com/token",
        "client_id": "cid",
        "client_secret": "sec",
    }

    _call(_preview_body(auth=auth, timeout=7), _project_db())

    assert build_calls[0]["headers"] == {"Authorization": "Bearer issued-token"}
    assert token_calls[0][0] == auth
    assert token_calls[0][1] is str
    assert token_calls[0][2] == 7.0
    assert token_calls[0][3] == {}


# ── preview_api_request：响应体读取与异常映射 ─────────────────────


def test_preview_truncates_at_byte_limit(monkeypatch):
    monkeypatch.setattr(pv, "MAX_PREVIEW_BYTES", 6)
    _patch_access(monkeypatch)
    _patch_build_kwargs(monkeypatch)
    _install_client(monkeypatch, response=_FakeResponse(chunks=[b"1234", b"567890", b"extra"]))

    out = _call(_preview_body(), _project_db())

    assert out.truncated is True
    assert out.size_bytes == 6
    assert out.body == "123456"


def test_preview_binary_body_masked(monkeypatch):
    _patch_access(monkeypatch)
    _patch_build_kwargs(monkeypatch)
    _install_client(
        monkeypatch,
        response=_FakeResponse(chunks=[b"\x00\x01"], headers={"content-type": "application/octet-stream"}),
    )

    out = _call(_preview_body(), _project_db())

    assert out.body == "[二进制响应，正文未显示]"
    assert out.size_bytes == 2


def test_preview_empty_body_stays_empty(monkeypatch):
    _patch_access(monkeypatch)
    _patch_build_kwargs(monkeypatch)
    _install_client(monkeypatch, response=_FakeResponse(chunks=[], headers={"content-type": "application/json"}))

    out = _call(_preview_body(), _project_db())

    assert out.body == ""
    assert out.size_bytes == 0
    assert out.truncated is False


@pytest.mark.parametrize(
    "encoding",
    [
        pytest.param("", id="missing-encoding-falls-back-to-utf8"),
        pytest.param("not-a-real-codec", id="unknown-encoding-lookup-error"),
    ],
)
def test_preview_encoding_fallback_matrix(monkeypatch, encoding):
    _patch_access(monkeypatch)
    _patch_build_kwargs(monkeypatch)
    _install_client(
        monkeypatch,
        response=_FakeResponse(chunks=[b"hello"], headers={"content-type": "text/plain"}, encoding=encoding),
    )

    out = _call(_preview_body(), _project_db())

    assert out.body == "hello"


@pytest.mark.parametrize(
    "content_type",
    [
        "Application/XML",
        "text/html",
        "application/javascript",
        "text/plain;charset=utf-8",
        "application/json",
    ],
)
def test_preview_readable_content_types_pass_body(monkeypatch, content_type):
    _patch_access(monkeypatch)
    _patch_build_kwargs(monkeypatch)
    _install_client(monkeypatch, response=_FakeResponse(chunks=[b"payload"], headers={"content-type": content_type}))

    out = _call(_preview_body(), _project_db())

    assert out.body == "payload"


def test_preview_timeout_maps_to_504(monkeypatch):
    _patch_access(monkeypatch)
    _patch_build_kwargs(monkeypatch)
    _install_client(monkeypatch, error=httpx.ConnectTimeout("timed out"))

    with pytest.raises(HTTPException) as exc_info:
        _call(_preview_body(), _project_db())

    assert exc_info.value.status_code == 504
    assert exc_info.value.detail == "请求超时"


def test_preview_connection_error_maps_to_502(monkeypatch):
    _patch_access(monkeypatch)
    _patch_build_kwargs(monkeypatch)
    _install_client(monkeypatch, error=httpx.ConnectError("refused"))

    with pytest.raises(HTTPException) as exc_info:
        _call(_preview_body(), _project_db())

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "请求失败：ConnectError"
