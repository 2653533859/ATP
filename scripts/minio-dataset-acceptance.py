#!/usr/bin/env python3
"""Run destructive, isolated ATP dataset checks against a real MinIO server.

Application credentials come from the normal ATP settings. Optional read-only
credentials come from ATP_MINIO_READONLY_USER/ATP_MINIO_READONLY_PASSWORD and
are never written to the evidence report.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from minio import Minio  # noqa: E402
from minio.commonconfig import CopySource  # noqa: E402
from minio.error import S3Error  # noqa: E402

from app.core import minio_client  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.services.dataset_storage import (  # noqa: E402
    MAX_DATASET_OBJECT_BYTES,
    DatasetStorageLimitError,
    cleanup_dataset_object_names,
    read_dataset_rows,
    reconcile_dataset_objects,
    serialize_dataset_rows,
    upload_dataset_rows,
    validate_dataset_rows_size,
)


class AcceptanceError(RuntimeError):
    pass


# MinIO/S3 在拒绝写入时返回的授权错误码；其他错误不能当作“权限生效”。
_ACCESS_DENIED_CODES = {"AccessDenied", "AllAccessDisabled", "InvalidAccessKeyId", "SignatureDoesNotMatch"}


def _rows(count: int) -> list[dict]:
    padding = "ATP-MinIO-acceptance-" * 18
    return [{"id": index, "name": f"row-{index}", "payload": padding} for index in range(count)]


def _names(client: Minio, bucket: str, prefix: str) -> set[str]:
    return {item.object_name for item in client.list_objects(bucket, prefix=prefix, recursive=True)}


def _check(checks: list[dict], name: str, condition: bool, detail: str) -> None:
    status = "PASS" if condition else "FAIL"
    checks.append({"name": name, "status": status, "detail": detail})
    print(f"[{status}] {name}: {detail}")
    if not condition:
        raise AcceptanceError(detail)


def _write_report(path: Path, checks: list[dict], *, status: str, rows: int, backup_bucket: str) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "environment": {
            "endpoint": f"{settings.MINIO_HOST}:{settings.MINIO_PORT}",
            "source_bucket": settings.MINIO_BUCKET,
            "backup_bucket": backup_bucket,
            "row_count": rows,
        },
        "checks": checks,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=25_000)
    parser.add_argument("--backup-bucket", default=f"{settings.MINIO_BUCKET}-acceptance-backup")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("--rows must be positive")

    checks: list[dict] = []
    client = minio_client.get_client()
    run_id = uuid4().hex
    project_id = int(run_id[:8], 16)
    dataset_id = 1
    prefix = f"datasets/{project_id}/{dataset_id}/"
    primary_name = f"{prefix}current-{run_id}.json"
    backup_name = f"acceptance/{run_id}/{primary_name}"
    created_names: set[str] = set()
    status = "failed"

    try:
        _check(checks, "source bucket reachable", client.bucket_exists(settings.MINIO_BUCKET), settings.MINIO_BUCKET)
        if not client.bucket_exists(args.backup_bucket):
            client.make_bucket(args.backup_bucket)

        rows = _rows(args.rows)
        payload = serialize_dataset_rows(rows)
        digest = hashlib.sha256(payload).hexdigest()
        _check(
            checks,
            "large dataset generated",
            len(payload) > 10 * 1024 * 1024,
            f"rows={len(rows)}, bytes={len(payload)}, sha256={digest}",
        )

        upload_dataset_rows(project_id=project_id, dataset_id=dataset_id, rows=rows, object_name=primary_name)
        created_names.add(primary_name)
        restored_rows = read_dataset_rows(primary_name)
        _check(
            checks,
            "ATP upload/read round trip",
            hashlib.sha256(serialize_dataset_rows(restored_rows)).hexdigest() == digest,
            f"rows={len(restored_rows)}, sha256={digest}",
        )

        orphan_name = f"{prefix}orphan-{run_id}.json"
        upload_dataset_rows(
            project_id=project_id, dataset_id=dataset_id, rows=[{"orphan": True}], object_name=orphan_name
        )
        created_names.add(orphan_name)
        dry_run = reconcile_dataset_objects(project_id, {primary_name})
        _check(
            checks,
            "orphan dry-run is non-destructive",
            dry_run["orphaned_objects"] == [orphan_name]
            and orphan_name in _names(client, settings.MINIO_BUCKET, prefix),
            f"orphan_count={dry_run['orphan_count']}, deleted_count={dry_run['deleted_count']}",
        )
        purged = reconcile_dataset_objects(project_id, {primary_name}, purge=True)
        created_names.discard(orphan_name)
        _check(
            checks,
            "explicit orphan purge",
            purged["deleted_count"] == 1 and orphan_name not in _names(client, settings.MINIO_BUCKET, prefix),
            f"deleted_count={purged['deleted_count']}",
        )

        rollback_name = f"{prefix}rollback-{run_id}.json"
        upload_dataset_rows(
            project_id=project_id, dataset_id=dataset_id, rows=[{"rollback": True}], object_name=rollback_name
        )
        errors = cleanup_dataset_object_names(project_id, dataset_id, [rollback_name])
        _check(
            checks,
            "failed transaction compensation",
            not errors and rollback_name not in _names(client, settings.MINIO_BUCKET, prefix),
            f"cleanup_errors={len(errors)}",
        )

        try:
            validate_dataset_rows_size([{"payload": "x" * (MAX_DATASET_OBJECT_BYTES + 1)}], "minio")
        except DatasetStorageLimitError:
            oversized_rejected = True
        else:
            oversized_rejected = False
        _check(checks, "50MB object limit", oversized_rejected, "oversized payload rejected before upload")

        client.copy_object(args.backup_bucket, backup_name, CopySource(settings.MINIO_BUCKET, primary_name))
        client.remove_object(settings.MINIO_BUCKET, primary_name)
        created_names.discard(primary_name)
        client.copy_object(settings.MINIO_BUCKET, primary_name, CopySource(args.backup_bucket, backup_name))
        created_names.add(primary_name)
        restored_rows = read_dataset_rows(primary_name)
        _check(
            checks,
            "backup and restore",
            hashlib.sha256(serialize_dataset_rows(restored_rows)).hexdigest() == digest,
            f"restored_rows={len(restored_rows)}, sha256={digest}",
        )

        readonly_user = os.getenv("ATP_MINIO_READONLY_USER", "").strip()
        readonly_password = os.getenv("ATP_MINIO_READONLY_PASSWORD", "")
        if readonly_user and readonly_password:
            readonly = Minio(
                f"{settings.MINIO_HOST}:{settings.MINIO_PORT}",
                access_key=readonly_user,
                secret_key=readonly_password,
                secure=False,
            )
            response = readonly.get_object(settings.MINIO_BUCKET, primary_name)
            try:
                read_ok = hashlib.sha256(response.read()).hexdigest() == digest
            finally:
                response.close()
                response.release_conn()
            forbidden_name = f"{prefix}forbidden.json"
            try:
                readonly.put_object(settings.MINIO_BUCKET, forbidden_name, io.BytesIO(b"{}"), 2)
            except S3Error as exc:
                # 只有明确的授权拒绝才算通过；网络或配置错误不能伪装成权限生效。
                write_blocked = exc.code in _ACCESS_DENIED_CODES
                write_detail = f"write rejected with {exc.code}"
                if not write_blocked:
                    created_names.add(forbidden_name)
            except Exception as exc:
                write_blocked = False
                write_detail = f"write probe failed without an authorization error: {type(exc).__name__}"
                created_names.add(forbidden_name)
            else:
                write_blocked = False
                write_detail = "write succeeded; the account is not read-only"
                client.remove_object(settings.MINIO_BUCKET, forbidden_name)
            _check(
                checks,
                "read-only policy",
                read_ok and write_blocked,
                f"read {'allowed' if read_ok else 'failed'}; {write_detail}",
            )
        else:
            checks.append(
                {
                    "name": "read-only policy",
                    "status": "SKIP",
                    "detail": "set ATP_MINIO_READONLY_USER and ATP_MINIO_READONLY_PASSWORD to require this check",
                }
            )
            print("[SKIP] read-only policy: credentials not configured")

        status = "passed_with_skips" if any(item["status"] == "SKIP" for item in checks) else "passed"
        return 0
    except Exception as exc:
        checks.append({"name": "acceptance execution", "status": "FAIL", "detail": str(exc)[:500]})
        print(f"[FAIL] acceptance execution: {exc}", file=sys.stderr)
        return 1
    finally:
        for object_name in created_names:
            try:
                client.remove_object(settings.MINIO_BUCKET, object_name)
            except Exception:
                pass
        try:
            client.remove_object(args.backup_bucket, backup_name)
        except Exception:
            pass
        _write_report(args.report, checks, status=status, rows=args.rows, backup_bucket=args.backup_bucket)


if __name__ == "__main__":
    raise SystemExit(main())
