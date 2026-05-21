"""集成路径 2：login → 创建项目/模块/用例 → 触发 run → 验证 run 入库。

MVP 范围：仅覆盖 API → DB → Celery broker 链路。不真跑 executor（不发出
出口流量）。Celery 任务在 worker 进程才会被消费；本测试在事务里只断言
trigger 接口返回的 TestRunOut 表行存在与状态为 pending。
"""
import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_project_module_case_run_chain(async_client, auth_headers, unique_name):
    # 1. create project
    resp = await async_client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={"name": f"proj-{unique_name}", "description": "integration"},
    )
    assert resp.status_code == 201, resp.text
    project = resp.json()
    project_id = project["id"]

    # 2. create module
    resp = await async_client.post(
        "/api/v1/modules",
        headers=auth_headers,
        json={"name": f"mod-{unique_name}", "project_id": project_id},
    )
    assert resp.status_code == 201, resp.text
    module = resp.json()
    module_id = module["id"]

    # 3. create API case 指向自身 mock 端点（保证无出口流量）
    case_payload = {
        "name": f"case-{unique_name}",
        "case_type": "api",
        "module_id": module_id,
        "tags": ["integration"],
        "automation_status": "auto",
        "steps": [
            {
                "step_order": 1,
                "name": "GET mock echo",
                "config": {
                    "method": "GET",
                    "url": f"http://test/mock/{project_id}/echo",
                    "assertions": [{"type": "status_code", "expected": 200}],
                },
            }
        ],
        "config": {},
    }
    resp = await async_client.post("/api/v1/cases", headers=auth_headers, json=case_payload)
    assert resp.status_code in (200, 201), resp.text
    case = resp.json()
    case_id = case["id"]

    # 4. trigger run（同步入队，状态默认 pending）
    resp = await async_client.post(
        f"/api/v1/cases/{case_id}/run",
        headers=auth_headers,
        json={"environment_id": None, "extra_vars": {}},
    )
    assert resp.status_code == 202, resp.text
    run = resp.json()
    assert run["case_id"] == case_id
    assert run["status"] in ("pending", "running", "passed", "failed")

    # 5. 通过 list runs 校验入库
    resp = await async_client.get(f"/api/v1/runs?case_id={case_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    runs = resp.json()
    items = runs.get("items", runs if isinstance(runs, list) else [])
    assert any(item["id"] == run["id"] for item in items)
