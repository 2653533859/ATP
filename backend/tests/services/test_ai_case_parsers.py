"""Tests for app.services.ai_case.parsers."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.ai_case.parsers import parse_schema


# ──────────── OpenAPI ────────────


def test_parse_openapi_json_basic():
    doc = {
        "openapi": "3.0.0",
        "servers": [{"url": "https://api.example.com/v1"}],
        "paths": {
            "/users/{id}": {
                "get": {
                    "summary": "Get user",
                    "operationId": "getUser",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                            "description": "User ID",
                        }
                    ],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "integer"}},
                                    }
                                }
                            }
                        }
                    },
                },
                "post": {
                    "summary": "Create user",
                    "requestBody": {"content": {"application/json": {"example": {"name": "alice"}}}},
                    "responses": {"201": {}},
                },
            }
        },
    }
    result = parse_schema("openapi", json.dumps(doc))
    assert len(result.endpoints) == 2
    methods = sorted(e.method for e in result.endpoints)
    assert methods == ["GET", "POST"]
    get_endpoint = next(e for e in result.endpoints if e.method == "GET")
    assert get_endpoint.path == "/users/{id}"
    assert get_endpoint.base_url == "https://api.example.com/v1"
    assert get_endpoint.summary == "Get user"
    assert get_endpoint.parameters[0].name == "id"
    assert get_endpoint.parameters[0].location == "path"
    assert get_endpoint.parameters[0].required is True
    post_endpoint = next(e for e in result.endpoints if e.method == "POST")
    assert post_endpoint.request_body_example == {"name": "alice"}
    assert post_endpoint.response_status == 201


def test_parse_openapi_yaml_basic():
    yaml_doc = """
openapi: 3.0.0
paths:
  /ping:
    get:
      summary: Ping
"""
    result = parse_schema("openapi", yaml_doc)
    assert len(result.endpoints) == 1
    assert result.endpoints[0].method == "GET"
    assert result.endpoints[0].path == "/ping"


def test_parse_openapi_empty_paths_returns_warning():
    result = parse_schema("openapi", json.dumps({"openapi": "3.0.0"}))
    assert result.endpoints == []
    assert any("paths" in w for w in result.warnings)


def test_parse_openapi_resolves_local_refs_in_parameters_and_examples():
    doc = {
        "openapi": "3.0.0",
        "components": {
            "parameters": {
                "TraceId": {"name": "X-Trace-Id", "in": "header", "required": True, "schema": {"type": "string"}}
            },
            "schemas": {
                "User": {"type": "object", "properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}
            },
        },
        "paths": {
            "/users": {
                "get": {
                    "parameters": [{"$ref": "#/components/parameters/TraceId"}],
                    "responses": {
                        "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/User"}}}}
                    },
                }
            }
        },
    }

    result = parse_schema("openapi", json.dumps(doc))

    endpoint = result.endpoints[0]
    assert endpoint.parameters[0].name == "X-Trace-Id"
    assert endpoint.response_example == {"id": 0, "name": ""}
    assert result.warnings == []


def test_parse_openapi_preserves_falsy_examples_and_media_examples():
    doc = {
        "openapi": "3.0.0",
        "paths": {
            "/flags": {
                "get": {
                    "parameters": [
                        {"name": "enabled", "in": "query", "example": False, "schema": {"type": "boolean"}},
                        {"name": "limit", "in": "query", "example": 0, "schema": {"type": "integer"}},
                    ],
                    "requestBody": {"content": {"application/json": {"example": False, "schema": {"type": "boolean"}}}},
                    "responses": {"200": {"content": {"application/json": {"example": 0}}}},
                }
            }
        },
    }

    endpoint = parse_schema("openapi", json.dumps(doc)).endpoints[0]

    assert [parameter.example for parameter in endpoint.parameters] == [False, 0]
    assert endpoint.request_body_example is False
    assert endpoint.response_example == 0
    assert endpoint.response_status == 200


def test_parse_openapi_uses_first_success_response_status_without_content():
    doc = {
        "openapi": "3.0.0",
        "paths": {
            "/created": {
                "post": {
                    "responses": {
                        "400": {"description": "invalid"},
                        "202": {"description": "accepted"},
                    }
                }
            }
        },
    }

    endpoint = parse_schema("openapi", json.dumps(doc)).endpoints[0]

    assert endpoint.response_status == 202


def test_parse_openapi_reports_external_refs_without_network_access():
    result = parse_schema(
        "openapi",
        json.dumps(
            {
                "openapi": "3.0.0",
                "paths": {"/users": {"get": {"parameters": [{"$ref": "https://example.com/common.json#/TraceId"}]}}},
            }
        ),
    )

    assert result.endpoints
    assert any("外部" in warning for warning in result.warnings)


def test_parse_openapi_rejects_external_refs_in_release_policy():
    with pytest.raises(ValueError, match="外部 OpenAPI"):
        parse_schema(
            "openapi",
            json.dumps(
                {
                    "openapi": "3.0.0",
                    "paths": {"/users": {"get": {"parameters": [{"$ref": "https://example.com/common.json"}]}}},
                }
            ),
            external_ref_policy="reject",
        )


# ──────────── Postman ────────────


def test_parse_postman_collection_basic():
    collection = {
        "info": {"name": "My"},
        "item": [
            {
                "name": "List users",
                "request": {
                    "method": "GET",
                    "url": {"path": ["api", "v1", "users"], "query": [{"key": "limit", "value": "10"}]},
                    "header": [{"key": "Authorization", "value": "Bearer xxx"}],
                },
            },
            {
                "name": "Folder",
                "item": [
                    {
                        "name": "Create user",
                        "request": {
                            "method": "POST",
                            "url": "https://api.example.com/api/v1/users",
                            "body": {"mode": "raw", "raw": '{"name": "bob"}'},
                        },
                    }
                ],
            },
        ],
    }
    result = parse_schema("postman", json.dumps(collection))
    assert len(result.endpoints) == 2
    list_endpoint = next(e for e in result.endpoints if e.method == "GET")
    assert list_endpoint.path == "/api/v1/users"
    assert any(p.name == "limit" and p.location == "query" for p in list_endpoint.parameters)
    assert any(p.name == "Authorization" and p.location == "header" for p in list_endpoint.parameters)
    create_endpoint = next(e for e in result.endpoints if e.method == "POST")
    assert create_endpoint.request_body_example == {"name": "bob"}
    assert create_endpoint.base_url == "https://api.example.com"


def test_parse_postman_string_url_query_and_disabled_fields():
    collection = {
        "info": {"name": "Query"},
        "item": [
            {
                "name": "Search",
                "request": {
                    "method": "GET",
                    "url": "https://api.example.com/search?limit=0&enabled=false&empty=",
                    "header": [
                        {"key": "X-Enabled", "value": "yes"},
                        {"key": "X-Skipped", "value": "no", "disabled": True},
                    ],
                },
            }
        ],
    }

    endpoint = parse_schema("postman", json.dumps(collection)).endpoints[0]

    assert [(parameter.name, parameter.example) for parameter in endpoint.parameters] == [
        ("limit", "0"),
        ("enabled", "false"),
        ("empty", ""),
        ("X-Enabled", "yes"),
    ]


def test_parse_postman_form_data_body_and_skips_disabled_fields():
    collection = {
        "info": {"name": "Form"},
        "item": [
            {
                "name": "Upload metadata",
                "request": {
                    "method": "POST",
                    "url": {
                        "raw": "https://api.example.com/upload",
                        "host": ["api", "example", "com"],
                        "path": ["upload"],
                    },
                    "body": {
                        "mode": "formdata",
                        "formdata": [
                            {"key": "name", "value": "alice"},
                            {"key": "ignored", "value": "x", "disabled": True},
                        ],
                    },
                },
            }
        ],
    }

    endpoint = parse_schema("postman", json.dumps(collection)).endpoints[0]

    assert endpoint.request_body_example == {"name": "alice"}


def test_parse_postman_empty_items_warning():
    result = parse_schema("postman", json.dumps({"info": {}, "item": []}))
    assert result.endpoints == []
    assert result.warnings


# ──────────── cURL ────────────


def test_parse_curl_with_post_body_and_headers():
    raw = (
        'curl -X POST "https://api.example.com/api/v1/login" '
        '-H "Content-Type: application/json" '
        '--data-raw \'{"username": "u", "password": "p"}\''
    )
    result = parse_schema("curl", raw)
    assert len(result.endpoints) == 1
    endpoint = result.endpoints[0]
    assert endpoint.method == "POST"
    assert endpoint.path == "/api/v1/login"
    assert endpoint.base_url == "https://api.example.com"
    assert endpoint.request_body_example == {"username": "u", "password": "p"}
    assert any(p.name == "Content-Type" for p in endpoint.parameters)


def test_parse_curl_default_method_get():
    raw = 'curl "https://api.example.com/health"'
    result = parse_schema("curl", raw)
    assert result.endpoints[0].method == "GET"
    assert result.endpoints[0].path == "/health"


def test_parse_curl_data_implies_post():
    raw = 'curl "https://api.example.com/post" --data \'{"a": 1}\''
    result = parse_schema("curl", raw)
    assert result.endpoints[0].method == "POST"
    assert result.endpoints[0].request_body_example == {"a": 1}


def test_parse_curl_invalid_raises():
    with pytest.raises(ValueError):
        parse_schema("curl", "not a curl command")


# ──────────── 接口样例 ────────────


def test_parse_sample_http_text_extracts_request_and_response_examples():
    raw = """
POST /api/v1/login
Request: {"username": "demo", "password": "secret"}
Response: {"code": 0, "token": "abc"}
"""
    result = parse_schema("sample", raw)

    assert len(result.endpoints) == 1
    endpoint = result.endpoints[0]
    assert endpoint.method == "POST"
    assert endpoint.path == "/api/v1/login"
    assert endpoint.request_body_example == {"username": "demo", "password": "secret"}
    assert endpoint.response_example == {"code": 0, "token": "abc"}


def test_parse_sample_json_object_with_headers_and_query():
    raw = json.dumps(
        {
            "method": "GET",
            "url": "https://api.example.com/api/v1/orders",
            "headers": {"Authorization": "Bearer token"},
            "query": {"status": "paid"},
            "response": {"items": []},
        }
    )
    result = parse_schema("sample", raw)

    endpoint = result.endpoints[0]
    assert endpoint.method == "GET"
    assert endpoint.path == "/api/v1/orders"
    assert endpoint.response_example == {"items": []}
    assert any(p.name == "Authorization" and p.location == "header" for p in endpoint.parameters)
    assert any(p.name == "status" and p.location == "query" for p in endpoint.parameters)


def test_parse_sample_plain_json_becomes_request_example():
    result = parse_schema("sample", '{"sku": "A001", "count": 2}')

    endpoint = result.endpoints[0]
    assert endpoint.method == "POST"
    assert endpoint.path == "/sample-endpoint"
    assert endpoint.request_body_example == {"sku": "A001", "count": 2}
    assert result.warnings


def test_parse_schema_unsupported_source_type():
    with pytest.raises(ValueError):
        parse_schema("har", "{}")
