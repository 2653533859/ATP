from app.services.api_contracts import compare_contracts


def test_openapi_comparison_detects_removed_operation_and_required_parameter():
    baseline = {
        "openapi": "3.0.0",
        "paths": {
            "/users": {
                "get": {
                    "parameters": [{"in": "query", "name": "page", "required": False}],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/removed": {"get": {"responses": {"200": {"description": "ok"}}}},
        },
    }
    current = {
        "openapi": "3.0.0",
        "paths": {
            "/users": {
                "get": {
                    "parameters": [{"in": "query", "name": "page", "required": True}],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }

    result = compare_contracts(baseline, current)

    assert result["compatible"] is False
    assert any("可选请求参数变为必填" in item["message"] for item in result["breaking_changes"])
    assert any("接口路径已删除" in item["message"] for item in result["breaking_changes"])


def test_json_schema_comparison_detects_deleted_field_and_reports_added_required_field():
    result = compare_contracts(
        {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}, "name": {}}},
        {"type": "object", "required": ["id", "email"], "properties": {"id": {"type": "string"}}},
    )

    assert result["compatible"] is False
    assert any(item["location"] == "$.name" for item in result["breaking_changes"])
    assert any(item["location"] == "$.id" for item in result["breaking_changes"])
    assert any(item["location"] == "$.email" for item in result["warnings"])


def test_openapi_comparison_resolves_local_schema_refs():
    baseline = {
        "openapi": "3.0.0",
        "components": {"schemas": {"User": {"type": "object", "properties": {"id": {"type": "integer"}}}}},
        "paths": {
            "/users": {
                "get": {
                    "responses": {
                        "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/User"}}}}
                    }
                }
            }
        },
    }
    current = {
        **baseline,
        "components": {"schemas": {"User": {"type": "object", "properties": {"name": {"type": "string"}}}}},
    }

    result = compare_contracts(baseline, current)

    assert result["compatible"] is False
    assert any(item["location"] == "GET /users response 200.id" for item in result["breaking_changes"])


def test_openapi_comparison_warns_for_external_refs_without_fetching():
    document = {
        "openapi": "3.0.0",
        "paths": {"/users": {"get": {"responses": {"200": {"$ref": "https://example.com/response.json"}}}}},
    }

    result = compare_contracts(document, document)

    assert any(item["severity"] == "warning" for item in result["warnings"])
