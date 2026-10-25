"""Unit tests for P1.3 Bidirectional Specification Synchronization and Test Asset Alignment.

Tests:
1. Path normalization and spec operation extraction
2. Extraction of method and path from case config and steps
3. Full spec synchronization against project cases:
   - Detects new spec endpoints (additions) and generates TestCaseCreate draft patches
   - Detects modified endpoints (new required parameters)
   - Detects deprecated endpoints (cases whose endpoint is no longer in spec)
4. Fast REST API /api-contracts/sync-cases endpoint integration
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

from app.models.bootstrap import load_all_models
from app.models.case import CaseType, TestCase
from app.models.project import Module
from app.models.user import User, UserRole

load_all_models()
from app.services.spec_sync import (
    case_request_fingerprint,
    extract_case_endpoint,
    extract_spec_endpoints,
    normalize_endpoint_path,
    sync_spec_with_cases,
)


class _FakeDB:
    def __init__(self, modules: list[Any], cases: list[Any]):
        self._modules = modules
        self._cases = cases

    async def execute(self, statement):
        class _Result:
            def __init__(self, items):
                self._items = items

            def scalars(self):
                return self

            def all(self):
                return self._items

        # Rough filter check
        sql_str = str(statement).lower()
        if "from modules" in sql_str:
            return _Result(self._modules)
        return _Result(self._cases)


def test_normalize_endpoint_path():
    assert normalize_endpoint_path("/api/v1/users/") == "/api/v1/users"
    assert normalize_endpoint_path("//api///v1//orders") == "/api/v1/orders"
    assert normalize_endpoint_path("/api/items?active=true") == "/api/items"
    assert normalize_endpoint_path("https://api.example.com/api/items?active=true") == "/api/items"
    assert normalize_endpoint_path("") == "/"


def test_extract_spec_endpoints():
    spec = {
        "paths": {
            "/users": {
                "parameters": [{"name": "tenant", "in": "header"}],
                "get": {
                    "summary": "获取用户列表",
                    "parameters": [{"name": "page", "in": "query", "required": False}],
                },
                "post": {
                    "summary": "创建用户",
                    "requestBody": {"content": {"application/json": {}}},
                },
            },
            "/orders/{order_id}": {
                "get": {
                    "summary": "获取订单详情",
                    "parameters": [{"name": "order_id", "in": "path", "required": True}],
                }
            },
        }
    }

    endpoints = extract_spec_endpoints(spec)
    assert len(endpoints) == 3
    assert ("GET", "/users") in endpoints
    assert ("POST", "/users") in endpoints
    assert ("GET", "/orders/{order_id}") in endpoints

    get_users = endpoints[("GET", "/users")]
    assert get_users["summary"] == "获取用户列表"
    param_names = [p["name"] for p in get_users["parameters"]]
    assert "tenant" in param_names
    assert "page" in param_names


def test_extract_case_endpoint():
    # Direct config
    c1 = TestCase(
        id=1,
        name="Case 1",
        case_type=CaseType.api,
        config={"method": "GET", "url": "/api/v1/users/"},
    )
    assert extract_case_endpoint(c1) == ("GET", "/api/v1/users")

    # Step config
    c2 = TestCase(
        id=2,
        name="Case 2",
        case_type=CaseType.api,
        config={"steps": [{"method": "POST", "url": "/api/v1/orders"}]},
    )
    assert extract_case_endpoint(c2) == ("POST", "/api/v1/orders")

    # Incomplete config
    c3 = TestCase(id=3, name="Case 3", case_type=CaseType.api, config={})
    assert extract_case_endpoint(c3) is None


def test_scenario_impact_distinguishes_source_change_from_local_override():
    module = Module(id=10, project_id=5, name="核心模块")
    case = TestCase(
        id=101,
        name="订单查询",
        case_type=CaseType.api,
        module_id=10,
        config={"method": "GET", "url": "/orders", "params": {}},
    )
    fingerprint = case_request_fingerprint(case)
    scenario = {
        "id": 7,
        "name": "订单场景",
        "project_id": 5,
        "steps": [
            {"method": "GET", "url": "/orders", "params": {}, "sourceCaseId": 101, "sourceCaseFingerprint": fingerprint}
        ],
    }
    spec = {"paths": {"/orders": {"get": {"parameters": [{"name": "role", "in": "query", "required": True}]}}}}
    db = _FakeDB(modules=[module], cases=[case])

    first = asyncio.run(sync_spec_with_cases(db, project_id=5, spec=spec, scenarios=[scenario]))
    assert "来源与场景请求一致" in first["scenario_impacts"][0]["review_reason"]
    assert "版本冲突" not in first["scenario_impacts"][0]["review_reason"]

    case.config = {"method": "GET", "url": "/orders", "params": {"region": "east"}}
    second = asyncio.run(sync_spec_with_cases(db, project_id=5, spec=spec, scenarios=[scenario]))
    assert "版本冲突" in second["scenario_impacts"][0]["review_reason"]
    assert "局部覆盖" not in second["scenario_impacts"][0]["review_reason"]

    scenario["steps"][0]["params"] = {"region": "west"}
    third = asyncio.run(sync_spec_with_cases(db, project_id=5, spec=spec, scenarios=[scenario]))
    assert "版本冲突" in third["scenario_impacts"][0]["review_reason"]
    assert "局部覆盖" in third["scenario_impacts"][0]["review_reason"]


def test_case_fingerprint_respects_empty_step_headers_over_flat_config():
    case = TestCase(
        id=1,
        case_type=CaseType.api,
        config={
            "method": "GET",
            "url": "/orders",
            "headers": {"X-Old": "value"},
            "steps": [{"method": "GET", "url": "/orders", "headers": {}}],
        },
    )
    step = {"method": "GET", "url": "/orders", "headers": {}}
    from app.services.spec_sync import scenario_request_fingerprint

    assert case_request_fingerprint(case) == scenario_request_fingerprint(step)


def test_sync_spec_with_cases_detects_additions_modifications_deprecations():
    module = Module(id=10, project_id=5, name="核心模块")

    # Existing cases in project:
    # 1. Matching GET /users (will have parameter modification)
    # 2. Case for GET /legacy (endpoint removed in spec -> deprecation)
    c_existing_get = TestCase(
        id=101,
        name="测试获取用户",
        case_type=CaseType.api,
        module_id=10,
        config={"method": "GET", "url": "/users", "params": {}},
    )
    c_deprecated = TestCase(
        id=102,
        name="旧版本接口用例",
        case_type=CaseType.api,
        module_id=10,
        config={"method": "GET", "url": "/legacy"},
    )

    db = _FakeDB(modules=[module], cases=[c_existing_get, c_deprecated])

    # Spec has:
    # 1. GET /users (modified: requires query parameter 'role')
    # 2. POST /users (new endpoint -> addition)
    spec = {
        "paths": {
            "/users": {
                "get": {
                    "summary": "获取用户列表V2",
                    "parameters": [{"name": "role", "in": "query", "required": True}],
                },
                "post": {
                    "summary": "创建新用户",
                    "parameters": [{"name": "x-api-key", "in": "header", "required": True}],
                },
            }
        }
    }

    scenarios = [
        {
            "id": 7,
            "name": "订单回归",
            "project_id": 5,
            "steps": [
                {"name": "获取用户", "method": "GET", "url": "/old-copy", "sourceCaseId": 101},
                {"name": "旧接口", "method": "GET", "url": "/legacy"},
            ],
        },
        {"id": 8, "project_id": 6, "steps": [{"method": "GET", "url": "/legacy"}]},
    ]
    result = asyncio.run(sync_spec_with_cases(db, project_id=5, spec=spec, default_module_id=10, scenarios=scenarios))

    assert result["total_spec_endpoints"] == 2
    assert result["total_cases"] == 2
    assert result["additions_count"] == 1
    assert result["modifications_count"] == 1
    assert result["deprecations_count"] == 1

    diff_types = [d["change_type"] for d in result["diffs"]]
    assert "addition" in diff_types
    assert "modification" in diff_types
    assert "deprecation" in diff_types

    # Check addition patch payload
    addition_diff = next(d for d in result["diffs"] if d["change_type"] == "addition")
    assert addition_diff["endpoint"] == "POST /users"
    assert addition_diff["patch_payload"] is not None
    assert addition_diff["patch_payload"]["module_id"] == 10
    assert addition_diff["patch_payload"]["config"]["method"] == "POST"

    # Check modification details
    mod_diff = next(d for d in result["diffs"] if d["change_type"] == "modification")
    assert mod_diff["case_id"] == 101
    assert any("新增必填 Query 参数: 'role'" in msg for msg in mod_diff["details"])

    # Check deprecation details
    dep_diff = next(d for d in result["diffs"] if d["change_type"] == "deprecation")
    assert dep_diff["case_id"] == 102
    assert dep_diff["endpoint"] == "GET /legacy"

    assert [(item["scenario_id"], item["step_index"]) for item in result["scenario_impacts"]] == [(7, 0), (7, 1)]
    assert result["scenario_impacts"][0]["source_case_id"] == 101
    assert "版本" in result["scenario_impacts"][0]["review_reason"]
    assert result["scenario_impacts"][1]["source_case_id"] is None
    assert "人工确认" in result["scenario_impacts"][1]["review_reason"]


def test_sync_spec_reports_scenario_only_endpoint_removed_from_baseline():
    db = _FakeDB(modules=[Module(id=10, project_id=5, name="核心模块")], cases=[])
    baseline = {"paths": {"/legacy": {"get": {"responses": {"200": {}}}}}}
    current = {"paths": {}}
    scenarios = [{"id": 7, "project_id": 5, "steps": [{"name": "旧查询", "method": "GET", "url": "/legacy"}]}]

    result = asyncio.run(sync_spec_with_cases(db, 5, current, scenarios=scenarios, baseline=baseline))

    assert result["deprecations_count"] == 1
    assert result["diffs"][0]["endpoint"] == "GET /legacy"
    assert result["scenario_impacts"][0]["step_name"] == "旧查询"


def test_sync_api_contracts_endpoint(monkeypatch):
    from app.api.v1.api_contracts import sync_project_spec_with_cases
    from app.schemas.api_contract import SpecCaseSyncIn

    admin_user = User(
        id=1,
        username="admin",
        email="admin@atp.local",
        role=UserRole.admin,
        hashed_password="***",
        is_active=True,
    )

    async def fake_sync(_db, project_id, spec, default_module_id, *, scenarios, baseline):
        assert scenarios == [{"id": 3, "project_id": 5, "steps": []}]
        assert baseline is None
        return {
            "total_spec_endpoints": 1,
            "total_cases": 0,
            "additions_count": 1,
            "modifications_count": 0,
            "deprecations_count": 0,
            "diffs": [],
            "draft_patches": [],
            "scenario_impacts": [],
        }

    monkeypatch.setattr("app.api.v1.api_contracts.sync_spec_with_cases", fake_sync)
    monkeypatch.setattr(
        "app.api.v1.api_contracts.read_project_scenarios_snapshot",
        lambda project_id: [{"id": 3, "project_id": project_id, "steps": []}],
    )
    monkeypatch.setattr("app.api.v1.api_contracts.assert_project_access", AsyncMock())

    body = SpecCaseSyncIn(spec={"paths": {}}, default_module_id=1)
    db = _FakeDB([], [])

    res = asyncio.run(sync_project_spec_with_cases(project_id=5, body=body, db=db, user=admin_user))
    assert res["total_spec_endpoints"] == 1
    assert res["additions_count"] == 1
