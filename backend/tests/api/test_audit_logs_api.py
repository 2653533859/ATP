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
