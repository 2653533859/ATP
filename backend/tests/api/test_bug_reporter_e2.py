"""E.2 缺陷跟踪扩展测试：GitLab Issues + 禅道多产品 override_product_id."""

import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx

from app.services import bug_reporter


# ── 禅道多产品 ─────────────────────────────────────────────


def test_resolve_zentao_product_id_default_when_no_override():
    config = {"product_id": 1, "product_map": {"backend": 2, "frontend": 3}}
    assert bug_reporter._resolve_zentao_product_id(config, None) == 1
    assert bug_reporter._resolve_zentao_product_id(config, "") == 1


def test_resolve_zentao_product_id_uses_map_key():
    config = {"product_id": 1, "product_map": {"backend": 2, "frontend": 3}}
    assert bug_reporter._resolve_zentao_product_id(config, "backend") == 2
    assert bug_reporter._resolve_zentao_product_id(config, "frontend") == 3


def test_resolve_zentao_product_id_passes_through_numeric_string():
    config = {"product_id": 1}
    # 数字字符串：转 int
    assert bug_reporter._resolve_zentao_product_id(config, "42") == 42


def test_resolve_zentao_product_id_passes_through_unknown_string():
    config = {"product_id": 1, "product_map": {}}
    # 非数字、非 map key：原样返回，让禅道侧校验
    assert bug_reporter._resolve_zentao_product_id(config, "unknown_key") == "unknown_key"


# ── GitLab ───────────────────────────────────────────────


def test_gitlab_project_path_url_encodes():
    config = {"project_id": "group/sub/project"}
    encoded = bug_reporter._gitlab_project_path(config)
    assert encoded == "group%2Fsub%2Fproject"


def test_gitlab_project_path_numeric_id():
    config = {"project_id": 1234}
    assert bug_reporter._gitlab_project_path(config) == "1234"


def test_gitlab_apply_field_mapping_joins_labels():
    payload = {}
    bug_reporter._apply_gitlab_field_mapping(payload, {"labels": ["bug", "p1"], "assignee_ids": [1, 2]})
    assert payload["labels"] == "bug,p1"
    assert payload["assignee_ids"] == [1, 2]


def test_gitlab_headers_uses_private_token():
    headers = bug_reporter._gitlab_headers({"token": "glpat-xxx"})
    assert headers["PRIVATE-TOKEN"] == "glpat-xxx"
    assert headers["Content-Type"] == "application/json"


def _make_mock_transport(responses):
    """构造按调用顺序回放的 httpx.MockTransport。"""

    iterator = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        resp = next(iterator)
        return resp

    return httpx.MockTransport(handler)


def test_create_gitlab_issue_returns_bug_id_and_url(monkeypatch):
    config = {
        "base_url": "https://gitlab.example.com",
        "project_id": "group/my-project",
        "token": "glpat-xxx",
    }

    mock_resp = httpx.Response(
        201,
        json={"iid": 42, "web_url": "https://gitlab.example.com/group/my-project/-/issues/42"},
    )

    class _FakeClient:
        def __init__(self, *a, **kw):
            self.last_request = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            self.last_request = (url, json, headers)
            assert "group%2Fmy-project" in url
            assert headers["PRIVATE-TOKEN"] == "glpat-xxx"
            return mock_resp

    monkeypatch.setattr(bug_reporter.httpx, "AsyncClient", _FakeClient)

    result = asyncio.run(bug_reporter._create_gitlab_issue(config, "Bug 1", "desc", {"labels": ["bug"]}))
    assert result["bug_id"] == "42"
    assert result["bug_url"].endswith("/issues/42")
    assert result["title"] == "Bug 1"


def test_create_bug_dispatches_gitlab():
    """create_bug() 入口接受 'gitlab' 类型，不抛 ValueError。"""
    # 验证 dispatch（不真实调用网络）
    import inspect

    src = inspect.getsource(bug_reporter.create_bug)
    assert '"gitlab"' in src
    assert "_create_gitlab_issue" in src


def test_create_bug_passes_override_product_id_to_zentao(monkeypatch):
    captured = {}

    async def fake_zentao_create(config, title, description, field_mapping, override_product_id=None):
        captured["override"] = override_product_id
        return {"bug_id": "100", "bug_url": "...", "title": title}

    monkeypatch.setattr(bug_reporter, "_create_zentao_bug", fake_zentao_create)

    result = asyncio.run(
        bug_reporter.create_bug(
            tracker_type="zentao",
            config={"product_id": 1},
            title="t",
            description="d",
            field_mapping={},
            override_product_id="backend",
        )
    )
    assert captured["override"] == "backend"
    assert result["bug_id"] == "100"
