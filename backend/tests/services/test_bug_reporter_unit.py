"""bug_reporter 单元缝测试：只 fake httpx.AsyncClient，四个平台的
payload 组装、鉴权、去重匹配与错误路径全部走真实现。"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services import bug_reporter


class _FakeResponse:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body
        self.text = text or (str(body) if body is not None else "")

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


class _FakeAsyncClient:
    script: list = []
    requests: list = []

    def __init__(self, timeout=None):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def _call(self, method, url, **kwargs):
        _FakeAsyncClient.requests.append({"method": method, "url": url, **kwargs})
        item = _FakeAsyncClient.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def get(self, url, **kwargs):
        return await self._call("GET", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self._call("POST", url, **kwargs)


@pytest.fixture()
def fake_http(monkeypatch):
    _FakeAsyncClient.script = []
    _FakeAsyncClient.requests = []
    monkeypatch.setattr(bug_reporter.httpx, "AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient


_JIRA = {"base_url": "https://jira.example.com/", "email": "qa@x.com", "api_token": "tok", "project_key": "ATP"}
_ZENTAO = {"base_url": "https://zentao.example.com", "account": "qa", "password": "pw", "product_id": 3}
_GITHUB = {"token": "gh-tok", "owner": "acme", "repo": "atp"}
_GITLAB = {"token": "gl-tok", "project_id": "group/atp"}


# ── 分发层 ──────────────────────────────────────────────────


def test_dispatch_rejects_unknown_tracker_types():
    with pytest.raises(ValueError, match="不支持"):
        asyncio.run(bug_reporter.create_bug("mantis", {}, "t", "d"))
    with pytest.raises(ValueError, match="不支持"):
        asyncio.run(bug_reporter.test_connection("mantis", {}))
    with pytest.raises(ValueError, match="不支持"):
        asyncio.run(bug_reporter.get_bug_status("mantis", {}, "1"))
    assert asyncio.run(bug_reporter.find_duplicate_bug("mantis", {}, "t")) is None


def test_upload_attachment_short_circuits():
    assert asyncio.run(bug_reporter.upload_attachment("jira", {}, "1", "a.png", b"")) is False
    assert asyncio.run(bug_reporter.upload_attachment("github", {}, "1", "a.png", b"x")) is False


# ── 纯函数 ──────────────────────────────────────────────────


def test_escape_jira_jql_value_neutralizes_metacharacters():
    assert bug_reporter._escape_jira_jql_value('a"b\\c\nd\re') == 'a\\"b\\\\c d e'


def test_apply_jira_field_mapping_builds_structured_fields():
    fields: dict = {}
    bug_reporter._apply_jira_field_mapping(
        fields,
        {"priority": "High", "labels": ["atp"], "components": ["api"], "custom_fields": {"customfield_1": "v"}},
    )
    assert fields == {
        "priority": {"name": "High"},
        "labels": ["atp"],
        "components": [{"name": "api"}],
        "customfield_1": "v",
    }
    untouched: dict = {}
    bug_reporter._apply_jira_field_mapping(untouched, {})
    assert untouched == {}


def test_apply_zentao_field_mapping_joins_keywords():
    payload: dict = {}
    bug_reporter._apply_zentao_field_mapping(
        payload, {"priority": 1, "severity": 2, "module": 9, "keywords": ["a", "b"], "custom_fields": {"os": "mac"}}
    )
    assert payload == {"pri": 1, "severity": 2, "module": 9, "keywords": "a,b", "os": "mac"}


def test_resolve_zentao_product_id_prefers_override_and_map():
    cfg = {"product_id": 3, "product_map": {"web": 7}}
    assert bug_reporter._resolve_zentao_product_id(cfg, None) == 3
    assert bug_reporter._resolve_zentao_product_id(cfg, "") == 3
    assert bug_reporter._resolve_zentao_product_id(cfg, "web") == 7
    assert bug_reporter._resolve_zentao_product_id(cfg, "12") == 12
    assert bug_reporter._resolve_zentao_product_id(cfg, "misc") == "misc"


def test_gitlab_project_path_url_encodes_group_paths():
    assert bug_reporter._gitlab_project_path({"project_id": "group/atp"}) == "group%2Fatp"
    assert bug_reporter._gitlab_project_path({"project_id": 42}) == "42"


def test_build_bug_description_includes_step_and_payloads():
    text = bug_reporter.build_bug_description(
        run_id=9,
        case_name="登录",
        environment="staging",
        error_message="boom",
        step_name="提交",
        step_index=1,
        request_data={"a": 1},
        response_data={"b": 2},
    )
    assert "执行记录 #9" in text
    assert "失败步骤: #2 提交" in text
    assert '"a": 1' in text and '"b": 2' in text

    minimal = bug_reporter.build_bug_description(run_id=1, case_name="c", environment=None, error_message=None)
    assert "环境: -" in minimal


# ── Jira ────────────────────────────────────────────────────


def test_create_jira_issue_posts_payload_and_maps_result(fake_http):
    fake_http.script = [_FakeResponse(201, {"key": "ATP-7"})]

    result = asyncio.run(bug_reporter.create_bug("jira", _JIRA, "标题", "描述", {"priority": "High"}))

    assert result == {"bug_id": "ATP-7", "bug_url": "https://jira.example.com/browse/ATP-7", "title": "标题"}
    request = fake_http.requests[0]
    assert request["url"] == "https://jira.example.com/rest/api/2/issue"
    assert request["auth"] == ("qa@x.com", "tok")
    assert request["json"]["fields"]["priority"] == {"name": "High"}


def test_create_jira_issue_raises_on_http_error(fake_http):
    fake_http.script = [_FakeResponse(400, text="bad field")]

    with pytest.raises(RuntimeError, match="Jira 创建失败: HTTP 400"):
        asyncio.run(bug_reporter.create_bug("jira", _JIRA, "t", "d"))


def test_jira_connection_and_status(fake_http):
    fake_http.script = [
        _FakeResponse(200, {"displayName": "QA Bot"}),
        _FakeResponse(200, {"fields": {"status": {"name": "Open"}}}),
    ]

    conn = asyncio.run(bug_reporter.test_connection("jira", _JIRA))
    status = asyncio.run(bug_reporter.get_bug_status("jira", _JIRA, "ATP-7"))

    assert conn == {"ok": True, "message": "连接成功：QA Bot"}
    assert status == {"bug_id": "ATP-7", "status": "Open", "bug_url": "https://jira.example.com/browse/ATP-7"}


def test_jira_connection_failure_raises(fake_http):
    fake_http.script = [_FakeResponse(401)]

    with pytest.raises(RuntimeError, match="Jira 连接失败"):
        asyncio.run(bug_reporter.test_connection("jira", _JIRA))


def test_find_jira_duplicate_matches_exact_summary_only(fake_http):
    fake_http.script = [
        _FakeResponse(
            200,
            {
                "issues": [
                    {"key": "ATP-1", "fields": {"summary": "别的标题"}},
                    {"key": "ATP-2", "fields": {"summary": "目标标题"}},
                ]
            },
        )
    ]

    dup = asyncio.run(bug_reporter.find_duplicate_bug("jira", _JIRA, "目标标题"))

    assert dup["bug_id"] == "ATP-2"
    # JQL 注入防护：标题中的引号已转义
    fake_http.script = [_FakeResponse(500)]
    assert asyncio.run(bug_reporter.find_duplicate_bug("jira", _JIRA, "任意")) is None


def test_upload_jira_attachment_reports_status(fake_http):
    fake_http.script = [_FakeResponse(200)]

    ok = asyncio.run(bug_reporter.upload_attachment("jira", _JIRA, "ATP-7", "s.png", b"png"))

    assert ok is True
    request = fake_http.requests[0]
    assert request["headers"]["X-Atlassian-Token"] == "no-check"
    assert request["files"]["file"][0] == "s.png"


# ── 禅道 ────────────────────────────────────────────────────


def test_zentao_token_failures(fake_http):
    fake_http.script = [_FakeResponse(403)]
    with pytest.raises(RuntimeError, match="禅道登录失败: HTTP 403"):
        asyncio.run(bug_reporter.test_connection("zentao", _ZENTAO))

    fake_http.script = [_FakeResponse(200, {"token": ""})]
    with pytest.raises(RuntimeError, match="未获取到 token"):
        asyncio.run(bug_reporter.test_connection("zentao", _ZENTAO))


def test_create_zentao_bug_uses_token_and_field_mapping(fake_http):
    fake_http.script = [
        _FakeResponse(201, {"token": "zt-token"}),
        _FakeResponse(201, {"id": 55}),
    ]

    result = asyncio.run(
        bug_reporter.create_bug("zentao", _ZENTAO, "标题", "步骤", {"severity": 1}, override_product_id="12")
    )

    assert result["bug_id"] == "55"
    assert result["bug_url"] == "https://zentao.example.com/bug-view-55.html"
    bug_request = fake_http.requests[1]
    assert bug_request["headers"]["Token"] == "zt-token"
    assert bug_request["json"]["product"] == 12
    assert bug_request["json"]["severity"] == 1


def test_create_zentao_bug_raises_on_http_error(fake_http):
    fake_http.script = [_FakeResponse(200, {"token": "zt"}), _FakeResponse(500, text="oops")]

    with pytest.raises(RuntimeError, match="禅道创建 Bug 失败"):
        asyncio.run(bug_reporter.create_bug("zentao", _ZENTAO, "t", "d"))


def test_get_zentao_bug_status_handles_wrapped_shapes(fake_http):
    fake_http.script = [_FakeResponse(200, {"token": "zt"}), _FakeResponse(200, {"bug": {"status": "active"}})]
    status = asyncio.run(bug_reporter.get_bug_status("zentao", _ZENTAO, "55"))
    assert status["status"] == "active"

    fake_http.script = [_FakeResponse(200, {"token": "zt"}), _FakeResponse(200, {"data": [{"status": "closed"}]})]
    status = asyncio.run(bug_reporter.get_bug_status("zentao", _ZENTAO, "55"))
    assert status["status"] == "closed"

    fake_http.script = [_FakeResponse(200, {"token": "zt"}), _FakeResponse(404)]
    with pytest.raises(RuntimeError, match="禅道状态查询失败"):
        asyncio.run(bug_reporter.get_bug_status("zentao", _ZENTAO, "55"))


def test_find_zentao_duplicate_matches_trimmed_title(fake_http):
    fake_http.script = [
        _FakeResponse(200, {"token": "zt"}),
        _FakeResponse(200, {"bugs": [{"id": 5, "title": " 目标 "}, {"id": 6, "title": "其他"}]}),
    ]
    dup = asyncio.run(bug_reporter.find_duplicate_bug("zentao", _ZENTAO, "目标"))
    assert dup["bug_id"] == "5"

    fake_http.script = [_FakeResponse(200, {"token": "zt"}), _FakeResponse(200, {"data": {"items": []}})]
    assert asyncio.run(bug_reporter.find_duplicate_bug("zentao", _ZENTAO, "目标")) is None

    fake_http.script = [_FakeResponse(200, {"token": "zt"}), _FakeResponse(200, {"bugs": "not-a-list"})]
    assert asyncio.run(bug_reporter.find_duplicate_bug("zentao", _ZENTAO, "目标")) is None


def test_upload_zentao_attachment_posts_files(fake_http):
    fake_http.script = [_FakeResponse(200, {"token": "zt"}), _FakeResponse(201)]

    ok = asyncio.run(bug_reporter.upload_attachment("zentao", _ZENTAO, "55", "s.png", b"png"))

    assert ok is True
    assert fake_http.requests[1]["files"]["files"][0] == "s.png"


# ── GitHub ──────────────────────────────────────────────────


def test_create_github_issue_and_headers(fake_http):
    fake_http.script = [_FakeResponse(201, {"number": 12, "html_url": "https://github.com/acme/atp/issues/12"})]

    result = asyncio.run(bug_reporter.create_bug("github", _GITHUB, "t", "d", {"labels": ["bug"]}))

    assert result["bug_id"] == "12"
    request = fake_http.requests[0]
    assert request["headers"]["Authorization"] == "Bearer gh-tok"
    assert request["json"]["labels"] == ["bug"]

    fake_http.script = [_FakeResponse(422)]
    with pytest.raises(RuntimeError, match="GitHub 创建 Issue 失败"):
        asyncio.run(bug_reporter.create_bug("github", _GITHUB, "t", "d"))


def test_find_github_duplicate_skips_pull_requests(fake_http):
    fake_http.script = [
        _FakeResponse(
            200,
            [
                {"number": 1, "title": "目标", "pull_request": {"url": "pr"}, "html_url": "pr-url"},
                {"number": 2, "title": "目标", "html_url": "issue-url"},
            ],
        )
    ]

    dup = asyncio.run(bug_reporter.find_duplicate_bug("github", _GITHUB, "目标"))

    assert dup == {"bug_id": "2", "bug_url": "issue-url", "title": "目标"}


def test_github_connection_and_status(fake_http):
    fake_http.script = [_FakeResponse(200, {"full_name": "acme/atp"})]
    assert asyncio.run(bug_reporter.test_connection("github", _GITHUB))["ok"] is True

    fake_http.script = [_FakeResponse(200, {"state": "open", "html_url": "u"})]
    status = asyncio.run(bug_reporter.get_bug_status("github", _GITHUB, "12"))
    assert status == {"bug_id": "12", "status": "open", "bug_url": "u"}

    fake_http.script = [_FakeResponse(404)]
    with pytest.raises(RuntimeError, match="GitHub 状态查询失败"):
        asyncio.run(bug_reporter.get_bug_status("github", _GITHUB, "404"))


# ── GitLab ──────────────────────────────────────────────────


def test_create_gitlab_issue_encodes_project_and_joins_labels(fake_http):
    fake_http.script = [_FakeResponse(201, {"iid": 8, "web_url": "https://gitlab.com/group/atp/-/issues/8"})]

    result = asyncio.run(
        bug_reporter.create_bug("gitlab", _GITLAB, "t", "d", {"labels": ["atp", "auto"], "milestone_id": 3})
    )

    assert result["bug_id"] == "8"
    request = fake_http.requests[0]
    assert "/projects/group%2Fatp/issues" in request["url"]
    assert request["headers"]["PRIVATE-TOKEN"] == "gl-tok"
    assert request["json"]["labels"] == "atp,auto"
    assert request["json"]["milestone_id"] == 3

    fake_http.script = [_FakeResponse(400, text="bad")]
    with pytest.raises(RuntimeError, match="GitLab 创建 Issue 失败"):
        asyncio.run(bug_reporter.create_bug("gitlab", _GITLAB, "t", "d"))


def test_gitlab_connection_duplicate_and_status(fake_http):
    fake_http.script = [_FakeResponse(200, {"path_with_namespace": "group/atp"})]
    assert "group/atp" in asyncio.run(bug_reporter.test_connection("gitlab", _GITLAB))["message"]

    fake_http.script = [_FakeResponse(200, [{"iid": 4, "title": "目标", "web_url": "u4"}])]
    dup = asyncio.run(bug_reporter.find_duplicate_bug("gitlab", _GITLAB, "目标"))
    assert dup["bug_id"] == "4"

    fake_http.script = [_FakeResponse(500)]
    assert asyncio.run(bug_reporter.find_duplicate_bug("gitlab", _GITLAB, "目标")) is None

    fake_http.script = [_FakeResponse(200, {"state": "closed", "web_url": "u"})]
    status = asyncio.run(bug_reporter.get_bug_status("gitlab", _GITLAB, "4"))
    assert status["status"] == "closed"

    fake_http.script = [_FakeResponse(404)]
    with pytest.raises(RuntimeError, match="GitLab 状态查询失败"):
        asyncio.run(bug_reporter.get_bug_status("gitlab", _GITLAB, "4"))
