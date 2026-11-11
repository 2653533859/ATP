"""真实链路冒烟：启动本地 FastAPI 应用，只读核对 Android Agent M3 路由契约。

不发起设备操作、不写业务数据；仅验证 OpenAPI 中声明的路径/方法与权限依赖存在。
用法：python scripts/android_agent_m3_smoke.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

EXPECTED_ROUTES = {
    ("post", "/api/v1/projects/{project_id}/android-agent/sessions"),
    ("post", "/api/v1/projects/{project_id}/android-agent/sessions/{session_id}/start"),
    ("get", "/api/v1/projects/{project_id}/android-agent/sessions/{session_id}"),
    ("post", "/api/v1/projects/{project_id}/android-agent/sessions/{session_id}/control"),
    ("post", "/api/v1/projects/{project_id}/android-agent/sessions/{session_id}/manual-action"),
    ("get", "/api/v1/projects/{project_id}/android-agent/sessions/{session_id}/events"),
    ("post", "/api/v1/projects/{project_id}/android-agent/sessions/{session_id}/drafts"),
    ("get", "/api/v1/projects/{project_id}/android-agent/drafts/{draft_id}"),
    ("patch", "/api/v1/projects/{project_id}/android-agent/drafts/{draft_id}"),
    ("get", "/api/v1/projects/{project_id}/android-agent/drafts/{draft_id}/replay-preview"),
    ("post", "/api/v1/projects/{project_id}/android-agent/drafts/{draft_id}/replays"),
    ("get", "/api/v1/projects/{project_id}/android-agent/replays/{replay_id}"),
    ("post", "/api/v1/projects/{project_id}/android-agent/drafts/{draft_id}/publish"),
}


def main() -> int:
    from app.main import app

    schema = app.openapi()
    available = {(method.lower(), path) for path, operations in schema["paths"].items() for method in operations}
    missing = sorted(EXPECTED_ROUTES - available)
    if missing:
        print(json.dumps({"ok": False, "missing": missing}, ensure_ascii=False, indent=2))
        return 1

    publish = schema["paths"]["/api/v1/projects/{project_id}/android-agent/drafts/{draft_id}/publish"]["post"]
    header_names = {param["name"] for param in publish.get("parameters", []) if param.get("in") == "header"}
    if "Idempotency-Key" not in header_names:
        print(json.dumps({"ok": False, "reason": "publish 缺少 Idempotency-Key 头"}, ensure_ascii=False))
        return 1

    print(
        json.dumps(
            {"ok": True, "routes": len(EXPECTED_ROUTES), "openapi_version": schema.get("openapi")}, ensure_ascii=False
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
