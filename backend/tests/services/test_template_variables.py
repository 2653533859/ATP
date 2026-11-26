from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime
from types import SimpleNamespace

from app.api.v1.cases import preview as pv
from app.services.template_variables import (
    render_template_string,
    render_template_value,
    resolve_dynamic_variable,
)
from app.worker.executors.api_executor import _render as api_render
from app.worker.executors.api_executor import _render_body_value as api_render_body_value
from app.worker.executors.multiprotocol_executor import render_dict, render_template


def test_resolve_builtin_dynamic_variables():
    parsed_uuid = uuid.UUID(resolve_dynamic_variable("$uuid"))
    assert parsed_uuid.version == 4

    uuid_hex = resolve_dynamic_variable("$uuid_hex")
    assert re.fullmatch(r"[0-9a-f]{32}", uuid_hex)

    ts = resolve_dynamic_variable("$timestamp")
    ts_ms = resolve_dynamic_variable("$timestamp_ms")
    assert isinstance(ts, int) and ts > 1_700_000_000
    assert isinstance(ts_ms, int) and ts_ms >= ts * 1000

    iso_now = resolve_dynamic_variable("$iso_now")
    assert iso_now.endswith("Z")
    datetime.fromisoformat(iso_now.replace("Z", "+00:00"))

    date_str = resolve_dynamic_variable("$date")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str)

    assert isinstance(resolve_dynamic_variable("$random_bool"), bool)
    assert isinstance(resolve_dynamic_variable("$random_name"), str)
    assert re.fullmatch(r"user_[a-z0-9]{8}@example\.com", resolve_dynamic_variable("$random_email"))
    assert re.fullmatch(r"1[3-9]\d{9}", resolve_dynamic_variable("$random_phone"))


def test_resolve_parameterized_dynamic_variables():
    val = resolve_dynamic_variable("$random_int(10, 20)")
    assert isinstance(val, int)
    assert 10 <= val <= 20

    swapped = resolve_dynamic_variable("$random_int(50, 40)")
    assert isinstance(swapped, int)
    assert 40 <= swapped <= 50

    s_len = resolve_dynamic_variable("$random_str(12)")
    assert isinstance(s_len, str)
    assert len(s_len) == 12
    assert s_len.isalnum()

    assert resolve_dynamic_variable("$random_int(abc, 10)") is None
    assert resolve_dynamic_variable("$unknown_fn") is None


def test_render_template_string_precedence_and_unknown_preserved():
    rendered = render_template_string(
        "id={{$uuid}}&tag={{ $random_str(6) }}&token={{token}}&keep={{missing_var}}",
        {"token": "abc-123"},
    )
    assert "token=abc-123" in rendered
    assert "keep={{missing_var}}" in rendered
    assert "{{$uuid}}" not in rendered
    assert "{{ $random_str(6) }}" not in rendered

    overridden = render_template_string("ts={{$timestamp}}", {"$timestamp": "fixed-ts"})
    assert overridden == "ts=fixed-ts"


def test_render_template_value_preserves_types():
    payload = {
        "count": "{{$random_int(5, 5)}}",
        "flag": "{{$random_bool}}",
        "explicit_obj": "{{nested}}",
        "label": "prefix_{{$random_int(1, 3)}}",
        "items": ["{{$timestamp}}", "{{unknown}}"],
    }
    rendered = render_template_value(payload, {"nested": {"a": 1}})
    assert rendered["count"] == 5
    assert isinstance(rendered["count"], int)
    assert isinstance(rendered["flag"], bool)
    assert rendered["explicit_obj"] == {"a": 1}
    assert rendered["label"].startswith("prefix_")
    assert isinstance(rendered["items"][0], int)
    assert rendered["items"][1] == "{{unknown}}"


def test_executors_delegate_dynamic_variables():
    url = api_render("https://example.com/items?req={{$uuid}}&env={{env}}", {"env": "prod"})
    assert "env=prod" in url
    assert "{{$uuid}}" not in url

    body = api_render_body_value({"ts": "{{$timestamp}}", "id": "{{user_id}}"}, {"user_id": 42})
    assert isinstance(body["ts"], int)
    assert body["id"] == 42

    multi_str = render_template("hello {{$random_name}} / {{token}}", {"token": "ok"})
    assert "{{$random_name}}" not in multi_str
    assert multi_str.endswith("/ ok")

    multi_dict = render_dict({"trace": "{{$uuid_hex}}", "keep": 123}, {})
    assert re.fullmatch(r"[0-9a-f]{32}", multi_dict["trace"])
    assert multi_dict["keep"] == 123


def test_random_int_bounds_and_non_str_safety():
    assert resolve_dynamic_variable("$random_int(0, 10000000000000)") is None
    assert resolve_dynamic_variable("$random_int(-10000000000000, 1)") is None
    assert render_template_string(12345, {}) == "12345"  # type: ignore[arg-type]


def test_preview_renders_dynamic_auth_when_effective_vars_empty(monkeypatch):
    monkeypatch.setattr(pv.settings, "ATP_LOCAL_MODE", True)
    monkeypatch.setattr(pv, "validate_public_http_url", lambda v: v)

    async def fake_assert(*_args, **_kwargs):
        return None

    async def fake_vars(*_args, **_kwargs):
        return {}

    async def fake_build(_step, _context, *, headers, params, cookies, project_id):
        return {"headers": headers, "params": params, "cookies": cookies}, object()

    captured = []

    def fake_digest(auth_config, render):
        captured.append(render(auth_config["password"]))
        return ("u", "resolved")

    class _Resp:
        status_code = 200
        reason_phrase = "OK"
        headers = {"content-type": "text/plain"}
        encoding = "utf-8"

        async def aiter_bytes(self, chunk_size=65536):
            yield b"ok"

    class _Stream:
        async def __aenter__(self):
            return _Resp()

        async def __aexit__(self, *_exc):
            return False

    class _Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            return False

        def stream(self, *_args, **_kwargs):
            return _Stream()

    monkeypatch.setattr(pv, "assert_project_access", fake_assert)
    monkeypatch.setattr(pv, "load_global_variables_map", fake_vars)
    monkeypatch.setattr(pv, "_build_request_kwargs", fake_build)
    monkeypatch.setattr(pv, "build_digest_auth", fake_digest)
    monkeypatch.setattr(pv.httpx, "AsyncClient", _Client)

    class _FakeDB:
        async def get(self, *_args, **_kwargs):
            return SimpleNamespace(id=1)

    body = pv.ApiRequestPreviewIn(
        url="https://example.com/probe",
        auth={"type": "digest", "username": "u", "password": "{{$uuid}}"},
    )
    asyncio.run(pv.preview_api_request(project_id=1, body=body, db=_FakeDB(), user=SimpleNamespace(id=1)))
    assert len(captured) == 1
    uuid.UUID(captured[0])
