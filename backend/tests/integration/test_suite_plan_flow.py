"""Integration path: case -> suite run -> plan run.

This covers the API + DB + Celery enqueue boundary for suite and plan execution.
The worker does not need to consume the jobs; the contract protected here is that
approved cases can be assembled into suites/plans and trigger pending run records.
"""

import pytest


async def _create_approved_api_case(async_client, auth_headers, unique_name):
    resp = await async_client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "name": f"proj-suite-plan-{unique_name}",
            "project_code": f"IT-SUITE-PLAN-{unique_name}",
            "description": "integration",
        },
    )
    assert resp.status_code == 201, resp.text
    project_id = resp.json()["id"]

    resp = await async_client.post(
        "/api/v1/modules",
        headers=auth_headers,
        json={"name": f"mod-suite-plan-{unique_name}", "project_id": project_id},
    )
    assert resp.status_code == 201, resp.text
    module_id = resp.json()["id"]

    resp = await async_client.post(
        "/api/v1/cases",
        headers=auth_headers,
        json={
            "name": f"case-suite-plan-{unique_name}",
            "case_type": "api",
            "module_id": module_id,
            "tags": ["integration", "suite-plan"],
            "automation_status": "auto",
            "steps": [
                {
                    "step_order": 1,
                    "name": "GET mock echo",
                    "action": "GET mock echo",
                    "config": {
                        "method": "GET",
                        "url": f"http://test/mock/{project_id}/echo",
                        "assertions": [{"type": "status_code", "expected": 200}],
                    },
                }
            ],
            "config": {},
        },
    )
    assert resp.status_code in (200, 201), resp.text
    case_id = resp.json()["id"]

    resp = await async_client.post(
        f"/api/v1/cases/{case_id}/submit-review",
        headers=auth_headers,
        json={"comment": "ready for integration suite run"},
    )
    assert resp.status_code == 200, resp.text
    resp = await async_client.post(
        f"/api/v1/cases/{case_id}/approve",
        headers=auth_headers,
        json={"comment": "approved for integration suite run"},
    )
    assert resp.status_code == 200, resp.text
    return project_id, case_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_suite_run_and_plan_run_chain(async_client, auth_headers, unique_name):
    project_id, case_id = await _create_approved_api_case(async_client, auth_headers, unique_name)

    resp = await async_client.post(
        "/api/v1/suites",
        headers=auth_headers,
        json={
            "name": f"suite-{unique_name}",
            "description": "integration suite",
            "project_id": project_id,
            "case_ids": [{"case_id": case_id, "sort": 0}],
            "config": {"execution_mode": "sequential"},
        },
    )
    assert resp.status_code == 201, resp.text
    suite_id = resp.json()["id"]

    resp = await async_client.post(
        f"/api/v1/suites/{suite_id}/run",
        headers=auth_headers,
        json={"env_id": None, "extra_vars": {"source": "integration"}},
    )
    assert resp.status_code == 202, resp.text
    suite_run = resp.json()
    assert suite_run["suite_id"] == suite_id
    assert suite_run["status"] == "pending"

    resp = await async_client.get(f"/api/v1/suite-runs?suite_id={suite_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert any(item["id"] == suite_run["id"] for item in resp.json())

    resp = await async_client.post(
        "/api/v1/plans",
        headers=auth_headers,
        json={
            "name": f"plan-{unique_name}",
            "description": "integration plan",
            "project_id": project_id,
            "suite_ids": [{"suite_id": suite_id, "sort": 0}],
            "schedule_type": "manual",
            "is_enabled": True,
            "config": {"retry": 0},
        },
    )
    assert resp.status_code == 201, resp.text
    plan_id = resp.json()["id"]

    resp = await async_client.post(
        f"/api/v1/plans/{plan_id}/run",
        headers=auth_headers,
        json={"env_id": None, "extra_vars": {"source": "integration"}},
    )
    assert resp.status_code == 202, resp.text
    plan_run = resp.json()
    assert plan_run["plan_id"] == plan_id
    assert plan_run["trigger_type"] == "manual"
    assert plan_run["status"] == "pending"

    resp = await async_client.get(f"/api/v1/plan-runs?plan_id={plan_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert any(item["id"] == plan_run["id"] for item in resp.json())
