"""
缺陷创建服务

支持两种平台：
- Jira:  REST API v2，Basic Auth (email + API Token)
- 禅道:  REST API，Session Token 认证
"""
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def create_bug(
    tracker_type: str,
    config: dict,
    title: str,
    description: str,
    field_mapping: dict | None = None,
    override_product_id: str | None = None,
) -> dict:
    """
    创建缺陷，返回 {"bug_id": "...", "bug_url": "...", "title": "..."}.

    Raises RuntimeError on failure.
    """
    if tracker_type == "jira":
        return await _create_jira_issue(config, title, description, field_mapping or {})
    elif tracker_type == "zentao":
        return await _create_zentao_bug(
            config, title, description, field_mapping or {},
            override_product_id=override_product_id,
        )
    elif tracker_type == "github":
        return await _create_github_issue(config, title, description, field_mapping or {})
    elif tracker_type == "gitlab":
        return await _create_gitlab_issue(config, title, description, field_mapping or {})
    else:
        raise ValueError(f"不支持的缺陷跟踪平台: {tracker_type}")


async def test_connection(tracker_type: str, config: dict) -> dict:
    if tracker_type == "jira":
        return await _test_jira_connection(config)
    if tracker_type == "zentao":
        return await _test_zentao_connection(config)
    if tracker_type == "github":
        return await _test_github_connection(config)
    if tracker_type == "gitlab":
        return await _test_gitlab_connection(config)
    raise ValueError(f"不支持的缺陷跟踪平台: {tracker_type}")


async def find_duplicate_bug(tracker_type: str, config: dict, title: str) -> dict | None:
    if tracker_type == "jira":
        return await _find_jira_duplicate(config, title)
    if tracker_type == "zentao":
        return await _find_zentao_duplicate(config, title)
    if tracker_type == "github":
        return await _find_github_duplicate(config, title)
    if tracker_type == "gitlab":
        return await _find_gitlab_duplicate(config, title)
    return None


async def upload_attachment(tracker_type: str, config: dict, bug_id: str, filename: str, content: bytes) -> bool:
    if not content:
        return False
    if tracker_type == "jira":
        return await _upload_jira_attachment(config, bug_id, filename, content)
    if tracker_type == "zentao":
        return await _upload_zentao_attachment(config, bug_id, filename, content)
    return False


async def get_bug_status(tracker_type: str, config: dict, bug_id: str) -> dict:
    if tracker_type == "jira":
        return await _get_jira_bug_status(config, bug_id)
    if tracker_type == "zentao":
        return await _get_zentao_bug_status(config, bug_id)
    if tracker_type == "github":
        return await _get_github_issue_status(config, bug_id)
    if tracker_type == "gitlab":
        return await _get_gitlab_issue_status(config, bug_id)
    raise ValueError(f"不支持的缺陷跟踪平台: {tracker_type}")


# ── Jira ─────────────────────────────────────────────────

def _escape_jira_jql_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "\\\"").replace("\n", " ").replace("\r", " ")


def _apply_jira_field_mapping(payload_fields: dict, field_mapping: dict) -> None:
    if not field_mapping:
        return
    if field_mapping.get("priority"):
        payload_fields["priority"] = {"name": field_mapping["priority"]}
    if field_mapping.get("labels"):
        payload_fields["labels"] = field_mapping["labels"]
    if field_mapping.get("components"):
        payload_fields["components"] = [{"name": name} for name in field_mapping["components"]]
    for key, value in (field_mapping.get("custom_fields") or {}).items():
        payload_fields[key] = value


async def _create_jira_issue(config: dict, title: str, description: str, field_mapping: dict) -> dict:
    base_url = config["base_url"].rstrip("/")
    email = config["email"]
    api_token = config["api_token"]
    project_key = config["project_key"]
    issue_type = config.get("issue_type", "Bug")

    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": title,
            "description": description,
            "issuetype": {"name": issue_type},
        }
    }
    _apply_jira_field_mapping(payload["fields"], field_mapping)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base_url}/rest/api/2/issue",
            json=payload,
            auth=(email, api_token),
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code not in (200, 201):
        detail = resp.text[:500]
        logger.error(f"Jira 创建失败: HTTP {resp.status_code} - {detail}")
        raise RuntimeError(f"Jira 创建失败: HTTP {resp.status_code}")

    data = resp.json()
    issue_key = data["key"]
    return {
        "bug_id": issue_key,
        "bug_url": f"{base_url}/browse/{issue_key}",
        "title": title,
    }


async def _test_jira_connection(config: dict) -> dict:
    base_url = config["base_url"].rstrip("/")
    email = config["email"]
    api_token = config["api_token"]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base_url}/rest/api/2/myself",
            auth=(email, api_token),
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Jira 连接失败: HTTP {resp.status_code}")
    data = resp.json()
    return {"ok": True, "message": f"连接成功：{data.get('displayName') or data.get('emailAddress') or email}"}


async def _get_jira_bug_status(config: dict, bug_id: str) -> dict:
    base_url = config["base_url"].rstrip("/")
    email = config["email"]
    api_token = config["api_token"]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base_url}/rest/api/2/issue/{bug_id}",
            params={"fields": "status"},
            auth=(email, api_token),
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Jira 状态查询失败: HTTP {resp.status_code}")
    status_name = resp.json().get("fields", {}).get("status", {}).get("name", "unknown")
    return {"bug_id": bug_id, "status": status_name, "bug_url": f"{base_url}/browse/{bug_id}"}


async def _find_jira_duplicate(config: dict, title: str) -> dict | None:
    base_url = config["base_url"].rstrip("/")
    email = config["email"]
    api_token = config["api_token"]
    project_key = config["project_key"]
    jql_title = _escape_jira_jql_value(title)
    jql = f'project = "{project_key}" AND summary ~ "{jql_title}" ORDER BY created DESC'
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base_url}/rest/api/2/search",
            params={"jql": jql, "maxResults": 5, "fields": "summary,status"},
            auth=(email, api_token),
        )
    if resp.status_code != 200:
        return None
    issues = resp.json().get("issues", [])
    for issue in issues:
        if issue.get("fields", {}).get("summary") == title:
            key = issue.get("key")
            return {"bug_id": key, "bug_url": f"{base_url}/browse/{key}", "title": title}
    return None


async def _upload_jira_attachment(config: dict, bug_id: str, filename: str, content: bytes) -> bool:
    base_url = config["base_url"].rstrip("/")
    email = config["email"]
    api_token = config["api_token"]
    files = {"file": (filename, content, "image/png")}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url}/rest/api/2/issue/{bug_id}/attachments",
            files=files,
            auth=(email, api_token),
            headers={"X-Atlassian-Token": "no-check"},
        )
    return resp.status_code in (200, 201)


# ── 禅道 ─────────────────────────────────────────────────

async def _zentao_get_token(config: dict) -> tuple[str, str]:
    base_url = config["base_url"].rstrip("/")
    account = config["account"]
    password = config["password"]
    async with httpx.AsyncClient(timeout=15) as client:
        login_resp = await client.post(
            f"{base_url}/api.php/v1/tokens",
            json={"account": account, "password": password},
        )
    if login_resp.status_code not in (200, 201):
        raise RuntimeError(f"禅道登录失败: HTTP {login_resp.status_code}")
    token = login_resp.json().get("token", "")
    if not token:
        raise RuntimeError("禅道登录失败: 未获取到 token")
    return base_url, token


def _apply_zentao_field_mapping(payload: dict, field_mapping: dict) -> None:
    if not field_mapping:
        return
    if field_mapping.get("priority") is not None:
        payload["pri"] = field_mapping["priority"]
    if field_mapping.get("severity") is not None:
        payload["severity"] = field_mapping["severity"]
    if field_mapping.get("module") is not None:
        payload["module"] = field_mapping["module"]
    if field_mapping.get("keywords"):
        payload["keywords"] = ",".join(field_mapping["keywords"])
    for key, value in (field_mapping.get("custom_fields") or {}).items():
        payload[key] = value


def _resolve_zentao_product_id(config: dict, override: str | None) -> int | str:
    """禅道多产品：优先 override，其次 config.product_id；override 可为 product_map 的 key 或直接的 id。"""
    if override is None or override == "":
        return config["product_id"]
    product_map = config.get("product_map") or {}
    if override in product_map:
        return product_map[override]
    # 数字字符串：直接转 int；否则原样返回（让禅道侧校验）
    try:
        return int(override)
    except (TypeError, ValueError):
        return override


async def _create_zentao_bug(
    config: dict,
    title: str,
    description: str,
    field_mapping: dict,
    override_product_id: str | None = None,
) -> dict:
    base_url, token = await _zentao_get_token(config)
    product_id = _resolve_zentao_product_id(config, override_product_id)
    headers = {"Token": token, "Content-Type": "application/json"}
    bug_payload = {
        "product": product_id,
        "title": title,
        "steps": description,
        "type": "codeerror",
        "severity": 3,
        "pri": 3,
    }
    _apply_zentao_field_mapping(bug_payload, field_mapping)
    async with httpx.AsyncClient(timeout=15) as client:
        bug_resp = await client.post(
            f"{base_url}/api.php/v1/bugs",
            json=bug_payload,
            headers=headers,
        )

    if bug_resp.status_code not in (200, 201):
        detail = bug_resp.text[:500]
        logger.error(f"禅道创建 Bug 失败: HTTP {bug_resp.status_code} - {detail}")
        raise RuntimeError(f"禅道创建 Bug 失败: HTTP {bug_resp.status_code}")

    data = bug_resp.json()
    bug_id = str(data.get("id", ""))
    return {
        "bug_id": bug_id,
        "bug_url": f"{base_url}/bug-view-{bug_id}.html",
        "title": title,
    }


async def _test_zentao_connection(config: dict) -> dict:
    base_url, token = await _zentao_get_token(config)
    return {"ok": True, "message": f"连接成功：已获取 token（{token[:8]}...）"}


async def _get_zentao_bug_status(config: dict, bug_id: str) -> dict:
    base_url, token = await _zentao_get_token(config)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base_url}/api.php/v1/bugs/{bug_id}",
            headers={"Token": token},
        )
    if resp.status_code != 200:
        raise RuntimeError(f"禅道状态查询失败: HTTP {resp.status_code}")
    data = resp.json().get("bug") or resp.json().get("data") or resp.json()
    if isinstance(data, list):
        data = data[0] if data else {}
    status_name = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
    return {"bug_id": bug_id, "status": status_name, "bug_url": f"{base_url}/bug-view-{bug_id}.html"}


async def _find_zentao_duplicate(config: dict, title: str) -> dict | None:
    base_url, token = await _zentao_get_token(config)
    product_id = config["product_id"]
    headers = {"Token": token}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base_url}/api.php/v1/bugs",
            params={"product": product_id, "limit": 20},
            headers=headers,
        )
    if resp.status_code != 200:
        return None
    items = resp.json().get("bugs") or resp.json().get("data") or resp.json()
    if isinstance(items, dict):
        items = items.get("items", [])
    if not isinstance(items, list):
        return None
    for bug in items:
        if str(bug.get("title", "")).strip() == title:
            bug_id = str(bug.get("id", ""))
            return {"bug_id": bug_id, "bug_url": f"{base_url}/bug-view-{bug_id}.html", "title": title}
    return None


async def _upload_zentao_attachment(config: dict, bug_id: str, filename: str, content: bytes) -> bool:
    base_url, token = await _zentao_get_token(config)
    files = {"files": (filename, content, "image/png")}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url}/api.php/v1/bugs/{bug_id}/files",
            files=files,
            headers={"Token": token},
        )
    return resp.status_code in (200, 201)


# ── GitHub Issues ───────────────────────────────────────


def _github_headers(config: dict) -> dict:
    token = config["token"]
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _github_base_url(config: dict) -> str:
    return config.get("base_url", "https://api.github.com").rstrip("/")


def _apply_github_field_mapping(field_mapping: dict) -> dict:
    payload: dict[str, Any] = {}
    if field_mapping.get("labels"):
        payload["labels"] = field_mapping["labels"]
    if field_mapping.get("assignees"):
        payload["assignees"] = field_mapping["assignees"]
    return payload


async def _test_github_connection(config: dict) -> dict:
    base_url = _github_base_url(config)
    headers = _github_headers(config)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{base_url}/repos/{config['owner']}/{config['repo']}", headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"GitHub 连接失败: HTTP {resp.status_code}")
    return {"ok": True, "message": f"连接成功：{config['owner']}/{config['repo']}"}


async def _create_github_issue(config: dict, title: str, description: str, field_mapping: dict) -> dict:
    base_url = _github_base_url(config)
    headers = _github_headers(config)
    payload = {"title": title, "body": description, **_apply_github_field_mapping(field_mapping)}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{base_url}/repos/{config['owner']}/{config['repo']}/issues", json=payload, headers=headers)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"GitHub 创建 Issue 失败: HTTP {resp.status_code}")
    data = resp.json()
    return {"bug_id": str(data["number"]), "bug_url": data["html_url"], "title": title}


async def _find_github_duplicate(config: dict, title: str) -> dict | None:
    base_url = _github_base_url(config)
    headers = _github_headers(config)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base_url}/repos/{config['owner']}/{config['repo']}/issues",
            params={"state": "all", "per_page": 20},
            headers=headers,
        )
    if resp.status_code != 200:
        return None
    for issue in resp.json():
        if issue.get("pull_request"):
            continue
        if issue.get("title") == title:
            return {"bug_id": str(issue["number"]), "bug_url": issue["html_url"], "title": title}
    return None


async def _get_github_issue_status(config: dict, bug_id: str) -> dict:
    base_url = _github_base_url(config)
    headers = _github_headers(config)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{base_url}/repos/{config['owner']}/{config['repo']}/issues/{bug_id}", headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"GitHub 状态查询失败: HTTP {resp.status_code}")
    data = resp.json()
    return {"bug_id": bug_id, "status": data.get("state", "unknown"), "bug_url": data.get("html_url")}


# ── GitLab Issues ───────────────────────────────────────


def _gitlab_headers(config: dict) -> dict:
    return {
        "PRIVATE-TOKEN": config["token"],
        "Content-Type": "application/json",
    }


def _gitlab_base_url(config: dict) -> str:
    return config.get("base_url", "https://gitlab.com").rstrip("/")


def _gitlab_project_path(config: dict) -> str:
    """GitLab project_id 可以是数字或 group/repo 编码后形式。"""
    from urllib.parse import quote

    project_id = str(config["project_id"])
    return quote(project_id, safe="")


async def _test_gitlab_connection(config: dict) -> dict:
    base_url = _gitlab_base_url(config)
    project = _gitlab_project_path(config)
    headers = _gitlab_headers(config)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{base_url}/api/v4/projects/{project}", headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"GitLab 连接失败: HTTP {resp.status_code}")
    data = resp.json()
    return {"ok": True, "message": f"连接成功：{data.get('path_with_namespace', config['project_id'])}"}


def _apply_gitlab_field_mapping(payload: dict, field_mapping: dict) -> None:
    if not field_mapping:
        return
    if field_mapping.get("labels"):
        payload["labels"] = ",".join(field_mapping["labels"])
    if field_mapping.get("assignee_ids"):
        payload["assignee_ids"] = field_mapping["assignee_ids"]
    if field_mapping.get("milestone_id") is not None:
        payload["milestone_id"] = field_mapping["milestone_id"]


async def _create_gitlab_issue(config: dict, title: str, description: str, field_mapping: dict) -> dict:
    base_url = _gitlab_base_url(config)
    project = _gitlab_project_path(config)
    headers = _gitlab_headers(config)
    payload: dict[str, Any] = {"title": title, "description": description}
    _apply_gitlab_field_mapping(payload, field_mapping)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base_url}/api/v4/projects/{project}/issues",
            json=payload,
            headers=headers,
        )
    if resp.status_code not in (200, 201):
        detail = resp.text[:500]
        logger.error(f"GitLab 创建 Issue 失败: HTTP {resp.status_code} - {detail}")
        raise RuntimeError(f"GitLab 创建 Issue 失败: HTTP {resp.status_code}")
    data = resp.json()
    return {
        "bug_id": str(data.get("iid", data.get("id", ""))),
        "bug_url": data.get("web_url", ""),
        "title": title,
    }


async def _find_gitlab_duplicate(config: dict, title: str) -> dict | None:
    base_url = _gitlab_base_url(config)
    project = _gitlab_project_path(config)
    headers = _gitlab_headers(config)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base_url}/api/v4/projects/{project}/issues",
            params={"search": title, "in": "title", "per_page": 20},
            headers=headers,
        )
    if resp.status_code != 200:
        return None
    for issue in resp.json():
        if issue.get("title") == title:
            return {
                "bug_id": str(issue.get("iid", issue.get("id", ""))),
                "bug_url": issue.get("web_url", ""),
                "title": title,
            }
    return None


async def _get_gitlab_issue_status(config: dict, bug_id: str) -> dict:
    base_url = _gitlab_base_url(config)
    project = _gitlab_project_path(config)
    headers = _gitlab_headers(config)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{base_url}/api/v4/projects/{project}/issues/{bug_id}",
            headers=headers,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"GitLab 状态查询失败: HTTP {resp.status_code}")
    data = resp.json()
    return {
        "bug_id": bug_id,
        "status": data.get("state", "unknown"),
        "bug_url": data.get("web_url", ""),
    }


def build_bug_description(
    run_id: int,
    case_name: str,
    environment: str | None,
    error_message: str | None,
    step_name: str | None = None,
    step_index: int | None = None,
    request_data: dict | None = None,
    response_data: dict | None = None,
) -> str:
    """构建缺陷描述文本"""
    lines = [
        f"来自 ATP 自动化测试平台，执行记录 #{run_id}",
        "",
        f"用例: {case_name}",
        f"环境: {environment or '-'}",
    ]
    if step_name is not None:
        lines.append(f"失败步骤: #{step_index + 1} {step_name}" if step_index is not None else f"失败步骤: {step_name}")
    if error_message:
        lines.append(f"\n错误信息:\n{error_message}")
    if request_data:
        lines.append(f"\n请求数据:\n{json.dumps(request_data, ensure_ascii=False, indent=2)[:2000]}")
    if response_data:
        lines.append(f"\n响应数据:\n{json.dumps(response_data, ensure_ascii=False, indent=2)[:2000]}")

    return "\n".join(lines)
