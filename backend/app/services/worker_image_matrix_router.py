"""容器执行环境镜像版本矩阵与动态路由分发引擎 (D1.3).

支持 Python/Node/Android SDK/Browser 多版本镜像矩阵注册与标签打分路由，
根据用例运行标签需求动态解析并命中最佳 Worker 容器镜像，并支持平滑兜底回退。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ImageCategory(str, Enum):
    PYTHON = "python"
    NODEJS = "nodejs"
    ANDROID_SDK = "android_sdk"
    BROWSER = "browser"
    PERFORMANCE = "performance"
    GENERIC = "generic"


@dataclass
class WorkerImageRecord:
    image_id: str
    name: str
    image_url: str
    category: ImageCategory
    tags: list[str] = field(default_factory=list)
    is_default: bool = False
    weight: float = 1.0
    min_cpu_cores: float = 1.0
    min_memory_mb: int = 1024
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "name": self.name,
            "image_url": self.image_url,
            "category": self.category.value,
            "tags": self.tags,
            "is_default": self.is_default,
            "weight": self.weight,
            "min_cpu_cores": self.min_cpu_cores,
            "min_memory_mb": self.min_memory_mb,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ImageRouteMatchResult:
    matched: bool
    selected_image: WorkerImageRecord
    match_score: float
    matched_tags: list[str]
    unmatched_tags: list[str]
    is_fallback: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "selected_image": self.selected_image.to_dict(),
            "match_score": self.match_score,
            "matched_tags": self.matched_tags,
            "unmatched_tags": self.unmatched_tags,
            "is_fallback": self.is_fallback,
            "reason": self.reason,
        }


# 内存镜像矩阵仓库
_IMAGE_MATRIX_REGISTRY: dict[str, WorkerImageRecord] = {}


def register_worker_image(image: WorkerImageRecord) -> None:
    """注册或更新 Worker 容器镜像。"""
    # 如果标记为当前分类的默认镜像，则先重置同分类下其他镜像的 is_default
    if image.is_default:
        for existing in _IMAGE_MATRIX_REGISTRY.values():
            if existing.category == image.category and existing.image_id != image.image_id:
                existing.is_default = False

    _IMAGE_MATRIX_REGISTRY[image.image_id] = image
    logger.info(
        "Registered worker image image_id=%s category=%s url=%s", image.image_id, image.category.value, image.image_url
    )


def get_worker_image(image_id: str) -> WorkerImageRecord | None:
    """获取指定镜像记录。"""
    return _IMAGE_MATRIX_REGISTRY.get(image_id)


def list_worker_images(category: ImageCategory | None = None) -> list[WorkerImageRecord]:
    """查询镜像矩阵列表。"""
    images = list(_IMAGE_MATRIX_REGISTRY.values())
    if category:
        images = [img for img in images if img.category == category]
    return images


def delete_worker_image(image_id: str) -> bool:
    """删除指定镜像。"""
    if image_id in _IMAGE_MATRIX_REGISTRY:
        del _IMAGE_MATRIX_REGISTRY[image_id]
        logger.info("Deleted worker image image_id=%s", image_id)
        return True
    return False


def resolve_worker_image(
    required_tags: list[str],
    category: ImageCategory | None = None,
    available_cpu_cores: float | None = None,
    available_memory_mb: int | None = None,
) -> ImageRouteMatchResult:
    """核心路由算法：对用例所需标签进行加权交集打分，返回最佳命中或平滑兜底镜像。"""
    if not _IMAGE_MATRIX_REGISTRY:
        init_default_image_matrix()

    candidates = list(_IMAGE_MATRIX_REGISTRY.values())

    # 1. 过滤分类
    if category:
        candidates = [c for c in candidates if c.category == category]

    # 2. 过滤资源最低门槛
    if available_cpu_cores is not None:
        candidates = [c for c in candidates if c.min_cpu_cores <= available_cpu_cores]
    if available_memory_mb is not None:
        candidates = [c for c in candidates if c.min_memory_mb <= available_memory_mb]

    req_set = set(t.lower() for t in required_tags)
    best_image: WorkerImageRecord | None = None
    best_score: float = -1.0
    best_matched_tags: list[str] = []
    best_unmatched_tags: list[str] = []

    for img in candidates:
        img_tags_set = set(t.lower() for t in img.tags)
        matched = req_set.intersection(img_tags_set)
        unmatched = req_set.difference(img_tags_set)

        # 评分模型：匹配标签数 * 10.0 + 权重加分
        score = len(matched) * 10.0 * img.weight

        if score > best_score:
            best_score = score
            best_image = img
            best_matched_tags = list(matched)
            best_unmatched_tags = list(unmatched)

    # 3. 命中判定或回退兜底
    if best_image and best_score > 0:
        return ImageRouteMatchResult(
            matched=True,
            selected_image=best_image,
            match_score=best_score,
            matched_tags=best_matched_tags,
            unmatched_tags=best_unmatched_tags,
            is_fallback=False,
            reason=f"精准命中镜像 [{best_image.name}]，匹配标签 {len(best_matched_tags)} 个，得分 {best_score:.1f}",
        )

    # 4. 回退到默认兜底镜像
    fallback_image = next((img for img in candidates if img.is_default), None)
    if not fallback_image:
        # 全局任意默认镜像
        fallback_image = next((img for img in _IMAGE_MATRIX_REGISTRY.values() if img.is_default), None)
    if not fallback_image and candidates:
        fallback_image = candidates[0]
    if not fallback_image and _IMAGE_MATRIX_REGISTRY:
        fallback_image = next(iter(_IMAGE_MATRIX_REGISTRY.values()))

    if not fallback_image:
        raise ValueError("镜像矩阵仓库为空，无法解析任何有效 Worker 镜像")

    return ImageRouteMatchResult(
        matched=False,
        selected_image=fallback_image,
        match_score=0.0,
        matched_tags=[],
        unmatched_tags=list(req_set),
        is_fallback=True,
        reason=f"未找到完全符合需求标签 {required_tags} 的镜像，安全平滑回退至默认镜像 [{fallback_image.name}]",
    )


def init_default_image_matrix() -> None:
    """初始化企业级开箱即用多版本镜像矩阵。"""
    defaults = [
        WorkerImageRecord(
            image_id="img_py312_core",
            name="ATP Python 3.12 核心执行环境",
            image_url="registry.internal/atp/worker-python:3.12-v1",
            category=ImageCategory.PYTHON,
            tags=["python:3.12", "pytest", "playwright", "x86_64"],
            is_default=True,
            weight=1.2,
            min_cpu_cores=1.0,
            min_memory_mb=1024,
        ),
        WorkerImageRecord(
            image_id="img_py310_legacy",
            name="ATP Python 3.10 兼容执行环境",
            image_url="registry.internal/atp/worker-python:3.10-legacy",
            category=ImageCategory.PYTHON,
            tags=["python:3.10", "pytest", "legacy"],
            is_default=False,
            weight=1.0,
            min_cpu_cores=1.0,
            min_memory_mb=1024,
        ),
        WorkerImageRecord(
            image_id="img_node20_playwright",
            name="ATP Node.js 20 Web UI 自动化执行环境",
            image_url="registry.internal/atp/worker-node:20-playwright",
            category=ImageCategory.BROWSER,
            tags=["node:20", "playwright:chromium", "playwright:firefox", "playwright:webkit", "ui_test"],
            is_default=True,
            weight=1.5,
            min_cpu_cores=2.0,
            min_memory_mb=2048,
        ),
        WorkerImageRecord(
            image_id="img_android_api34",
            name="ATP Android SDK 34 移动端执行环境",
            image_url="registry.internal/atp/worker-android:api34-uiautomator2",
            category=ImageCategory.ANDROID_SDK,
            tags=["android:34", "uiautomator2", "adb", "mobile_test"],
            is_default=True,
            weight=1.5,
            min_cpu_cores=2.0,
            min_memory_mb=4096,
        ),
        WorkerImageRecord(
            image_id="img_perf_locust",
            name="ATP 性能高并发压测执行环境",
            image_url="registry.internal/atp/worker-perf:locust-distributed",
            category=ImageCategory.PERFORMANCE,
            tags=["locust", "performance_test", "high_concurrency"],
            is_default=True,
            weight=1.8,
            min_cpu_cores=4.0,
            min_memory_mb=8192,
        ),
    ]

    for d in defaults:
        _IMAGE_MATRIX_REGISTRY[d.image_id] = d
    logger.info("Initialized default image matrix with %s images", len(defaults))


def reset_image_matrix_registry() -> None:
    """供单元测试重置状态使用。"""
    _IMAGE_MATRIX_REGISTRY.clear()
