from pathlib import Path


def repo_path(path: str) -> Path:
    return Path(__file__).resolve().parents[2] / path


def test_audit_logs_router_registered():
    content = repo_path("app/api/v1/router.py").read_text(encoding="utf-8")

    assert "projects" in content
    assert "router.include_router(projects.router)" in content


def test_audit_logs_endpoint_requires_admin():
    """审计日志端点（projects.list_audit_logs）必须由 require_admin 守卫。

    projects.py 含多个 require_admin 端点，故精确定位 list_audit_logs 的
    函数签名段落断言，避免「文件里出现 require_admin」造成的误判。
    """
    content = repo_path("app/api/v1/projects.py").read_text(encoding="utf-8")

    assert '@router.get("/audit-logs"' in content

    start = content.index("async def list_audit_logs")
    signature = content[start : content.index("):", start) + 2]
    assert "Depends(require_admin)" in signature


def test_audit_logs_endpoint_supports_a_time_window_and_rejects_reversed_bounds():
    content = repo_path("app/api/v1/projects.py").read_text(encoding="utf-8")

    start = content.index("async def list_audit_logs")
    body = content[start:]
    assert "created_from: datetime | None = Query(None)" in body
    assert "created_to: datetime | None = Query(None)" in body
    assert "def _audit_log_filters(" in content
    assert "created_to < created_from" in content
    assert "AuditLog.created_at >= created_from" in content
    assert "AuditLog.created_at <= created_to" in content


def test_audit_logs_export_is_bounded_and_spreadsheet_safe():
    content = repo_path("app/api/v1/projects.py").read_text(encoding="utf-8")

    assert '@router.get("/audit-logs/export")' in content
    assert "limit: int = Query(5000, ge=1, le=10000)" in content
    assert "_audit_log_csv_cell" in content
    assert "writer.writerow(" in content
    start = content.index("async def export_audit_logs")
    signature = content[start : content.index("):", start) + 2]
    body = content[start:]
    assert "current_user: User = Depends(require_admin)" in signature
    assert 'action="audit_log_export"' in body
    assert "detail=json.dumps(" in body
    assert "await db.commit()" in body
