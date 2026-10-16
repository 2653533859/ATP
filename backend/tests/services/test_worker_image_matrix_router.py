"""Unit tests for D1.3 Worker Image Matrix Router Service."""

import pytest

from app.services.worker_image_matrix_router import (
    ImageCategory,
    WorkerImageRecord,
    delete_worker_image,
    get_worker_image,
    init_default_image_matrix,
    list_worker_images,
    register_worker_image,
    reset_image_matrix_registry,
    resolve_worker_image,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_image_matrix_registry()
    init_default_image_matrix()
    yield
    reset_image_matrix_registry()


def test_default_matrix_initialization():
    images = list_worker_images()
    assert len(images) == 5

    py_img = get_worker_image("img_py312_core")
    assert py_img is not None
    assert py_img.category == ImageCategory.PYTHON
    assert "python:3.12" in py_img.tags
    assert py_img.is_default is True

    android_img = get_worker_image("img_android_api34")
    assert android_img is not None
    assert android_img.category == ImageCategory.ANDROID_SDK


def test_resolve_exact_tags_match():
    # 查找包含 python:3.12 与 playwright 的镜像
    res = resolve_worker_image(required_tags=["python:3.12", "playwright"])
    assert res.matched is True
    assert res.is_fallback is False
    assert res.selected_image.image_id == "img_py312_core"
    assert "python:3.12" in res.matched_tags
    assert "playwright" in res.matched_tags
    assert res.match_score > 0


def test_resolve_fallback_when_no_match():
    # 搜索完全不存在的奇异标签
    res = resolve_worker_image(required_tags=["cobol:1985", "quantum_computing"])
    assert res.matched is False
    assert res.is_fallback is True
    assert res.selected_image.is_default is True
    assert "安全平滑回退至默认镜像" in res.reason


def test_resolve_category_filtering():
    # 限制只在 BROWSER 类别查找
    res = resolve_worker_image(
        required_tags=["ui_test"],
        category=ImageCategory.BROWSER,
    )
    assert res.matched is True
    assert res.selected_image.image_id == "img_node20_playwright"
    assert res.selected_image.category == ImageCategory.BROWSER


def test_resource_threshold_filtering():
    # 性能压测镜像 img_perf_locust 需要 4.0 CPU
    # 如果可用 CPU 仅 2.0，则该镜像被过滤排除
    res = resolve_worker_image(
        required_tags=["locust", "performance_test"],
        available_cpu_cores=2.0,
    )
    # 由于 2.0C 无法满足 4.0C 门槛，不能命中 img_perf_locust，安全回退
    assert res.selected_image.image_id != "img_perf_locust"
    assert res.is_fallback is True


def test_register_and_delete_image():
    custom_img = WorkerImageRecord(
        image_id="img_custom_go",
        name="ATP Go 1.22 执行环境",
        image_url="registry.internal/atp/worker-golang:1.22",
        category=ImageCategory.GENERIC,
        tags=["go:1.22", "grpc", "microservice"],
        is_default=False,
    )
    register_worker_image(custom_img)

    fetched = get_worker_image("img_custom_go")
    assert fetched is not None
    assert fetched.name == "ATP Go 1.22 执行环境"

    # 删除
    deleted = delete_worker_image("img_custom_go")
    assert deleted is True
    assert get_worker_image("img_custom_go") is None
