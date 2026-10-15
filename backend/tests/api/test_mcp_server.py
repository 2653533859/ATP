"""Unit tests for ATP Model Context Protocol (MCP) Server (P1.1).

Tests:
1. JSON-RPC 2.0 initialize negotiation and protocol version
2. tools/list schema validation
3. tools/call dispatching for test case listing, details, and defect creation
4. Error handling for unknown tools and methods
5. FastAPI /api/v1/mcp endpoints
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.mcp import TOOLS_MANIFEST
from app.mcp.server import METHOD_NOT_FOUND, MCPServer
from app.models.bootstrap import load_all_models
from app.models.case import CaseType, RunStatus, TestCase
from app.models.project import Module
from app.models.user import User, UserRole

load_all_models()


class _FakeDB:
    def __init__(self, entities: dict[type, dict[int, Any]] | None = None):
        self.entities = entities or {}
        self.added = []
        self.commits = 0
        self._next_id = 9000

    async def get(self, model: type, pk: int) -> Any | None:
        return self.entities.get(model, {}).get(pk)

    async def execute(self, statement):
        # Lightweight statement evaluation for mock
        class _Result:
            def __init__(self, items):
                self._items = items

            def scalars(self):
                return self

            def all(self):
                return self._items

            def scalar_one_or_none(self):
                return self._items[0] if self._items else None

            def scalar(self):
                return len(self._items)

        # Default fallback
        return _Result([])

    def add(self, item):
        if not getattr(item, "id", None):
            item.id = self._next_id
            self._next_id += 1
        self.added.append(item)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _item):
        pass


def _admin_user() -> User:
    return User(
        id=1,
        username="admin",
        email="admin@atp.local",
        role=UserRole.admin,
        hashed_password="***",
        is_active=True,
    )


def test_mcp_server_initialize():
    server = MCPServer()
    db = _FakeDB()
    user = _admin_user()

    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }

    resp = asyncio.run(server.handle_request(db, user, req))
    assert resp is not None
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    result = resp["result"]
    assert result["protocolVersion"] == "2024-11-05"
    assert result["serverInfo"]["name"] == "atp-mcp-server"
    assert "tools" in result["capabilities"]


def test_mcp_server_ping():
    server = MCPServer()
    db = _FakeDB()
    user = _admin_user()

    req = {"jsonrpc": "2.0", "id": 2, "method": "ping"}
    resp = asyncio.run(server.handle_request(db, user, req))
    assert resp is not None
    assert resp["id"] == 2
    assert resp["result"] == {}


def test_mcp_server_tools_list():
    server = MCPServer()
    db = _FakeDB()
    user = _admin_user()

    req = {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}
    resp = asyncio.run(server.handle_request(db, user, req))
    assert resp is not None
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]

    expected = [
        "atp_list_cases",
        "atp_get_case_detail",
        "atp_run_case",
        "atp_get_run_status",
        "atp_diagnose_failure",
        "atp_create_defect",
        "atp_get_project_summary",
    ]
    for exp in expected:
        assert exp in tool_names
    assert len(tools) == len(TOOLS_MANIFEST)


def test_mcp_server_unknown_method():
    server = MCPServer()
    db = _FakeDB()
    user = _admin_user()

    req = {"jsonrpc": "2.0", "id": 4, "method": "non_existent_method"}
    resp = asyncio.run(server.handle_request(db, user, req))
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == METHOD_NOT_FOUND


def test_mcp_server_tools_call_unknown_tool():
    server = MCPServer()
    db = _FakeDB()
    user = _admin_user()

    req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "unknown_tool_xyz",
            "arguments": {},
        },
    }
    resp = asyncio.run(server.handle_request(db, user, req))
    assert resp is not None
    result = resp["result"]
    assert result["isError"] is True
    assert "未知工具" in result["content"][0]["text"]


def test_mcp_server_tools_call_get_case_detail(monkeypatch):
    server = MCPServer()
    user = _admin_user()

    mock_case = TestCase(
        id=42,
        name="测试用例42",
        case_type=CaseType.api,
        module_id=1,
        priority="P1",
        status=RunStatus.pending,
        config={"method": "GET", "url": "/api/test"},
    )
    mock_module = Module(id=1, project_id=7, name="基础模块")

    db = _FakeDB({TestCase: {42: mock_case}, Module: {1: mock_module}})

    req = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "atp_get_case_detail",
            "arguments": {"case_id": 42},
        },
    }

    resp = asyncio.run(server.handle_request(db, user, req))
    assert resp is not None
    result = resp["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["id"] == 42
    assert payload["name"] == "测试用例42"
    assert payload["config"]["method"] == "GET"


def test_mcp_server_tools_call_create_defect(monkeypatch):
    server = MCPServer()
    user = _admin_user()
    db = _FakeDB()

    req = {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "atp_create_defect",
            "arguments": {
                "project_id": 7,
                "title": "登录失败缺陷",
                "description": "用户名密码正确时返回500",
                "severity": "critical",
            },
        },
    }

    resp = asyncio.run(server.handle_request(db, user, req))
    assert resp is not None
    result = resp["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["title"] == "登录失败缺陷"
    assert payload["project_id"] == 7
    assert payload["status"] == "open"
    assert len(db.added) == 1
    assert db.commits == 1


def test_mcp_api_router_status():
    from app.api.v1.mcp import get_mcp_status, list_mcp_tools

    status_data = get_mcp_status()
    assert status_data["server"] == "atp-mcp-server"
    assert status_data["version"] == "2.5.0"
    assert status_data["tools_count"] == len(TOOLS_MANIFEST)

    tools_data = list_mcp_tools(_=_admin_user())
    assert len(tools_data["tools"]) == len(TOOLS_MANIFEST)
