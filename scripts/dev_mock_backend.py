from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import urllib.parse


ADMIN_USER = {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "is_active": True,
    "role": "admin",
    "language": "zh-CN",
}
TOKENS = {
    "access_token": "mock-access-token",
    "refresh_token": "mock-refresh-token",
    "token_type": "bearer",
}
PROJECTS = [
    {
        "id": 1,
        "name": "E2E 测试项目",
        "project_code": "E2E",
        "description": "Playwright fixture project",
        "owner_id": 1,
        "ai_llm_config_id": None,
        "run_retention_days_override": None,
        "created_at": "2026-05-21T00:00:00Z",
        "updated_at": "2026-05-21T00:00:00Z",
    }
]
MODULES = [
    {
        "id": 10,
        "name": "根模块",
        "module_code": "root",
        "project_id": 1,
        "parent_id": None,
        "sort_order": 0,
        "created_at": "2026-05-21T00:00:00Z",
        "children": [],
    }
]
CASES = [
    {
        "id": 100,
        "name": "GET /health 烟测",
        "description": None,
        "case_code": "C-100",
        "summary": "简单健康检查",
        "case_type": "api",
        "status": "active",
        "priority": "P1",
        "case_level": "smoke",
        "review_status": "approved",
        "automation_status": "auto",
        "tags": ["smoke"],
        "module_id": 10,
        "creator_id": 1,
        "owner_id": 1,
        "is_ready_for_execution": True,
        "created_at": "2026-05-21T00:00:00Z",
        "updated_at": "2026-05-21T00:00:00Z",
    }
]
OVERVIEW = {
    "total_cases": 12,
    "total_runs": 99,
    "pass_rate": 0.875,
    "recent_runs_7d": 21,
}
PASS_RATE_TREND = [
    {"date": f"2026-05-{15 + i}", "total": 10 + i, "passed": 8 + i, "rate": 0.8}
    for i in range(7)
]
DURATION_TREND = [
    {
        "date": item["date"],
        "avg_duration_ms": 500 + 10 * item["total"],
        "max_duration_ms": 1500,
        "run_count": item["total"],
    }
    for item in PASS_RATE_TREND
]


class Handler(BaseHTTPRequestHandler):
    def send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:5173")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_json({})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path.endswith("/auth/login") or path.endswith("/auth/refresh"):
            self.send_json(TOKENS)
            return
        if path.endswith("/cases/100/run"):
            self.send_json(
                {
                    "id": 9001,
                    "case_id": 100,
                    "status": "pending",
                    "created_at": "2026-05-21T10:00:00Z",
                    "steps": [],
                }
            )
            return
        self.send_json({"ok": True})

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/health":
            self.send_json({"status": "ok", "mode": "mock"})
        elif path.endswith("/auth/me"):
            self.send_json(ADMIN_USER)
        elif path.endswith("/projects"):
            self.send_json(PROJECTS)
        elif path.endswith("/projects/1/modules"):
            self.send_json(MODULES)
        elif path.endswith("/cases"):
            self.send_json({"items": CASES, "total": len(CASES), "page": 1, "page_size": 20})
        elif path.endswith("/statistics/overview"):
            self.send_json(OVERVIEW)
        elif path.endswith("/statistics/pass-rate-trend"):
            self.send_json(PASS_RATE_TREND)
        elif path.endswith("/statistics/duration-trend"):
            self.send_json(DURATION_TREND)
        elif "/statistics/" in path:
            self.send_json([])
        elif path.endswith("/runs"):
            self.send_json({"items": [], "total": 0, "page": 1, "page_size": 20})
        elif (
            path.endswith("/suites")
            or path.endswith("/plans")
            or path.endswith("/devices")
            or path.endswith("/apks")
            or path.endswith("/mock-rules")
        ):
            self.send_json([])
        else:
            self.send_json([])

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
