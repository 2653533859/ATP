from urllib.parse import unquote, urlparse


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
