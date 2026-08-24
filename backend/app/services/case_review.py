"""Small serialization helpers shared by review workflow and history APIs."""

import json
from typing import Any


def build_review_audit_detail(*, action: str, status: str, comment: str | None, source: str = "case") -> str:
    return json.dumps(
        {
            "action": action,
            "status": status,
            "comment": comment,
            "source": source,
        },
        ensure_ascii=False,
    )


def parse_review_audit_detail(detail: str | None) -> dict[str, Any]:
    if not detail:
        return {}
    try:
        value = json.loads(detail)
    except (TypeError, ValueError):
        return {"comment": detail}
    return value if isinstance(value, dict) else {"comment": str(value)}
