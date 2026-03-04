"""
脚本管理 API

POST /cases/{case_id}/script   上传脚本文件（multipart/form-data）
GET  /cases/{case_id}/script   获取脚本内容（文本，供 Monaco 预览）
DELETE /cases/{case_id}/script 删除脚本
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.minio_client import upload_bytes, read_bytes, delete_file, presigned_url
from app.models.case import TestCase, CaseType
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(tags=["脚本管理"])

_MAX_SCRIPT_SIZE = 1 * 1024 * 1024  # 1 MB


def _script_object_name(case_id: int) -> str:
    return f"scripts/cases/{case_id}/script.py"


@router.post("/cases/{case_id}/script")
async def upload_script(
    case_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    if case.case_type not in (CaseType.web, CaseType.android):
        raise HTTPException(status_code=400, detail="仅脚本类用例支持上传脚本")

    content = await file.read()
    if len(content) > _MAX_SCRIPT_SIZE:
        raise HTTPException(status_code=413, detail="脚本文件超过 1MB 限制")

    object_name = _script_object_name(case_id)
    upload_bytes(object_name, content, content_type="text/x-python")

    # 将 script_path 写入 case.config
    config = dict(case.config or {})
    config["script_path"] = object_name
    case.config = config
    await db.commit()

    return {"script_path": object_name, "size": len(content)}


@router.get("/cases/{case_id}/script")
async def get_script(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    script_path = (case.config or {}).get("script_path")
    if not script_path:
        return {"content": "", "exists": False}

    try:
        content = read_bytes(script_path).decode("utf-8", errors="replace")
        return {"content": content, "exists": True, "script_path": script_path}
    except Exception:
        return {"content": "", "exists": False}


@router.delete("/cases/{case_id}/script", status_code=204)
async def delete_script(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    case = await db.get(TestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    script_path = (case.config or {}).get("script_path")
    if script_path:
        try:
            delete_file(script_path)
        except Exception:
            pass
        config = dict(case.config)
        config.pop("script_path", None)
        case.config = config
        await db.commit()
