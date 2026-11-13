"""录制历史、草稿与 Web 证据持久化服务。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.minio_client import delete_file, presigned_url
from app.models.recording_record import RecordingRecord
from app.schemas.recording_record import (
    RecordingArtifactOut,
    RecordingRecordCreate,
    RecordingRecordOut,
    RecordingRecordUpdate,
)
from app.services.web_network_guard import sanitize_network_url

logger = logging.getLogger(__name__)

_ALLOWED_ARTIFACT_PREFIXES = ("traces/recordings/", "reports/recordings/")
_ALLOWED_ARTIFACT_KINDS = ("trace", "har", "report")
_VALID_SOURCES = {"workbench", "case_drawer", "resume", "assets", "mirror", "visual_editor"}
_VALID_STATUSES = {"draft", "saved", "stopped", "error"}
_MAX_STEPS = 500


class RecordingSessionConflictError(Exception):
    """Raised when a client-supplied session_id collides under a unique index constraint."""


def _is_valid_artifact_object(object_name: str) -> bool:
    normalized = object_name.strip().replace("\\", "/")
    if not normalized or ".." in normalized.split("/") or normalized.startswith("/"):
        return False
    return normalized.startswith(_ALLOWED_ARTIFACT_PREFIXES)


def _is_safe_artifact_url(url: str) -> bool:
    candidate = url.strip()
    if not candidate:
        return False
    if candidate.startswith("/"):
        return not candidate.startswith("//")
    parsed = urlsplit(candidate)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def sanitize_target_url(url: str | None) -> str | None:
    text = str(url or "").strip()
    if not text:
        return None
    if text.startswith(("http://", "https://", "ws://", "wss://")):
        cleaned = sanitize_network_url(text)
        parsed = urlsplit(cleaned)
        return parsed._replace(query="", fragment="").geturl()[:1024]
    return text.split("?", 1)[0][:1024]


def sanitize_recording_steps(raw_steps: Any) -> list[dict[str, Any]]:
    """Normalize and redact sensitive values inside recorded lowcode steps."""
    if not isinstance(raw_steps, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in raw_steps[:_MAX_STEPS]:
        if not isinstance(raw, dict):
            continue
        action = str(raw.get("action") or "").strip()[:64]
        if not action:
            continue
        name = str(raw.get("name") or action).strip()[:255]
        raw_params = raw.get("params")
        params: dict[str, Any] = dict(raw_params) if isinstance(raw_params, dict) else {}
        if params.get("sensitive") or params.get("is_password") or "敏感值" in name:
            params["value"] = ""
            if "text" in params:
                params["text"] = ""
            params.pop("is_password", None)
        if "url" in params and isinstance(params["url"], str):
            params["url"] = sanitize_network_url(params["url"])
        result.append({"action": action, "name": name, "params": params})
    return result


def sanitize_summary(raw_summary: Any) -> dict[str, Any]:
    if not isinstance(raw_summary, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in raw_summary.items():
        key_str = str(key)[:64]
        if key_str in {"current_url", "url"} and isinstance(value, str):
            cleaned[key_str] = sanitize_target_url(value)
        elif key_str in {"error", "artifact_error"} and value is not None:
            cleaned[key_str] = str(value)[:1000]
        elif isinstance(value, (str, int, float, bool)) or value is None:
            cleaned[key_str] = value[:512] if isinstance(value, str) else value
    return cleaned


def sanitize_artifacts_for_storage(raw_artifacts: Any) -> dict[str, dict[str, Any]]:
    """Strip transient signed URLs and persist safe MinIO/local object names only."""
    if not isinstance(raw_artifacts, dict):
        return {}
    stored: dict[str, dict[str, Any]] = {}
    for kind in _ALLOWED_ARTIFACT_KINDS:
        raw = raw_artifacts.get(kind)
        if not isinstance(raw, dict):
            continue
        object_name = str(raw.get("object_name") or "").strip()
        if not _is_valid_artifact_object(object_name):
            continue
        try:
            size = max(0, int(raw.get("size") or 0))
        except (TypeError, ValueError):
            size = 0
        stored[kind] = {
            "kind": kind,
            "filename": str(raw.get("filename") or object_name.rsplit("/", 1)[-1])[:255],
            "content_type": str(raw.get("content_type") or "application/octet-stream")[:128],
            "size": size,
            "object_name": object_name,
        }
    return stored


def _sign_artifacts_sync(raw_artifacts: Any) -> dict[str, RecordingArtifactOut]:
    if not isinstance(raw_artifacts, dict):
        return {}
    signed: dict[str, RecordingArtifactOut] = {}
    for kind, raw in raw_artifacts.items():
        if not isinstance(raw, dict):
            continue
        object_name = str(raw.get("object_name") or "").strip() or None
        url: str | None = None
        if object_name and _is_valid_artifact_object(object_name):
            try:
                url = presigned_url(object_name)
            except Exception as exc:
                logger.debug("录制产物预签名失败 (%s): %s", object_name, exc)
        elif isinstance(raw.get("url"), str) and _is_safe_artifact_url(raw.get("url") or ""):
            url = str(raw.get("url")).strip()
        try:
            size = max(0, int(raw.get("size") or 0))
        except (TypeError, ValueError):
            size = 0
        signed[str(kind)] = RecordingArtifactOut(
            kind=str(raw.get("kind") or kind),
            filename=str(raw.get("filename") or kind),
            content_type=str(raw.get("content_type") or "application/octet-stream"),
            size=size,
            object_name=object_name,
            url=url,
        )
    return signed


async def hydrate_artifacts(raw_artifacts: Any) -> dict[str, RecordingArtifactOut]:
    return await asyncio.to_thread(_sign_artifacts_sync, raw_artifacts)


def _count_assertions(steps: list[dict[str, Any]]) -> int:
    return sum(1 for step in steps if str(step.get("action") or "").startswith("assert_"))


def build_recording_title(
    kind: str,
    *,
    title: str | None = None,
    target_url: str | None = None,
    device_serial: str | None = None,
    device_name: str | None = None,
    steps: list[dict[str, Any]] | None = None,
    source: str = "workbench",
) -> str:
    explicit = str(title or "").strip()
    if explicit:
        return explicit[:255]
    step_count = len(steps or [])
    if kind == "web":
        clean_url = sanitize_target_url(target_url) or ""
        host_label = ""
        if clean_url:
            parsed = urlsplit(clean_url)
            if parsed.netloc:
                path = parsed.path if parsed.path and parsed.path != "/" else ""
                host_label = f"{parsed.netloc}{path}"[:80]
        prefix = "断点续录" if source == "resume" else "Web 录制"
        if host_label:
            return f"{prefix} · {host_label}"[:255]
        return f"{prefix} ({step_count} 步)"[:255]
    device_label = str(device_name or device_serial or "Android 设备").strip()[:80]
    prefix = "可视化录制" if source == "visual_editor" else "App 录制"
    return f"{prefix} · {device_label} ({step_count} 步)"[:255]


def _normalize_asset_ids(raw_ids: Any) -> list[int]:
    if not isinstance(raw_ids, list):
        return []
    result: list[int] = []
    seen: set[int] = set()
    for item in raw_ids[:500]:
        try:
            value = int(item)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in seen:
            seen.add(value)
            result.append(value)
    return result


async def serialize_recording_record(record: RecordingRecord) -> RecordingRecordOut:
    steps = record.steps if isinstance(record.steps, list) else []
    artifacts = await hydrate_artifacts(record.artifacts)
    return RecordingRecordOut(
        id=record.id,
        project_id=record.project_id,
        owner_id=record.owner_id,
        kind=record.kind,
        source=record.source,
        session_id=record.session_id,
        title=record.title,
        target_url=record.target_url,
        browser=record.browser,
        device_id=record.device_id,
        device_serial=record.device_serial,
        case_id=record.case_id,
        status=record.status,
        steps=steps,
        steps_count=len(steps),
        assertion_count=_count_assertions(steps),
        asset_ids=_normalize_asset_ids(record.asset_ids),
        artifacts=artifacts,
        summary=record.summary if isinstance(record.summary, dict) else {},
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def get_recording_record_by_session(
    db: AsyncSession,
    kind: str,
    session_id: str | None,
    *,
    project_id: int | None = None,
) -> RecordingRecord | None:
    sid = str(session_id or "").strip()
    if not sid:
        return None
    query = select(RecordingRecord).where(
        RecordingRecord.kind == kind,
        RecordingRecord.session_id == sid,
    )
    if project_id is not None:
        query = query.where(RecordingRecord.project_id == project_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


def _merge_artifacts(existing_artifacts: Any, incoming: dict[str, dict[str, Any]]) -> dict[str, Any]:
    merged = dict(existing_artifacts or {}) if isinstance(existing_artifacts, dict) else {}
    if incoming:
        merged.update(incoming)
    return merged


def _apply_create_payload_to_record(
    record: RecordingRecord,
    *,
    title: str,
    source: str,
    target_url: str | None,
    browser: str | None,
    device_id: int | None,
    device_serial: str | None,
    steps: list[dict[str, Any]],
    asset_ids: list[int],
    summary: dict[str, Any],
    case_id: int | None,
    status_value: str,
) -> None:
    record.title = title
    record.source = source
    record.target_url = target_url
    record.browser = browser
    record.device_id = device_id
    record.device_serial = device_serial
    record.steps = steps
    record.asset_ids = asset_ids
    record.summary = summary
    if case_id is not None:
        record.case_id = case_id
    if record.status != "saved" or status_value == "saved":
        record.status = status_value


async def upsert_web_recording_record(
    db: AsyncSession,
    snapshot: dict[str, Any],
    owner_id: int | None,
) -> RecordingRecord | None:
    """Persist a terminal Web recording snapshot (steps + artifacts + diagnostics)."""
    project_id = snapshot.get("project_id")
    session_id = str(snapshot.get("id") or "").strip()
    session_status = str(snapshot.get("status") or "").strip()
    if not isinstance(project_id, int) or project_id <= 0 or not session_id:
        return None
    if session_status not in {"stopped", "error"}:
        return None

    source = str(snapshot.get("source") or "workbench").strip()
    if source not in _VALID_SOURCES:
        source = "workbench"
    target_url = sanitize_target_url(snapshot.get("start_url"))
    steps = sanitize_recording_steps(snapshot.get("steps"))
    asset_ids = _normalize_asset_ids(snapshot.get("asset_ids"))
    artifacts = sanitize_artifacts_for_storage(snapshot.get("artifacts"))
    summary = sanitize_summary(
        {
            "current_url": snapshot.get("current_url"),
            "error": snapshot.get("error"),
            "artifact_error": snapshot.get("artifact_error"),
            "replayed_step_count": int(snapshot.get("replayed_step_count") or 0),
            "is_resuming": bool(snapshot.get("is_resuming")),
            "auto_assert": bool(snapshot.get("auto_assert", True)),
            "network_event_count": len(snapshot.get("network_events") or []),
            "failed_request_count": len(snapshot.get("failed_requests") or []),
            "error_response_count": len(snapshot.get("error_responses") or []),
            "console_error_count": sum(
                1
                for msg in (snapshot.get("console_messages") or [])
                if isinstance(msg, dict) and str(msg.get("type") or "").lower() == "error"
            )
            + len(snapshot.get("page_errors") or []),
        }
    )

    if session_status == "error" and not steps:
        computed_status = "error"
    elif source == "assets":
        # Visual baseline capture records shouldn't trigger case draft recovery prompts.
        computed_status = "stopped"
    elif steps:
        computed_status = "draft"
    else:
        computed_status = "stopped"

    title = build_recording_title(
        "web",
        target_url=target_url,
        steps=steps,
        source=source,
    )
    browser_value = str(snapshot.get("browser") or "")[:32] or None

    def _apply_web_update(target: RecordingRecord) -> None:
        if owner_id is not None and target.owner_id is None:
            target.owner_id = owner_id
        target.source = source
        target.title = title
        target.target_url = target_url
        target.browser = browser_value or target.browser
        target.steps = steps
        target.asset_ids = asset_ids or _normalize_asset_ids(target.asset_ids)
        if artifacts:
            target.artifacts = _merge_artifacts(target.artifacts, artifacts)
        target.summary = summary
        if target.status != "saved":
            target.status = computed_status

    existing = await get_recording_record_by_session(db, "web", session_id, project_id=project_id)
    if existing is not None:
        _apply_web_update(existing)
        await db.commit()
        await db.refresh(existing)
        return existing

    record = RecordingRecord(
        project_id=project_id,
        owner_id=owner_id,
        kind="web",
        source=source,
        session_id=session_id,
        title=title,
        target_url=target_url,
        browser=browser_value,
        status=computed_status,
        steps=steps,
        asset_ids=asset_ids,
        artifacts=artifacts,
        summary=summary,
    )
    db.add(record)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        existing = await get_recording_record_by_session(db, "web", session_id, project_id=project_id)
        if existing is None:
            raise RecordingSessionConflictError("Web 录制会话标识冲突") from exc
        _apply_web_update(existing)
        await db.commit()
        await db.refresh(existing)
        return existing
    await db.refresh(record)
    return record


async def create_or_upsert_recording_record(
    db: AsyncSession,
    payload: RecordingRecordCreate,
    owner_id: int,
) -> RecordingRecord:
    steps = sanitize_recording_steps(payload.steps)
    target_url = sanitize_target_url(payload.target_url)
    summary = sanitize_summary(payload.summary)
    asset_ids = _normalize_asset_ids(payload.asset_ids)
    device_name = str(summary.get("device_name") or "").strip() or None
    title = build_recording_title(
        payload.kind,
        title=payload.title,
        target_url=target_url,
        device_serial=payload.device_serial,
        device_name=device_name,
        steps=steps,
        source=payload.source,
    )
    session_id = str(payload.session_id or "").strip() or None

    def _apply_to(target: RecordingRecord) -> None:
        _apply_create_payload_to_record(
            target,
            title=title,
            source=payload.source,
            target_url=target_url,
            browser=payload.browser,
            device_id=payload.device_id,
            device_serial=payload.device_serial,
            steps=steps,
            asset_ids=asset_ids,
            summary=summary,
            case_id=payload.case_id,
            status_value=payload.status,
        )

    if session_id is not None:
        existing = await get_recording_record_by_session(db, payload.kind, session_id, project_id=payload.project_id)
        if existing is not None:
            _apply_to(existing)
            await db.commit()
            await db.refresh(existing)
            return existing

    record = RecordingRecord(
        project_id=payload.project_id,
        owner_id=owner_id,
        kind=payload.kind,
        source=payload.source,
        session_id=session_id,
        title=title,
        target_url=target_url,
        browser=payload.browser,
        device_id=payload.device_id,
        device_serial=payload.device_serial,
        case_id=payload.case_id,
        status=payload.status,
        steps=steps,
        asset_ids=asset_ids,
        artifacts={},
        summary=summary,
    )
    db.add(record)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if session_id is not None:
            existing = await get_recording_record_by_session(
                db, payload.kind, session_id, project_id=payload.project_id
            )
            if existing is not None:
                _apply_to(existing)
                await db.commit()
                await db.refresh(existing)
                return existing
        raise RecordingSessionConflictError("同一项目下的录制会话标识冲突") from exc
    await db.refresh(record)
    return record


async def update_recording_record(
    db: AsyncSession,
    record: RecordingRecord,
    payload: RecordingRecordUpdate,
) -> RecordingRecord:
    if payload.title is not None:
        record.title = payload.title.strip()[:255] or record.title
    if payload.status is not None and payload.status in _VALID_STATUSES:
        record.status = payload.status
    if payload.case_id is not None:
        record.case_id = payload.case_id
    if payload.device_id is not None:
        record.device_id = payload.device_id
    if payload.device_serial is not None:
        record.device_serial = payload.device_serial
    if payload.steps is not None:
        record.steps = sanitize_recording_steps(payload.steps)
    if payload.summary is not None:
        merged = dict(record.summary or {})
        merged.update(sanitize_summary(payload.summary))
        record.summary = merged
    await db.commit()
    await db.refresh(record)
    return record


async def list_recording_records(
    db: AsyncSession,
    *,
    project_id: int,
    kind: str | None = None,
    status: str | None = None,
    limit: int = 30,
) -> list[RecordingRecord]:
    query = select(RecordingRecord).where(RecordingRecord.project_id == project_id)
    if kind:
        query = query.where(RecordingRecord.kind == kind)
    if status:
        query = query.where(RecordingRecord.status == status)
    query = query.order_by(RecordingRecord.updated_at.desc(), RecordingRecord.id.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def delete_recording_record(db: AsyncSession, record: RecordingRecord) -> None:
    object_names: list[str] = []
    if isinstance(record.artifacts, dict):
        for raw in record.artifacts.values():
            if isinstance(raw, dict):
                object_name = str(raw.get("object_name") or "").strip()
                if _is_valid_artifact_object(object_name):
                    object_names.append(object_name)

    await db.delete(record)
    await db.commit()

    for object_name in object_names:
        try:
            await asyncio.to_thread(delete_file, object_name)
        except Exception as exc:
            logger.debug("清理录制产物对象失败 (%s): %s", object_name, exc)
