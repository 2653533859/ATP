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
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "example": {"name": "alice"}
                            }
                        }
                    },
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
    assert get_endpoint.summary == "Get user"
    assert get_endpoint.parameters[0].name == "id"
    assert get_endpoint.parameters[0].location == "path"
    assert get_endpoint.parameters[0].required is True
    post_endpoint = next(e for e in result.endpoints if e.method == "POST")
    assert post_endpoint.request_body_example == {"name": "alice"}


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


def test_parse_schema_unsupported_source_type():
    with pytest.raises(ValueError):
        parse_schema("har", "{}")
