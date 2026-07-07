"""集成路径 3：login → 创建项目 → 创建 mock 规则 → GET /mock/{pid}/path 命中。"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_rule_creates_and_serves_response(async_client, auth_headers, unique_name):
    # 1. create project
    resp = await async_client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"name": f"proj-mock-{unique_name}", "project_code": f"IT-MOCK-{unique_name}"},
    )
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]

    # 2. create mock rule
    rule_payload = {
        "name": f"rule-{unique_name}",
        "project_id": project_id,
        "method": "GET",
        "path": f"/ping/{unique_name}",
        "status_code": 200,
        "response_headers": {"Content-Type": "application/json"},
        "response_body": '{"ok": true, "marker": "%s"}' % unique_name,
        "is_enabled": True,
    }
    resp = await async_client.post("/api/v1/mock-rules", headers=auth_headers, json=rule_payload)
    assert resp.status_code == 201, resp.text

    # 3. GET /mock/{project_id}/ping/{name} 命中
    resp = await async_client.get(f"/mock/{project_id}/ping/{unique_name}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {"ok": True, "marker": unique_name}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mock_unmatched_path_returns_404(async_client, auth_headers, unique_name):
    resp = await async_client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"name": f"proj-mock-miss-{unique_name}", "project_code": f"IT-MOCK-MISS-{unique_name}"},
    )
    project_id = resp.json()["id"]

    # 无任何规则注册时，未命中路径预期 404
    resp = await async_client.get(f"/mock/{project_id}/nonexistent/{unique_name}")
    assert resp.status_code == 404
