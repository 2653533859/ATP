"""P1.3 Mock 独立端口：验证 mock_main 路由模板与基础结构。

不实际启动 FastAPI server，仅验证：
- /health 端点可用
- 路由注册了 /{project_id}/{path:path} 模板（不含 /mock 前缀）
- 复用了 mock_server.mock_endpoint 函数（同一可调用对象）
"""
import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# stub 底层依赖避免真实 DB / MinIO / OTel
_minio_stub = sys.modules.setdefault(
    "app.core.minio_client",
    types.SimpleNamespace(
        ensure_bucket=lambda: None,
        read_bytes=lambda *_a, **_kw: b"",
        upload_bytes=lambda *_a, **_kw: None,
        list_objects=lambda *_a, **_kw: [],
        delete_file=lambda *_a, **_kw: None,
    ),
)
# 若 conftest 已 setdefault 但缺字段，补齐
for _name, _fn in (
    ("ensure_bucket", lambda: None),
    ("read_bytes", lambda *_a, **_kw: b""),
    ("upload_bytes", lambda *_a, **_kw: None),
):
    if not hasattr(_minio_stub, _name):
        setattr(_minio_stub, _name, _fn)
_db_stub = sys.modules.setdefault(
    "app.core.database",
    types.SimpleNamespace(
        get_db=lambda: None,
        AsyncSessionLocal=lambda *a, **k: None,
        engine=types.SimpleNamespace(dispose=lambda: None),
    ),
)
if not hasattr(_db_stub, "engine"):
    _db_stub.engine = types.SimpleNamespace(dispose=lambda: None)
if not hasattr(_db_stub, "AsyncSessionLocal"):
    _db_stub.AsyncSessionLocal = lambda *a, **k: None

sys.modules.setdefault(
    "app.core.redis_client",
    types.SimpleNamespace(
        get_json_cache=lambda *a, **kw: None,
        set_json_cache=lambda *a, **kw: None,
        delete_json_cache=lambda *a, **kw: None,
        delete_json_cache_pattern=lambda *a, **kw: None,
        publish_run_event=lambda *a, **kw: None,
        get_async_redis=lambda *a, **kw: None,
    ),
)


def test_mock_main_app_has_health_and_mock_routes():
    from app.mock_main import app
    from app.api.v1.mock_server import mock_endpoint as shared_mock_endpoint

    paths = {route.path: route for route in app.routes if hasattr(route, "path")}
    assert "/health" in paths
    # 裸路径模板（不带 /mock 前缀）
    assert "/{project_id}/{path:path}" in paths

    mock_route = paths["/{project_id}/{path:path}"]
    # 复用了主应用的 mock_endpoint 实现
    assert mock_route.endpoint is shared_mock_endpoint
    # 方法覆盖 7 个 HTTP verb
    expected = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
    assert expected.issubset(set(mock_route.methods))


def test_mock_main_health_endpoint_returns_service_marker():
    """health 标注 service=mock-standalone，方便排查"""
    from app.mock_main import app

    health_route = next(r for r in app.routes if getattr(r, "path", None) == "/health")
    result = asyncio.run(health_route.endpoint())
    assert result == {"status": "ok", "service": "mock-standalone"}


def test_mock_main_app_title_marks_standalone():
    from app.mock_main import app

    assert "Mock Server" in app.title
