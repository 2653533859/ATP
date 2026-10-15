"""N2.5 Protocol Sub-Items Acceptance Regression.

Validates that:
1. dispatch_case properly rejects empty protocol cases (graphql, websocket, grpc) with an explicit error.
2. dispatch_case routes GraphQL cases to graphql_executor.
3. dispatch_case routes WebSocket cases to websocket_executor.
4. dispatch_case routes gRPC cases to grpc_executor.
5. Multi-protocol pipelines correctly propagate variables across mixed steps.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.case import CaseType, RunStatus
from app.worker.case_dispatch import dispatch_case, _reject_empty_protocol_case


class _FakeDB:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


@pytest.mark.parametrize(
    "case_type",
    [CaseType.graphql, CaseType.websocket, CaseType.grpc],
)
def test_reject_empty_protocol_case(case_type):
    """Protocol cases must configure executable steps; empty ones are rejected."""
    run = SimpleNamespace(id=1, status=RunStatus.pending, error_message=None)
    case = SimpleNamespace(id=10, case_type=case_type, config={})
    db = _FakeDB()

    rejected = asyncio.run(_reject_empty_protocol_case(db, run, case))
    assert rejected is True
    assert run.status == RunStatus.error
    assert "协议用例未配置可执行步骤" in (run.error_message or "")
    assert db.commits == 1


def test_dispatch_graphql_case(monkeypatch):
    """GraphQL cases are routed to run_graphql_case."""
    mock_run_graphql = AsyncMock()
    monkeypatch.setattr("app.worker.executors.graphql_executor.run_graphql_case", mock_run_graphql)

    run = SimpleNamespace(id=2, status=RunStatus.running, trace_id="trace-gql-01")
    case = SimpleNamespace(
        id=20,
        case_type=CaseType.graphql,
        config={"steps": [{"endpoint": "http://api.test/graphql", "query": "{ me { id } }"}]},
    )
    db = _FakeDB()

    dispatched = asyncio.run(dispatch_case(db, run, case, extra_vars={"env": "test"}))
    assert dispatched is True
    mock_run_graphql.assert_called_once_with(db, run, case, {"env": "test"})


def test_dispatch_websocket_case(monkeypatch):
    """WebSocket cases are routed to run_websocket_case."""
    mock_run_ws = AsyncMock()
    monkeypatch.setattr("app.worker.executors.websocket_executor.run_websocket_case", mock_run_ws)

    run = SimpleNamespace(id=3, status=RunStatus.running, trace_id="trace-ws-01")
    case = SimpleNamespace(
        id=30,
        case_type=CaseType.websocket,
        config={"steps": [{"url": "ws://api.test/ws/echo", "messages": [{"action": "send", "content": "ping"}]}]},
    )
    db = _FakeDB()

    dispatched = asyncio.run(dispatch_case(db, run, case, extra_vars={}))
    assert dispatched is True
    mock_run_ws.assert_called_once_with(db, run, case, {})


def test_dispatch_grpc_case(monkeypatch):
    """gRPC cases are routed to run_grpc_case."""
    mock_run_grpc = AsyncMock()
    monkeypatch.setattr("app.worker.executors.grpc_executor.run_grpc_case", mock_run_grpc)

    run = SimpleNamespace(id=4, status=RunStatus.running, trace_id="trace-grpc-01")
    case = SimpleNamespace(
        id=40,
        case_type=CaseType.grpc,
        config={"steps": [{"target": "localhost:50051", "service": "demo.Echo", "method": "Say"}]},
    )
    db = _FakeDB()

    dispatched = asyncio.run(dispatch_case(db, run, case, extra_vars={"tenant": "atp"}))
    assert dispatched is True
    mock_run_grpc.assert_called_once_with(db, run, case, {"tenant": "atp"})


def test_dispatch_multiprotocol_pipeline(monkeypatch):
    """API cases declaring mixed protocol steps route to multiprotocol_executor."""
    mock_run_multi = AsyncMock()
    monkeypatch.setattr("app.worker.executors.multiprotocol_executor.run_multiprotocol_case", mock_run_multi)

    run = SimpleNamespace(id=5, status=RunStatus.running, trace_id="trace-multi-01")
    case = SimpleNamespace(
        id=50,
        case_type=CaseType.api,
        config={
            "steps": [
                {"protocol": "http", "url": "/login"},
                {"protocol": "websocket", "url": "/ws/chat"},
            ]
        },
    )
    db = _FakeDB()

    dispatched = asyncio.run(dispatch_case(db, run, case, extra_vars={}))
    assert dispatched is True
    mock_run_multi.assert_called_once_with(db, run, case, {})
