"""Unit tests for T1.3 Traffic Recording Session to TestCase and TestSuite Converter.

Tests:
1. generate_step_assertions generates status_code, JSONPath (code/success), and latency SLA assertions
2. convert_traffic_entry_to_step creates standard CaseStepCreate and executor step config
3. synthesize_case_from_traffic produces clean parameterized TestCase payload with extractions
4. synthesize_case_from_traffic handles database persistence mode
5. synthesize_suite_from_session creates TestSuite wrapping synthesized case
"""

from __future__ import annotations

import pytest

from app.models.bootstrap import load_all_models
from app.services.traffic_recorder_gateway import start_recording_session
from app.services.traffic_to_case_converter import (
    convert_traffic_entry_to_step,
    generate_step_assertions,
    synthesize_case_from_traffic,
    synthesize_suite_from_session,
)

load_all_models()


def test_generate_step_assertions():
    entry = {
        "status_code": 201,
        "duration_ms": 120.0,
        "response_body": {
            "code": 0,
            "success": True,
            "status": "created",
            "data": {"id": 1001},
        },
    }

    assertions = generate_step_assertions(entry)
    targets = {a["target"]: a for a in assertions}

    # Status code
    assert "status_code" in targets
    assert targets["status_code"]["expected"] == 201

    # Duration SLA
    assert "duration" in targets
    assert targets["duration"]["operator"] == "lt"
    assert targets["duration"]["expected"] >= 3000

    # Body JSONPaths
    body_assertions = [a for a in assertions if a["target"] == "body"]
    assert len(body_assertions) == 3
    exprs = {a["expression"]: a["expected"] for a in body_assertions}
    assert exprs["$.code"] == 0
    assert exprs["$.success"] is True
    assert exprs["$.status"] == "created"


def test_convert_traffic_entry_to_step():
    entry = {
        "method": "POST",
        "path": "/api/v1/orders/create",
        "url": "https://api.example.com/api/v1/orders/create",
        "status_code": 200,
        "headers": {"Content-Type": "application/json"},
        "query_params": {"channel": "app"},
        "request_body": {"item_id": 99, "quantity": 2},
        "response_body": {"order_id": 888},
        "duration_ms": 85.0,
        "extractions": [{"variable": "order_id", "type": "jsonpath", "expression": "$.order_id"}],
    }

    c_step, e_step = convert_traffic_entry_to_step(entry, step_no=1)

    assert c_step.step_no == 1
    assert c_step.action == "POST /api/v1/orders/create"
    assert c_step.is_key_step is True
    assert "quantity" in str(c_step.test_data)

    assert e_step["step_no"] == 1
    assert e_step["method"] == "POST"
    assert e_step["body_type"] == "json"
    assert e_step["body"]["item_id"] == 99
    assert len(e_step["extractions"]) == 1
    assert len(e_step["assertions"]) >= 1


@pytest.mark.asyncio
async def test_synthesize_case_from_traffic_preview():
    raw_entries = [
        # Noise entry: static asset (should be excluded)
        {
            "method": "GET",
            "path": "/static/bundle.js",
            "url": "https://api.example.com/static/bundle.js",
            "status_code": 200,
            "is_noise": True,
        },
        # Step 1: Login
        {
            "method": "POST",
            "path": "/api/v1/auth/login",
            "url": "https://api.example.com/api/v1/auth/login",
            "status_code": 200,
            "request_body": {"username": "admin"},
            "response_body": {"token": "token_abc123"},
            "duration_ms": 60.0,
            "is_noise": False,
        },
        # Step 2: Query order using token
        {
            "method": "GET",
            "path": "/api/v1/orders/1001",
            "url": "https://api.example.com/api/v1/orders/1001",
            "headers": {"Authorization": "Bearer token_abc123"},
            "status_code": 200,
            "response_body": {"order_id": 1001, "status": "paid"},
            "duration_ms": 40.0,
            "is_noise": False,
        },
    ]

    res = await synthesize_case_from_traffic(
        raw_entries,
        case_name="冒烟用例 - 登录查询闭环",
        module_id=1,
        owner_id=1,
        project_id=10,
        persist=False,
    )

    assert res["name"] == "冒烟用例 - 登录查询闭环"
    assert res["total_steps"] == 2
    assert res["persisted"] is False
    assert len(res["steps"]) == 2

    # Verify that token dependency was extracted and parameterized in step 2
    exec_steps = res["config"]["steps"]
    assert exec_steps[0]["extractions"][0]["variable"] == "token"
    assert exec_steps[1]["headers"]["Authorization"] == "Bearer {{token}}"


@pytest.mark.asyncio
async def test_synthesize_case_from_traffic_persist():
    raw_entries = [
        {
            "method": "GET",
            "path": "/api/v1/products",
            "url": "https://api.example.com/api/v1/products",
            "status_code": 200,
            "response_body": {"items": []},
            "duration_ms": 30.0,
            "is_noise": False,
        },
    ]

    class _MockDB:
        def __init__(self):
            self.added = []
            self.committed = False

        def add(self, obj):
            # assign mock id
            obj.id = 777
            self.added.append(obj)

        async def flush(self):
            pass

        async def commit(self):
            self.committed = True

        async def refresh(self, obj):
            pass

    db = _MockDB()

    res = await synthesize_case_from_traffic(
        raw_entries,
        case_name="商品列表测试",
        module_id=2,
        owner_id=1,
        project_id=10,
        persist=True,
        db=db,  # type: ignore[arg-type]
    )

    assert res["persisted"] is True
    assert res["case_id"] == 777
    assert db.committed is True
    assert len(db.added) == 2  # TestCase + 1 CaseStep


@pytest.mark.asyncio
async def test_synthesize_suite_from_session():
    # Setup active session with 1 clean entry
    session = start_recording_session(
        project_id=10,
        target_base_url="https://api.example.com",
        session_id="rec_suite_test_01",
    )
    session.record_entry(
        method="GET",
        path="/api/v1/health-service/items",
        headers={},
        query_params={},
        request_body=None,
        status_code=200,
        response_headers={},
        response_body={"items": [1, 2, 3]},
        duration_ms=45.0,
    )

    class _MockDB:
        def __init__(self):
            self.added = []

        def add(self, obj):
            obj.id = 999
            self.added.append(obj)

        async def flush(self):
            pass

        async def commit(self):
            pass

        async def refresh(self, obj):
            pass

    db = _MockDB()

    suite_res = await synthesize_suite_from_session(
        "rec_suite_test_01",
        suite_name="微服务全量业务套件",
        module_id=1,
        project_id=10,
        owner_id=1,
        persist=True,
        db=db,  # type: ignore[arg-type]
    )

    assert suite_res["suite_name"] == "微服务全量业务套件"
    assert suite_res["suite_id"] == 999
    assert suite_res["persisted"] is True
    assert suite_res["case_summary"]["total_steps"] == 1
