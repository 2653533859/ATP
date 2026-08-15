"""Reconcile ATP-managed MinIO lifecycle rules without deleting foreign rules.

The command is intentionally opt-in. It is used by the Helm hook and the
optional Docker Compose profile, never by normal API startup. The reconciler
keeps lifecycle rules owned by other systems and replaces only rules whose IDs
are in the ``atp-managed-`` namespace.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from minio.commonconfig import Filter
from minio.lifecycleconfig import (
    AbortIncompleteMultipartUpload,
    Expiration,
    LifecycleConfig,
    Rule,
)

from app.core.config import settings
from app.core.minio_client import ensure_bucket, get_client

logger = logging.getLogger(__name__)

_MANAGED_PREFIX = "atp-managed-"
_ABORT_RULE_ID = f"{_MANAGED_PREFIX}abort-incomplete-multipart"


@dataclass(frozen=True)
class ExpirationRuleSpec:
    rule_id: str
    prefix: str
    days: int


def parse_expiration_rules(payload: str) -> list[ExpirationRuleSpec]:
    """Parse and validate the JSON list supplied by deployment config."""

    try:
        raw_rules = json.loads(payload or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("MINIO_LIFECYCLE_EXPIRATION_RULES_JSON must be valid JSON") from exc
    if not isinstance(raw_rules, list):
        raise ValueError("MINIO_LIFECYCLE_EXPIRATION_RULES_JSON must be a JSON array")

    parsed: list[ExpirationRuleSpec] = []
    seen_ids: set[str] = set()
    for raw in raw_rules:
        if not isinstance(raw, dict):
            raise ValueError("Each MinIO lifecycle expiration rule must be an object")
        rule_id = str(raw.get("id", "")).strip()
        prefix = str(raw.get("prefix", ""))
        days = raw.get("days")
        if not rule_id or not prefix or prefix.startswith("/"):
            raise ValueError("MinIO lifecycle rules require a relative, non-empty prefix and id")
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 3650:
            raise ValueError("MinIO lifecycle rule days must be an integer between 1 and 3650")
        if rule_id in seen_ids:
            raise ValueError(f"Duplicate MinIO lifecycle rule id: {rule_id}")
        seen_ids.add(rule_id)
        parsed.append(ExpirationRuleSpec(rule_id=rule_id, prefix=prefix, days=days))
    return parsed


def _managed_expiration_id(rule_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", rule_id).strip("-")
    if not slug:
        raise ValueError("MinIO lifecycle rule id must contain a supported character")
    return f"{_MANAGED_PREFIX}expiration-{slug}"[:255]


def build_managed_rules(abort_days: int, expiration_rules: list[ExpirationRuleSpec]) -> list[Rule]:
    if not 1 <= abort_days <= 3650:
        raise ValueError("MinIO incomplete multipart retention must be between 1 and 3650 days")
    rules = [
        Rule(
            "Enabled",
            abort_incomplete_multipart_upload=AbortIncompleteMultipartUpload(days_after_initiation=abort_days),
            rule_filter=Filter(prefix=""),
            rule_id=_ABORT_RULE_ID,
        )
    ]
    managed_ids = {_ABORT_RULE_ID}
    for spec in expiration_rules:
        managed_id = _managed_expiration_id(spec.rule_id)
        if managed_id in managed_ids:
            raise ValueError(f"MinIO lifecycle rule id collides after normalization: {spec.rule_id}")
        managed_ids.add(managed_id)
        rules.append(
            Rule(
                "Enabled",
                expiration=Expiration(days=spec.days),
                rule_filter=Filter(prefix=spec.prefix),
                rule_id=managed_id,
            )
        )
    return rules


def merge_lifecycle_config(
    existing: LifecycleConfig | None,
    managed_rules: list[Rule],
) -> LifecycleConfig:
    """Keep foreign rules and replace the rules owned by this command."""

    existing_rules = list(existing.rules) if existing else []
    preserved = [rule for rule in existing_rules if not (rule.rule_id or "").startswith(_MANAGED_PREFIX)]
    return LifecycleConfig(preserved + managed_rules)


def reconcile_lifecycle(
    client: Any,
    bucket: str,
    *,
    abort_days: int,
    expiration_rules: list[ExpirationRuleSpec],
) -> dict[str, int]:
    managed_rules = build_managed_rules(abort_days, expiration_rules)
    existing = client.get_bucket_lifecycle(bucket)
    existing_count = len(existing.rules) if existing else 0
    config = merge_lifecycle_config(existing, managed_rules)
    client.set_bucket_lifecycle(bucket, config)
    return {
        "preserved_rules": existing_count
        - sum(1 for rule in (existing.rules if existing else []) if (rule.rule_id or "").startswith(_MANAGED_PREFIX)),
        "managed_rules": len(managed_rules),
    }


def main() -> None:
    if os.getenv("MINIO_LIFECYCLE_APPLY", "").strip().lower() not in {"1", "true", "yes"}:
        raise SystemExit("Set MINIO_LIFECYCLE_APPLY=true to reconcile MinIO lifecycle rules")
    ensure_bucket()
    result = reconcile_lifecycle(
        get_client(),
        settings.MINIO_BUCKET,
        abort_days=settings.MINIO_LIFECYCLE_ABORT_INCOMPLETE_DAYS,
        expiration_rules=parse_expiration_rules(settings.MINIO_LIFECYCLE_EXPIRATION_RULES_JSON),
    )
    logger.info("MinIO lifecycle reconciled bucket=%s result=%s", settings.MINIO_BUCKET, result)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    main()
