from urllib.parse import unquote, urlparse


RUN_ARTIFACT_PREFIXES = (
    "android-artifacts/runs/",
    "ios-artifacts/runs/",
    "traces/runs/",
    "videos/runs/",
    "visual-diffs/runs/",
    "web-files/runs/",
)


def extract_object_name(value: str | None) -> str | None:
    """从对象名或 MinIO presigned URL 中提取 object name。"""
    if not value:
        return None
    if value.startswith("http"):
        path = urlparse(value).path
        parts = path.split("/", 2)
        if len(parts) >= 3 and parts[2]:
            return unquote(parts[2]).lstrip("/")
        return None
    return value.lstrip("/") or None


def collect_run_artifact_object_names(value: object, *, run_ids: set[int] | None = None) -> list[str]:
    """Collect run-scoped MinIO objects from a nested execution summary."""
    objects: list[str] = []
    seen: set[str] = set()

    def visit(candidate: object) -> None:
        if isinstance(candidate, dict):
            for nested in candidate.values():
                visit(nested)
            return
        if isinstance(candidate, (list, tuple)):
            for nested in candidate:
                visit(nested)
            return
        if not isinstance(candidate, str):
            return
        object_name = extract_object_name(candidate)
        if not object_name or not object_name.startswith(RUN_ARTIFACT_PREFIXES):
            return
        matches_run = run_ids is None or any(
            object_name.startswith(f"{prefix}{run_id}/") for prefix in RUN_ARTIFACT_PREFIXES for run_id in run_ids
        )
        if matches_run and object_name not in seen:
            seen.add(object_name)
            objects.append(object_name)

    visit(value)
    return objects
