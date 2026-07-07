"""Integration paths for notification configs and bug reporting.

External SMTP / issue-tracker calls are replaced with monkeypatched functions,
while the API, auth, encryption, database writes, and run-summary persistence go
through the real app stack and real Postgres/Redis/MinIO test services.
"""

from __future__ import annotations

import pytest


async def _create_project(async_client, auth_headers, unique_name, suffix: str) -> int:
    resp = await async_client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json={
            "name": f"proj-{suffix}-{unique_name}",
            "project_code": f"IT-{suffix}-{unique_name}",
            "description": "integration",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_approved_case(
    async_client,
    auth_headers,
    unique_name,
    suffix: str,
    project_id: int | None = None,
) -> tuple[int, int]:
    if project_id is None:
        project_id = await _create_project(async_client, auth_headers, unique_name, suffix)

    resp = await async_client.post(
        "/api/v1/modules",
        headers=auth_headers,
        json={"name": f"mod-{suffix}-{unique_name}", "project_id": project_id},
    )
    assert resp.status_code == 201, resp.text
    module_id = resp.json()["id"]

    resp = await async_client.post(
        "/api/v1/cases",
        headers=auth_headers,
        json={
            "name": f"case-{suffix}-{unique_name}",
            "case_type": "api",
            "module_id": module_id,
            "tags": ["integration", suffix],
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
        json={"comment": "ready for integration bug flow"},
    )
    assert resp.status_code == 200, resp.text
    resp = await async_client.post(
        f"/api/v1/cases/{case_id}/approve",
        headers=auth_headers,
        json={"comment": "approved for integration bug flow"},
    )
    assert resp.status_code == 200, resp.text
    return project_id, case_id


async def _create_failed_run(
    async_client,
    auth_headers,
    db_session,
    unique_name,
    suffix: str,
    project_id: int | None = None,
) -> tuple[int, int]:
    from app.models.case import RunStatus, TestRun

    project_id, case_id = await _create_approved_case(
        async_client,
        auth_headers,
        unique_name,
        suffix,
        project_id=project_id,
    )
    resp = await async_client.post(
        f"/api/v1/cases/{case_id}/run",
        headers=auth_headers,
        json={"environment_id": None, "extra_vars": {"source": "integration"}},
    )
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["id"]

    run = await db_session.get(TestRun, run_id)
    assert run is not None
    run.status = RunStatus.failed
    run.error_message = f"{suffix} integration failure"
    run.result_summary = {"total": 1, "passed": 0, "failed": 1, "error": 0}
    await db_session.commit()
    return project_id, run_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_notification_config_masks_and_test_send_paths(async_client, auth_headers, unique_name, monkeypatch):
    from app.services import notifier

    project_id = await _create_project(async_client, auth_headers, unique_name, "notification")
    sent: dict[str, object] = {}

    async def fake_send_email(config, summary):
        sent["email_config"] = config
        sent["email_summary"] = summary

    async def fake_send_wechat(_config, _summary):
        raise RuntimeError("invalid webhook")

    monkeypatch.setattr(notifier, "_send_email", fake_send_email)
    monkeypatch.setattr(notifier, "_send_wechat", fake_send_wechat)

    resp = await async_client.post(
        "/api/v1/notifications",
        headers=auth_headers,
        json={
            "name": f"email-{unique_name}",
            "project_id": project_id,
            "channel": "email",
            "config": {
                "smtp_host": "smtp.example.test",
                "smtp_port": 587,
                "username": "qa@example.test",
                "password": "email-secret",
                "recipients": ["qa@example.test"],
                "status_filters": ["passed", "failed"],
                "language": "en-US",
            },
            "is_enabled": True,
        },
    )
    assert resp.status_code == 201, resp.text
    email_cfg_id = resp.json()["id"]

    resp = await async_client.get(f"/api/v1/notifications?project_id={project_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    email_cfg = next(item for item in resp.json() if item["id"] == email_cfg_id)
    assert email_cfg["config"]["password"] == "******"
    assert email_cfg["config"]["recipients"] == ["qa@example.test"]

    resp = await async_client.post(f"/api/v1/notifications/{email_cfg_id}/test", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert sent["email_config"]["password"] == "email-secret"
    assert sent["email_summary"]["title"] == "ATP notification test"

    resp = await async_client.post(
        "/api/v1/notifications",
        headers=auth_headers,
        json={
            "name": f"wechat-{unique_name}",
            "project_id": project_id,
            "channel": "wechat",
            "config": {"webhook_url": "https://qy.example.test/hook?key=secret"},
            "is_enabled": True,
        },
    )
    assert resp.status_code == 201, resp.text
    wechat_cfg_id = resp.json()["id"]

    resp = await async_client.post(f"/api/v1/notifications/{wechat_cfg_id}/test", headers=auth_headers)
    assert resp.status_code == 500, resp.text
    assert "invalid webhook" in resp.json()["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bug_tracker_connection_create_duplicate_status_and_manual_link(
    async_client,
    auth_headers,
    db_session,
    unique_name,
    monkeypatch,
):
    from app.api.v1 import bug_trackers

    captured: dict[str, object] = {}

    async def fake_test_connection(tracker_type, config):
        captured["connection"] = {"tracker_type": tracker_type, "config": config}
        return {"ok": True, "message": "jira ok"}

    async def fake_find_duplicate_bug(tracker_type, config, title):
        captured["duplicate_lookup"] = {"tracker_type": tracker_type, "config": config, "title": title}
        return {
            "bug_id": "ATP-12",
            "bug_url": "https://jira.example.test/browse/ATP-12",
            "title": title,
        }

    async def fake_create_bug(**kwargs):
        captured["create_bug"] = kwargs
        return {
            "bug_id": "ATP-99",
            "bug_url": "https://jira.example.test/browse/ATP-99",
            "title": kwargs["title"],
        }

    async def fake_get_bug_status(**kwargs):
        captured["bug_status"] = kwargs
        return {
            "bug_id": kwargs["bug_id"],
            "status": "closed",
            "bug_url": f"https://jira.example.test/browse/{kwargs['bug_id']}",
        }

    monkeypatch.setattr(bug_trackers, "test_connection", fake_test_connection)
    monkeypatch.setattr(bug_trackers, "find_duplicate_bug", fake_find_duplicate_bug)
    monkeypatch.setattr(bug_trackers, "get_bug_status", fake_get_bug_status)

    project_id, duplicate_run_id = await _create_failed_run(
        async_client,
        auth_headers,
        db_session,
        unique_name,
        "bug-duplicate",
    )

    resp = await async_client.post(
        "/api/v1/bug-trackers",
        headers=auth_headers,
        json={
            "name": f"jira-{unique_name}",
            "project_id": project_id,
            "tracker_type": "jira",
            "config": {
                "base_url": "https://jira.example.test",
                "email": "qa@example.test",
                "api_token": "jira-secret",
                "project_key": "ATP",
            },
            "field_mapping": {"labels": ["integration"]},
            "is_enabled": True,
        },
    )
    assert resp.status_code == 201, resp.text
    tracker = resp.json()
    tracker_id = tracker["id"]
    assert tracker["config"]["api_token"] == "******"

    resp = await async_client.post(
        "/api/v1/bug-trackers/test-connection",
        headers=auth_headers,
        json={"tracker_id": tracker_id, "tracker_type": "jira", "config": {}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
    assert captured["connection"]["config"]["api_token"] == "jira-secret"

    resp = await async_client.post(
        f"/api/v1/runs/{duplicate_run_id}/create-bug",
        headers=auth_headers,
        json={"tracker_id": tracker_id},
    )
    assert resp.status_code == 200, resp.text
    duplicate_result = resp.json()
    assert duplicate_result["duplicate_of"] == "ATP-12"
    assert duplicate_result["attachment_uploaded"] is False

    resp = await async_client.get(f"/api/v1/runs/{duplicate_run_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    duplicate_summary = resp.json()["result_summary"]
    assert duplicate_summary["bug"]["bug_id"] == "ATP-12"
    assert duplicate_summary["bug"]["duplicate_of"] == "ATP-12"
    assert duplicate_summary["bug"]["tracker_id"] == tracker_id

    resp = await async_client.get(f"/api/v1/runs/{duplicate_run_id}/bug-status", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "closed"
    assert captured["bug_status"]["config"]["api_token"] == "jira-secret"

    async def fake_find_no_duplicate(**_kwargs):
        return None

    monkeypatch.setattr(bug_trackers, "find_duplicate_bug", fake_find_no_duplicate)
    monkeypatch.setattr(bug_trackers, "create_bug", fake_create_bug)

    _, create_run_id = await _create_failed_run(
        async_client,
        auth_headers,
        db_session,
        unique_name,
        "bug-create",
        project_id=project_id,
    )
    resp = await async_client.post(
        f"/api/v1/runs/{create_run_id}/create-bug",
        headers=auth_headers,
        json={"tracker_id": tracker_id},
    )
    assert resp.status_code == 200, resp.text
    create_result = resp.json()
    assert create_result["bug_id"] == "ATP-99"
    assert create_result["duplicate_of"] is None
    assert captured["create_bug"]["field_mapping"] == {"labels": ["integration"]}
    assert captured["create_bug"]["config"]["api_token"] == "jira-secret"

    resp = await async_client.get(f"/api/v1/runs/{create_run_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    create_summary = resp.json()["result_summary"]
    assert create_summary["bug"]["bug_id"] == "ATP-99"
    assert create_summary["bug"]["duplicate_of"] is None
    assert create_summary["bug"]["tracker_id"] == tracker_id

    _, linked_run_id = await _create_failed_run(
        async_client,
        auth_headers,
        db_session,
        unique_name,
        "bug-link",
        project_id=project_id,
    )
    resp = await async_client.post(
        f"/api/v1/runs/{linked_run_id}/link-bug",
        headers=auth_headers,
        json={
            "tracker_id": tracker_id,
            "bug_id": "ATP-77",
            "bug_url": "https://jira.example.test/browse/ATP-77",
            "title": "Existing bug",
            "status": "linked",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["bug_id"] == "ATP-77"

    resp = await async_client.get(f"/api/v1/runs/{linked_run_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    linked_summary = resp.json()["result_summary"]
    assert linked_summary["bug"]["bug_id"] == "ATP-77"
    assert linked_summary["bug"]["linked_manually"] is True
    assert linked_summary["bug"]["tracker_id"] == tracker_id
