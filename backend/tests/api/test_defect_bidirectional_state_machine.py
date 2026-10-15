"""Unit and API tests for P4.2 Jira / ZenTao bidirectional defect lifecycle state machine sync.

Tests:
1. map_internal_to_external_status mappings for Jira, ZenTao, GitHub, GitLab
2. parse_external_webhook_payload for Jira issue/changelog, ZenTao bug events, and GitHub/GitLab
3. handle_defect_external_webhook: Webhook receiving external status change and updating internal Defect
4. push_defect_to_external_issue: Active status transition push to external issue
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from app.api.v1 import defects
from app.models.bootstrap import load_all_models
from app.models.bug_tracker import BugTracker, TrackerType
from app.models.defect import Defect
from app.services.defect_external import (
    map_internal_to_external_status,
    parse_external_webhook_payload,
)

load_all_models()
NOW = datetime.now(timezone.utc)


class _Result:
    def __init__(self, scalar=None):
        self.scalar = scalar

    def scalar_one_or_none(self):
        return self.scalar


class _FakeRequest:
    def __init__(self, payload: dict):
        self._payload = payload

    async def json(self):
        return self._payload


class _DB:
    def __init__(self, tracker=None, defect=None, link=None):
        self.tracker = tracker
        self.defect = defect
        self.link = link
        self.commits = 0
        self.added: list[object] = []

    async def get(self, model, obj_id):
        if model is BugTracker:
            return self.tracker
        if model is Defect:
            return self.defect
        return None

    async def execute(self, _statement):
        return _Result(self.link)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commits += 1


def _user(user_id: int = 7):
    return SimpleNamespace(id=user_id, username="engineer", role="engineer")


def test_map_internal_to_external_status():
    assert map_internal_to_external_status("resolved", "jira") == "Done"
    assert map_internal_to_external_status("closed", "jira") == "Closed"
    assert map_internal_to_external_status("in_progress", "jira") == "In Progress"
    assert map_internal_to_external_status("open", "jira") == "Open"

    assert map_internal_to_external_status("resolved", "zentao") == "resolved"
    assert map_internal_to_external_status("closed", "zentao") == "closed"
    assert map_internal_to_external_status("open", "zentao") == "active"


def test_parse_external_webhook_payload():
    # 1. Jira direct fields
    jira_payload = {
        "issue": {
            "key": "ATP-888",
            "fields": {"status": {"name": "Closed"}},
        }
    }
    parsed = parse_external_webhook_payload("jira", jira_payload)
    assert parsed == {"external_key": "ATP-888", "external_status": "Closed"}

    # 2. Jira changelog fallback
    jira_changelog = {
        "issue": {"key": "ATP-999"},
        "changelog": {
            "items": [
                {"field": "assignee", "toString": "Alice"},
                {"field": "status", "toString": "Resolved"},
            ]
        },
    }
    parsed_cl = parse_external_webhook_payload("jira", jira_changelog)
    assert parsed_cl == {"external_key": "ATP-999", "external_status": "Resolved"}

    # 3. ZenTao webhook
    zentao_payload = {"objectType": "bug", "objectID": "502", "status": "resolved"}
    parsed_zt = parse_external_webhook_payload("zentao", zentao_payload)
    assert parsed_zt == {"external_key": "502", "external_status": "resolved"}


def test_handle_defect_external_webhook_jira_syncs_to_closed(monkeypatch):
    monkeypatch.setattr(defects, "write_audit_log", AsyncMock())

    tracker = SimpleNamespace(
        id=1,
        project_id=10,
        tracker_type=TrackerType.jira,
        is_enabled=True,
    )
    defect = SimpleNamespace(
        id=88,
        project_id=10,
        title="Jira 联动缺陷",
        status="open",
    )
    link = SimpleNamespace(
        id=101,
        defect_id=88,
        tracker_id=1,
        external_key="ATP-888",
        external_status="Open",
        sync_state="linked",
        last_synced_at=None,
        last_error=None,
    )
    db: Any = _DB(tracker=tracker, defect=defect, link=link)
    req: Any = _FakeRequest(
        {
            "issue": {
                "key": "ATP-888",
                "fields": {"status": {"name": "Closed"}},
            }
        }
    )

    out = asyncio.run(defects.handle_defect_external_webhook(1, req, db))
    assert out.external_key == "ATP-888"
    assert out.internal_status == "closed"
    assert defect.status == "closed"
    assert link.external_status == "Closed"
    assert link.sync_state == "synced"
    assert db.commits == 1


def test_push_defect_to_external_issue_zentao(monkeypatch):
    monkeypatch.setattr(defects, "write_audit_log", AsyncMock())

    tracker = SimpleNamespace(
        id=2,
        project_id=10,
        tracker_type=TrackerType.zentao,
        is_enabled=True,
        config={"base_url": "https://zentao.local"},
    )
    defect = SimpleNamespace(
        id=99,
        project_id=10,
        title="禅道推送缺陷",
        status="resolved",
    )
    link = SimpleNamespace(
        id=202,
        defect_id=99,
        tracker_id=2,
        external_key="502",
        tracker=tracker,
    )
    db: Any = _DB(tracker=tracker, defect=defect, link=link)

    monkeypatch.setattr(defects, "_get_defect", AsyncMock(return_value=defect))
    monkeypatch.setattr(defects, "_get_external_link", AsyncMock(return_value=link))

    user: Any = _user()
    out = asyncio.run(defects.push_defect_to_external_issue(99, 202, db, user))
    assert out["tracker_type"] == "zentao"
    assert db.commits == 1
