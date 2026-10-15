"""W3C/Appium 2 XCUITest Session Recovery and Self-Healing Service (T1.2).

Detects WebDriverAgent (WDA) crashes, session termination, and orchestrates
automatic session re-establishment to heal broken test execution flows.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Error signatures indicative of WDA crashes or dead sessions
WDA_CRASH_SIGNATURES = (
    "session terminated",
    "a session is either terminated or not started",
    "wda unresponsive",
    "webdriveragentrunner-runner crashed",
    "connection refused",
    "session not found",
    "invalid session id",
    "unable to connect to webdriveragent",
    "instrumentation crashed",
)


def is_wda_session_crash(error: str | BaseException) -> bool:
    """Return True if an error matches known WDA session crashes or terminations."""
    text = str(error).lower()
    return any(sig in text for sig in WDA_CRASH_SIGNATURES)


async def recover_wda_session(
    appium_server_url: str,
    capabilities: dict[str, Any],
    *,
    timeout: float = 30.0,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Attempt to create a fresh W3C session on Appium / WDA after a session crash.

    Returns dict with recovered status, new session_id, and any error message.
    """
    server_url = appium_server_url.rstrip("/")
    client = http_client or httpx.AsyncClient(timeout=timeout)
    owns_client = http_client is None

    try:
        # 1. Health probe WDA / Appium status
        status_resp = await client.get(f"{server_url}/status")
        if status_resp.status_code != 200:
            return {
                "recovered": False,
                "error": f"Appium/WDA status probe failed: HTTP {status_resp.status_code}",
            }

        # 2. Request new W3C session
        payload = {
            "capabilities": {
                "alwaysMatch": capabilities,
                "firstMatch": [{}],
            }
        }
        session_resp = await client.post(f"{server_url}/session", json=payload)
        if session_resp.status_code not in (200, 201):
            return {
                "recovered": False,
                "error": f"Failed to recreate W3C session: HTTP {session_resp.status_code} - {session_resp.text[:300]}",
            }

        session_data = session_resp.json()
        val = session_data.get("value", {})
        session_id = val.get("sessionId") if isinstance(val, dict) else session_data.get("sessionId")
        if not session_id:
            return {
                "recovered": False,
                "error": "Appium response missing sessionId",
            }

        logger.info("Successfully recovered WDA session: %s on %s", session_id, server_url)
        return {
            "recovered": True,
            "session_id": session_id,
            "capabilities": val.get("capabilities", capabilities) if isinstance(val, dict) else capabilities,
        }
    except Exception as exc:
        logger.warning("WDA session recovery failed on %s: %s", server_url, exc)
        return {
            "recovered": False,
            "error": str(exc),
        }
    finally:
        if owns_client:
            await client.aclose()
