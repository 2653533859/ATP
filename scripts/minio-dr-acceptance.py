#!/usr/bin/env python3
"""Verify a cross-endpoint MinIO application-object backup and restore drill.

The command creates one uniquely scoped probe object on the source endpoint,
copies it through the target endpoint, restores it to a second source object,
and verifies SHA-256 at every boundary.  All probe objects are removed in a
finally block.  Access keys and secret keys are read only from environment
variables and are never written to the JSON report.

Required environment variables::

    ATP_MINIO_DR_SOURCE_ENDPOINT=primary.example.test:9000
    ATP_MINIO_DR_SOURCE_ACCESS_KEY=...
    ATP_MINIO_DR_SOURCE_SECRET_KEY=...
    ATP_MINIO_DR_SOURCE_BUCKET=atp
    ATP_MINIO_DR_TARGET_ENDPOINT=backup.example.test:9000
    ATP_MINIO_DR_TARGET_ACCESS_KEY=...
    ATP_MINIO_DR_TARGET_SECRET_KEY=...
    ATP_MINIO_DR_TARGET_BUCKET=atp-dr

Set ``ATP_MINIO_DR_SOURCE_SECURE`` or ``ATP_MINIO_DR_TARGET_SECURE`` to a
truthy value when the endpoint uses HTTPS.  The target endpoint must use a
different host from the source; loopback aliases and endpoints resolving to the
same IP are rejected so a same-host bucket copy cannot be claimed as recovery.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import ipaddress
import io
import json
import os
from pathlib import Path
import re
import socket
from typing import Any, Iterable
from uuid import uuid4
from urllib.parse import urlsplit

from minio import Minio
from minio.error import S3Error


class AcceptanceError(RuntimeError):
    """A required recovery condition could not be proven."""


@dataclass(frozen=True)
class EndpointConfig:
    name: str
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_endpoint(value: str) -> str:
    """Validate a Minio SDK endpoint without accepting credentials or paths."""
    endpoint = str(value or "").strip()
    if not endpoint:
        raise AcceptanceError("MinIO endpoint 不能为空")
    parsed = urlsplit(f"//{endpoint}")
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise AcceptanceError("MinIO endpoint 只能是 host:port，不能包含凭据、路径或查询参数")
    try:
        port = parsed.port
    except ValueError as exc:
        raise AcceptanceError("MinIO endpoint 端口无效") from exc
    if not parsed.hostname or port is None or not 1 <= port <= 65535:
        raise AcceptanceError("MinIO endpoint 必须是 host:port，端口范围为 1-65535")
    return endpoint


def endpoint_host(value: str) -> str:
    return (urlsplit(f"//{value}").hostname or "").casefold().rstrip(".")


def endpoint_addresses(value: str) -> set[str]:
    """Resolve an endpoint host to stable IP identities when possible.

    Unresolvable names return an empty set so an offline contract check does not
    turn DNS availability into a false failure; the live MinIO connection still
    has to succeed before the drill can pass.
    """

    host = endpoint_host(value)
    if host == "localhost":
        return {"127.0.0.1", "::1"}
    try:
        return {ipaddress.ip_address(host).compressed}
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return set()
    return {ipaddress.ip_address(item[4][0]).compressed for item in infos if len(item) > 4 and item[4] and item[4][0]}


def endpoints_share_host(source: str, target: str) -> bool:
    """Return whether source and target are textually or network-identically co-located."""

    source_host = endpoint_host(source)
    target_host = endpoint_host(target)
    if source_host == target_host:
        return True
    source_addresses = endpoint_addresses(source)
    target_addresses = endpoint_addresses(target)
    return bool(source_addresses and target_addresses and source_addresses.intersection(target_addresses))


def _required_env(prefix: str, field: str) -> str:
    value = os.environ.get(f"ATP_MINIO_DR_{prefix}_{field}", "")
    if not value.strip():
        raise AcceptanceError(f"缺少环境变量 ATP_MINIO_DR_{prefix}_{field}")
    return value


def load_endpoint_config(prefix: str) -> EndpointConfig:
    endpoint = parse_endpoint(_required_env(prefix, "ENDPOINT"))
    access_key = _required_env(prefix, "ACCESS_KEY")
    secret_key = _required_env(prefix, "SECRET_KEY")
    bucket = _required_env(prefix, "BUCKET").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        raise AcceptanceError(f"MinIO {prefix.lower()} bucket 名称无效")
    return EndpointConfig(
        name=prefix.lower(),
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        bucket=bucket,
        secure=_truthy(os.environ.get(f"ATP_MINIO_DR_{prefix}_SECURE", "")),
    )


def build_client(config: EndpointConfig) -> Minio:
    return Minio(config.endpoint, config.access_key, config.secret_key, secure=config.secure)


def parse_lifecycle_requirement(value: str) -> tuple[str, int]:
    """Parse ``relative-prefix=days`` used by the optional lifecycle gate."""
    raw_prefix, separator, raw_days = str(value or "").partition("=")
    prefix = raw_prefix.strip()
    if not separator or not prefix or prefix.startswith("/"):
        raise AcceptanceError("生命周期要求必须是 relative-prefix=days")
    try:
        days = int(raw_days)
    except ValueError as exc:
        raise AcceptanceError("生命周期保留天数必须是整数") from exc
    if not 1 <= days <= 3650:
        raise AcceptanceError("生命周期保留天数必须在 1 到 3650 之间")
    return prefix, days


def _rule_summary(config: Any) -> list[dict[str, Any]]:
    rules = list(getattr(config, "rules", []) or []) if config else []
    result: list[dict[str, Any]] = []
    for rule in rules:
        rule_filter = getattr(rule, "rule_filter", None)
        expiration = getattr(rule, "expiration", None)
        result.append(
            {
                "id": str(getattr(rule, "rule_id", "") or ""),
                "status": str(getattr(rule, "status", "") or ""),
                "prefix": str(getattr(rule_filter, "prefix", "") or ""),
                "expiration_days": getattr(expiration, "days", None),
            }
        )
    return result


def _read_object(client: Any, bucket: str, object_name: str) -> bytes:
    response = client.get_object(bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def _put_object(client: Any, bucket: str, object_name: str, payload: bytes) -> None:
    client.put_object(
        bucket,
        object_name,
        io.BytesIO(payload),
        len(payload),
        content_type="application/json",
    )


def _remaining(client: Any, bucket: str, prefix: str) -> list[str]:
    return sorted(
        str(getattr(item, "object_name", ""))
        for item in client.list_objects(bucket, prefix=prefix, recursive=True)
        if getattr(item, "object_name", None)
    )


def _check(checks: list[dict[str, str]], name: str, condition: bool, detail: str) -> None:
    status = "PASS" if condition else "FAIL"
    checks.append({"name": name, "status": status, "detail": detail})
    print(f"[{status}] {name}: {detail}")
    if not condition:
        raise AcceptanceError(detail)


def _safe_error(value: Any, configs: Iterable[EndpointConfig | None]) -> str:
    detail = str(value).replace("\r", " ").replace("\n", " ").strip()
    for config in configs:
        if config is None:
            continue
        for secret in (config.access_key, config.secret_key):
            if secret:
                detail = detail.replace(secret, "<redacted>")
    return detail[:500] or "unknown error"


def _write_report(
    path: Path,
    *,
    args: argparse.Namespace,
    run_id: str,
    source: EndpointConfig | None,
    target: EndpointConfig | None,
    checks: list[dict[str, str]],
) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "status": "failed" if any(item["status"] == "FAIL" for item in checks) else "passed",
        "inputs": {
            "source_endpoint": source.endpoint if source else None,
            "source_bucket": source.bucket if source else None,
            "target_endpoint": target.endpoint if target else None,
            "target_bucket": target.bucket if target else None,
            "required_lifecycle_rules": args.require_lifecycle_rule,
        },
        "checks": checks,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", type=Path, required=True, help="输出脱敏 JSON 证据路径")
    parser.add_argument("--require-lifecycle-rule", action="append", default=[], metavar="PREFIX=DAYS")
    return parser


def _lifecycle_requirement_satisfied(rules: Iterable[dict[str, Any]], prefix: str, days: int) -> bool:
    return any(
        item.get("status") == "Enabled" and item.get("prefix") == prefix and item.get("expiration_days") == days
        for item in rules
    )


def _get_lifecycle(client: Any, bucket: str) -> Any:
    try:
        return client.get_bucket_lifecycle(bucket)
    except S3Error as exc:
        if exc.code in {"NoSuchLifecycleConfiguration", "NoSuchBucketLifecycleConfiguration"}:
            return None
        raise


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checks: list[dict[str, str]] = []
    run_id = uuid4().hex
    source_names: list[str] = []
    target_names: list[str] = []
    source: EndpointConfig | None = None
    target: EndpointConfig | None = None
    source_client: Any = None
    target_client: Any = None
    exit_code = 1
    prefix = f"atp-dr-acceptance/{run_id}/"
    try:
        source = load_endpoint_config("SOURCE")
        target = load_endpoint_config("TARGET")
        _check(
            checks,
            "endpoint-independence",
            not endpoints_share_host(source.endpoint, target.endpoint),
            "源端和目标端点必须位于不同主机，不能把同一主机的 bucket copy 写成跨主机恢复",
        )
        required_rules = [parse_lifecycle_requirement(item) for item in args.require_lifecycle_rule]
        source_client = build_client(source)
        target_client = build_client(target)
        _check(checks, "source-bucket", source_client.bucket_exists(source.bucket), source.bucket)
        _check(checks, "target-bucket", target_client.bucket_exists(target.bucket), target.bucket)

        source_lifecycle = _rule_summary(_get_lifecycle(source_client, source.bucket))
        target_lifecycle = _rule_summary(_get_lifecycle(target_client, target.bucket))
        _check(checks, "source-lifecycle-audit", True, f"rules={len(source_lifecycle)}")
        _check(checks, "target-lifecycle-audit", True, f"rules={len(target_lifecycle)}")
        for lifecycle_prefix, lifecycle_days in required_rules:
            _check(
                checks,
                f"source-lifecycle-{lifecycle_prefix}",
                _lifecycle_requirement_satisfied(source_lifecycle, lifecycle_prefix, lifecycle_days),
                f"source requires {lifecycle_prefix}={lifecycle_days}",
            )
            _check(
                checks,
                f"target-lifecycle-{lifecycle_prefix}",
                _lifecycle_requirement_satisfied(target_lifecycle, lifecycle_prefix, lifecycle_days),
                f"target requires {lifecycle_prefix}={lifecycle_days}",
            )

        source_probe = f"{prefix}source/probe.json"
        target_copy = f"{prefix}target/probe.json"
        source_restore = f"{prefix}restored/probe.json"
        payload = json.dumps(
            {"schema": "atp-minio-dr-v1", "run_id": run_id, "marker": "cross-endpoint-recovery"},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()

        _put_object(source_client, source.bucket, source_probe, payload)
        source_names.append(source_probe)
        source_read = _read_object(source_client, source.bucket, source_probe)
        _check(checks, "source-round-trip", hashlib.sha256(source_read).hexdigest() == digest, f"sha256={digest}")

        _put_object(target_client, target.bucket, target_copy, source_read)
        target_names.append(target_copy)
        target_read = _read_object(target_client, target.bucket, target_copy)
        _check(checks, "cross-endpoint-copy", hashlib.sha256(target_read).hexdigest() == digest, f"sha256={digest}")

        _put_object(source_client, source.bucket, source_restore, target_read)
        source_names.append(source_restore)
        restored = _read_object(source_client, source.bucket, source_restore)
        _check(checks, "cross-endpoint-restore", hashlib.sha256(restored).hexdigest() == digest, f"sha256={digest}")
        exit_code = 0
    except Exception as exc:
        detail = _safe_error(exc, (source, target))
        checks.append({"name": "acceptance-execution", "status": "FAIL", "detail": detail})
        print(f"[FAIL] acceptance-execution: {detail}")
        exit_code = 1
    finally:
        cleanup_errors: list[str] = []
        if source_client is not None and source is not None:
            for object_name in source_names:
                try:
                    source_client.remove_object(source.bucket, object_name)
                except Exception as exc:  # pragma: no cover - exercised by live failure handling
                    cleanup_errors.append(f"source:{object_name}:{type(exc).__name__}")
            try:
                leftovers = _remaining(source_client, source.bucket, prefix)
                if leftovers:
                    cleanup_errors.append(f"source-leftovers:{len(leftovers)}")
            except Exception as exc:  # pragma: no cover - exercised by live failure handling
                cleanup_errors.append(f"source-list:{type(exc).__name__}")
        if target_client is not None and target is not None:
            for object_name in target_names:
                try:
                    target_client.remove_object(target.bucket, object_name)
                except Exception as exc:  # pragma: no cover - exercised by live failure handling
                    cleanup_errors.append(f"target:{object_name}:{type(exc).__name__}")
            try:
                leftovers = _remaining(target_client, target.bucket, prefix)
                if leftovers:
                    cleanup_errors.append(f"target-leftovers:{len(leftovers)}")
            except Exception as exc:  # pragma: no cover - exercised by live failure handling
                cleanup_errors.append(f"target-list:{type(exc).__name__}")
        if cleanup_errors:
            checks.append({"name": "cleanup", "status": "FAIL", "detail": "; ".join(cleanup_errors)[:500]})
            print(f"[FAIL] cleanup: {'; '.join(cleanup_errors)}")
            exit_code = 1
        else:
            checks.append({"name": "cleanup", "status": "PASS", "detail": "temporary source/target objects removed"})
            print("[PASS] cleanup: temporary source/target objects removed")
        try:
            _write_report(
                args.report,
                args=args,
                run_id=run_id,
                source=source,
                target=target,
                checks=checks,
            )
        except OSError as exc:
            print(f"[FAIL] evidence-report: {exc}")
            if not any(item["name"] == "evidence-report" for item in checks):
                checks.append({"name": "evidence-report", "status": "FAIL", "detail": str(exc)[:500]})
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
