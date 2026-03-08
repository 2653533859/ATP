"""
缺陷创建服务

支持两种平台：
- Jira:  REST API v2，Basic Auth (email + API Token)
- 禅道:  REST API，Session Token 认证
"""
import json
import logging

import httpx

logger = logging.getLogger(__name__)


async def create_bug(
    tracker_type: str,
    config: dict,
    title: str,
    description: str,
) -> dict:
    """
    创建缺陷，返回 {"bug_id": "...", "bug_url": "...", "title": "..."}.

    Raises RuntimeError on failure.
    """
    if tracker_type == "jira":
        return await _create_jira_issue(config, title, description)
    elif tracker_type == "zentao":
        return await _create_zentao_bug(config, title, description)
    else:
        raise ValueError(f"不支持的缺陷跟踪平台: {tracker_type}")


# ── Jira ─────────────────────────────────────────────────

async def _create_jira_issue(config: dict, title: str, description: str) -> dict:
    """
    通过 Jira REST API v2 创建 Issue。

    config 示例:
    {
        "base_url": "https://xxx.atlassian.net",
        "email": "user@example.com",
        "api_token": "...",
        "project_key": "ATP",
        "issue_type": "Bug"         # 可选，默认 Bug
    }
    """
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


# ── 禅道 ─────────────────────────────────────────────────

async def _create_zentao_bug(config: dict, title: str, description: str) -> dict:
    """
    通过禅道 REST API 创建 Bug。

    config 示例:
    {
        "base_url": "http://zentao.xxx.com",
        "account": "admin",
        "password": "...",
        "product_id": 1
    }
    """
    base_url = config["base_url"].rstrip("/")
    account = config["account"]
    password = config["password"]
    product_id = config["product_id"]

    async with httpx.AsyncClient(timeout=15) as client:
        # 1. 获取 session token
        login_resp = await client.post(
            f"{base_url}/api.php/v1/tokens",
            json={"account": account, "password": password},
        )
        if login_resp.status_code not in (200, 201):
            raise RuntimeError(f"禅道登录失败: HTTP {login_resp.status_code}")

        token = login_resp.json().get("token", "")
        if not token:
            raise RuntimeError("禅道登录失败: 未获取到 token")

        headers = {"Token": token, "Content-Type": "application/json"}

        # 2. 创建 Bug
        bug_payload = {
            "product": product_id,
            "title": title,
            "steps": description,
            "type": "codeerror",
            "severity": 3,
            "pri": 3,
        }
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
