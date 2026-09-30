"""Signed reads for files stored by the isolated local profile."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.local_object_store import content_type_for, object_path, verify_signature

router = APIRouter(prefix="/local-files", tags=["本地文件"])


@router.get("/{object_name:path}")
def get_local_file(object_name: str, expires: int, signature: str) -> FileResponse:
    if not settings.ATP_LOCAL_MODE or not verify_signature(object_name, expires, signature):
        raise HTTPException(status_code=403, detail="invalid or expired file URL")
    try:
        path = object_path(object_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid object name") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    media_type = content_type_for(object_name)
    disposition = "inline" if media_type in {"image/png", "image/jpeg", "image/webp"} else "attachment"
    return FileResponse(path, media_type=media_type, filename=path.name, content_disposition_type=disposition)
