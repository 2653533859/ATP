"""容器执行环境镜像版本矩阵与动态路由 API (D1.3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_engineer
from app.models.user import User
from app.services.worker_image_matrix_router import (
    ImageCategory,
    WorkerImageRecord,
    delete_worker_image,
    get_worker_image,
    list_worker_images,
    register_worker_image,
    resolve_worker_image,
)

router = APIRouter(prefix="/cloud-native/images", tags=["容器镜像矩阵与标签路由"])


class RegisterWorkerImageIn(BaseModel):
    image_id: str = Field(min_length=2, max_length=64, description="镜像唯一标识 (如 img_py312_core)")
    name: str = Field(min_length=1, max_length=128, description="镜像描述名称")
    image_url: str = Field(min_length=3, max_length=256, description="镜像完整 Registry 路径")
    category: str = Field(
        default="generic", description="镜像所属分类 (python | nodejs | android_sdk | browser | performance | generic)"
    )
    tags: list[str] = Field(default_factory=list, description="镜像包含的标签集合")
    is_default: bool = Field(default=False, description="是否作为该分类下的默认兜底镜像")
    weight: float = Field(default=1.0, ge=0.1, le=10.0, description="权重乘数")
    min_cpu_cores: float = Field(default=1.0, ge=0.1, description="运行所需最低 CPU 核数")
    min_memory_mb: int = Field(default=1024, ge=128, description="运行所需最低内存 (MB)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="业务元数据")


class ResolveWorkerImageIn(BaseModel):
    required_tags: list[str] = Field(default_factory=list, description="用例执行所需的环境标签列表")
    category: str | None = Field(default=None, description="期望的镜像类别")
    available_cpu_cores: float | None = Field(default=None, description="当前分配的 CPU 资源")
    available_memory_mb: int | None = Field(default=None, description="当前分配的内存 (MB)")


@router.post("/register")
async def register_worker_image_endpoint(
    body: RegisterWorkerImageIn,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """向矩阵仓库注册或更新 Worker 执行环境镜像 (需工程师权限)。"""
    _ = _user
    try:
        cat_enum = ImageCategory(body.category.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的镜像分类: {body.category}")

    record = WorkerImageRecord(
        image_id=body.image_id,
        name=body.name,
        image_url=body.image_url,
        category=cat_enum,
        tags=body.tags,
        is_default=body.is_default,
        weight=body.weight,
        min_cpu_cores=body.min_cpu_cores,
        min_memory_mb=body.min_memory_mb,
        metadata=body.metadata,
    )
    register_worker_image(record)
    return {"message": "镜像注册成功", "image": record.to_dict()}


@router.get("")
async def list_worker_images_endpoint(
    category_str: str | None = Query(default=None, alias="category", description="按分类过滤"),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询镜像矩阵仓库中的全部 Worker 镜像列表。"""
    _ = _user
    cat_enum = None
    if category_str:
        try:
            cat_enum = ImageCategory(category_str.lower())
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效的镜像分类: {category_str}")

    images = list_worker_images(category=cat_enum)
    return {"total": len(images), "images": [img.to_dict() for img in images]}


@router.get("/{image_id}")
async def get_worker_image_endpoint(
    image_id: str,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取指定镜像的详细信息与标签矩阵。"""
    _ = _user
    img = get_worker_image(image_id)
    if not img:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"镜像不存在: {image_id}")
    return img.to_dict()


@router.delete("/{image_id}")
async def delete_worker_image_endpoint(
    image_id: str,
    _user: User = Depends(require_engineer),
) -> dict[str, Any]:
    """从镜像矩阵中移除指定的 Worker 镜像。"""
    _ = _user
    success = delete_worker_image(image_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"镜像不存在: {image_id}")
    return {"message": f"镜像 {image_id} 已删除"}


@router.post("/resolve")
async def resolve_worker_image_endpoint(
    body: ResolveWorkerImageIn,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """根据测试用例运行标签动态推演匹配最佳容器镜像。"""
    _ = _user
    cat_enum = None
    if body.category:
        try:
            cat_enum = ImageCategory(body.category.lower())
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效的镜像分类: {body.category}")

    try:
        match_result = resolve_worker_image(
            required_tags=body.required_tags,
            category=cat_enum,
            available_cpu_cores=body.available_cpu_cores,
            available_memory_mb=body.available_memory_mb,
        )
        return match_result.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
