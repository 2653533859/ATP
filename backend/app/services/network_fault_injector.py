"""Network Packet Capture Analysis and Fault Injection Service (Q1.3).

Provides:
1. Standard HTTP Archive (HAR 1.2) capture parsing and network performance profiling.
2. Network fault injection simulator:
   - DNS spoofing / NXDOMAIN failure
   - TCP connection resets (ECONNRESET) and SYN timeouts (ETIMEDOUT)
   - HTTP status code injection (502 / 503 / 504)
   - Response body corruption / tampering
3. Fault incident compilation and artifact archiving.
"""

from __future__ import annotations

import json
import logging
import random
import re
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def parse_har_capture(har_content: str | bytes | dict[str, Any]) -> dict[str, Any]:
    """Parse standard HTTP Archive (HAR 1.2) data into aggregated network metrics."""
    raw_har: Any
    if isinstance(har_content, (str, bytes)):
        try:
            raw_har = json.loads(har_content)
        except Exception as exc:
            return {"valid": False, "error": f"Invalid HAR JSON: {exc}"}
    elif isinstance(har_content, dict):
        raw_har = har_content
    else:
        return {"valid": False, "error": "HAR content must be JSON string, bytes, or dict"}

    if not isinstance(raw_har, dict):
        return {"valid": False, "error": "HAR content root must be a JSON object"}

    raw_log = raw_har.get("log")
    log: dict[str, Any] = raw_log if isinstance(raw_log, dict) else {}
    raw_entries = log.get("entries")
    entries: list[Any] = raw_entries if isinstance(raw_entries, list) else []

    total_requests = len(entries)
    if total_requests == 0:
        return {
            "valid": True,
            "total_requests": 0,
            "failed_requests": 0,
            "total_bytes_transferred": 0,
            "avg_latency_ms": 0.0,
            "domains_accessed": [],
            "slowest_requests": [],
            "entries_summary": [],
        }

    failed_count = 0
    total_bytes = 0
    latencies: list[float] = []
    domains: set[str] = set()
    parsed_entries: list[dict[str, Any]] = []

    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        req = entry.get("request") or {}
        resp = entry.get("response") or {}
        url = str(req.get("url") or "")
        method = str(req.get("method") or "GET")
        status = int(resp.get("status") or 0)
        time_ms = float(entry.get("time") or 0.0)

        # Body sizes
        body_size = int(resp.get("bodySize", 0))
        headers_size = int(resp.get("headersSize", 0))
        entry_bytes = max(0, body_size) + max(0, headers_size)
        total_bytes += entry_bytes
        latencies.append(time_ms)

        if url:
            domain = urlparse(url).netloc
            if domain:
                domains.add(domain)

        is_failed = status == 0 or status >= 400
        if is_failed:
            failed_count += 1

        parsed_entries.append(
            {
                "index": idx,
                "url": url,
                "method": method,
                "status": status,
                "duration_ms": round(time_ms, 2),
                "bytes": entry_bytes,
                "is_failed": is_failed,
            }
        )

    # Find top 5 slowest requests
    slowest = sorted(parsed_entries, key=lambda x: x["duration_ms"], reverse=True)[:5]
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    return {
        "valid": True,
        "total_requests": total_requests,
        "failed_requests": failed_count,
        "success_rate": round(((total_requests - failed_count) / total_requests) * 100.0, 2),
        "total_bytes_transferred": total_bytes,
        "avg_latency_ms": avg_latency,
        "domains_accessed": sorted(domains),
        "slowest_requests": slowest,
        "entries_summary": parsed_entries,
    }


def simulate_network_fault(
    request_url: str,
    fault_policy: dict[str, Any],
    *,
    seed: float | None = None,
) -> dict[str, Any]:
    """Evaluate a request URL against a fault injection policy (DNS spoofing, timeout, reset, 5xx)."""
    url_pattern = str(fault_policy.get("url_pattern") or ".*")
    try:
        if not re.search(url_pattern, request_url, re.IGNORECASE):
            return {"fault_injected": False, "action": "pass", "target_url": request_url}
    except re.error:
        # If invalid regex, fall back to simple substring match
        if url_pattern not in request_url:
            return {"fault_injected": False, "action": "pass", "target_url": request_url}

    probability = float(fault_policy.get("probability", 1.0))
    rnd = random.Random(seed) if seed is not None else random
    if rnd.uniform(0.0, 1.0) > probability:
        return {"fault_injected": False, "action": "pass", "target_url": request_url}

    fault_type = str(fault_policy.get("fault_type") or "connection_reset").lower()
    params = fault_policy.get("params") or {}

    if fault_type == "dns_nxdomain":
        return {
            "fault_injected": True,
            "fault_type": "dns_nxdomain",
            "action": "fail",
            "target_url": request_url,
            "error": f"DNS resolution failed (NXDOMAIN): Name or service not known for {urlparse(request_url).hostname}",
        }

    elif fault_type == "dns_spoofing":
        spoofed_host = str(params.get("spoofed_host") or "127.0.0.1:9999")
        parsed = urlparse(request_url)
        hijacked_url = request_url.replace(parsed.netloc, spoofed_host, 1)
        return {
            "fault_injected": True,
            "fault_type": "dns_spoofing",
            "action": "redirect",
            "target_url": request_url,
            "hijacked_url": hijacked_url,
            "spoofed_host": spoofed_host,
        }

    elif fault_type in ("connection_reset", "econnreset"):
        return {
            "fault_injected": True,
            "fault_type": "connection_reset",
            "action": "fail",
            "target_url": request_url,
            "error": "ConnectionResetError: [Errno 104] Connection reset by peer",
        }

    elif fault_type in ("connection_timeout", "etimedout"):
        return {
            "fault_injected": True,
            "fault_type": "connection_timeout",
            "action": "fail",
            "target_url": request_url,
            "error": f"TimeoutError: Connection timed out connecting to {request_url}",
        }

    elif fault_type in ("http_error", "http_5xx"):
        status_code = int(params.get("status_code", 502))
        return {
            "fault_injected": True,
            "fault_type": "http_error",
            "action": "mock_response",
            "target_url": request_url,
            "status_code": status_code,
            "response_body": params.get("response_body", f"HTTP {status_code} Fault Injected"),
        }

    elif fault_type == "content_tampering":
        return {
            "fault_injected": True,
            "fault_type": "content_tampering",
            "action": "tamper",
            "target_url": request_url,
            "corrupted_payload": params.get("corrupted_payload", "CORRUPTED_STREAM_0xFF"),
        }

    return {"fault_injected": False, "action": "pass", "target_url": request_url}


def archive_network_fault_incident(
    fault_result: dict[str, Any],
    *,
    step_name: str | None = None,
    run_id: int | None = None,
) -> dict[str, Any]:
    """Compile a structured incident artifact summarizing a triggered fault injection event."""
    return {
        "incident_type": "network_fault_injection",
        "run_id": run_id,
        "step_name": step_name or "network_request",
        "fault_type": fault_result.get("fault_type"),
        "target_url": fault_result.get("target_url"),
        "error_or_action": fault_result.get("error") or fault_result.get("action"),
        "details": fault_result,
    }
