"""共享的 fake 依赖与模块替身，避免每个 api 测试文件单独注入造成冲突。"""
import sys
import types


def fake_require_admin():
    return None


def fake_require_engineer():
    return None


_minio_stub = types.SimpleNamespace(
    list_objects=lambda prefix: [],
    delete_file=lambda object_name: None,
    ensure_bucket=lambda: None,
    read_bytes=lambda *_a, **_kw: b"",
    upload_bytes=lambda *_a, **_kw: None,
)

if "app.core.minio_client" not in sys.modules:
    sys.modules["app.core.minio_client"] = _minio_stub
else:
    # 已 stub 但可能缺字段时，补齐共用字段
    _existing = sys.modules["app.core.minio_client"]
    for _name in ("list_objects", "delete_file", "ensure_bucket", "read_bytes", "upload_bytes"):
        if not hasattr(_existing, _name):
            setattr(_existing, _name, getattr(_minio_stub, _name))

# 本地无 redis / celery 时的兜底 stub，setdefault 不影响 CI 真依赖
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
