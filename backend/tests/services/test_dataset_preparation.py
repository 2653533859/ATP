import asyncio

import httpx
import pytest

from app.services.dataset_preparation import DatasetPreparationError, execute_dataset_preparation


@pytest.fixture(autouse=True)
def allow_test_urls(monkeypatch):
    monkeypatch.setattr("app.services.dataset_preparation.validate_public_http_url", lambda value: value)


class _FakeClient:
    def __init__(self, **_kwargs):
        self.requests: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        return httpx.Response(
            201,
            json={"id": "u-1", "name": "alice"},
            headers={"content-type": "application/json"},
            request=httpx.Request(method, url),
        )


def test_preparation_request_extracts_run_scoped_variable(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr("app.services.dataset_preparation.httpx.AsyncClient", lambda **_kwargs: client)
    context = {"base_url": "https://api.example.test", "username": "alice"}

    summaries = asyncio.run(
        execute_dataset_preparation(
            [
                {"action": "set_variable", "variable": "tenant", "value": "demo"},
                {
                    "action": "request",
                    "name": "create user",
                    "method": "POST",
                    "url": "{{base_url}}/users",
                    "body_type": "json",
                    "body": {"name": "{{username}}", "tenant": "{{tenant}}"},
                    "assertions": [{"source": "status", "operator": "eq", "expected": 201}],
                    "post_actions": [
                        {"action": "extract", "variable": "user_id", "expression": "$.id"},
                    ],
                },
            ],
            context,
        )
    )

    assert context["user_id"] == "u-1"
    assert summaries[1] == {
        "action": "request",
        "name": "create user",
        "method": "POST",
        "status_code": 201,
        "post_action_count": 1,
    }
    assert client.requests[0]["json"] == {"name": "alice", "tenant": "demo"}


def test_preparation_body_assertion_and_no_secret_in_summary(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr("app.services.dataset_preparation.httpx.AsyncClient", lambda **_kwargs: client)
    context = {"token": "secret-token"}

    summaries = asyncio.run(
        execute_dataset_preparation(
            [
                {
                    "action": "request",
                    "url": "https://api.example.test/users",
                    "headers": {"Authorization": "Bearer {{token}}"},
                    "assertions": [{"source": "body", "expression": "$.name", "expected": "alice"}],
                }
            ],
            context,
        )
    )

    assert summaries[0]["status_code"] == 201
    assert "secret-token" not in repr(summaries)


@pytest.mark.parametrize(
    "action",
    [
        {"action": "request", "method": "TRACE", "url": "https://api.example.test"},
        {"action": "request", "url": "https://api.example.test", "timeout": 61},
        {"action": "execute_python", "code": "print('unsafe')"},
    ],
)
def test_preparation_rejects_unsafe_or_invalid_actions(action):
    with pytest.raises(DatasetPreparationError):
        asyncio.run(execute_dataset_preparation([action], {}))


def test_preparation_rejects_private_or_unresolvable_seed_url(monkeypatch):
    monkeypatch.setattr(
        "app.services.dataset_preparation.validate_public_http_url",
        lambda _value: (_ for _ in ()).throw(ValueError("不允许访问本机或内网地址")),
    )

    with pytest.raises(DatasetPreparationError, match="不允许访问本机或内网地址"):
        asyncio.run(
            execute_dataset_preparation(
                [{"action": "request", "url": "https://internal.example.test/seed"}],
                {},
            )
        )


def test_preparation_rejects_non_list_actions():
    with pytest.raises(DatasetPreparationError, match="动作数量"):
        asyncio.run(execute_dataset_preparation({"action": "request"}, {}))
