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
)

if "app.core.minio_client" not in sys.modules:
    sys.modules["app.core.minio_client"] = _minio_stub
