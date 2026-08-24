"""Trigger an ATP performance test and wait for its CI threshold gate."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode


def _request_json(url: str, method: str, api_key: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        detail = ""
        if isinstance(exc, HTTPError):
            try:
                detail = exc.read().decode("utf-8")[:500]
            except OSError:
                pass
        raise RuntimeError(f"ATP performance gate request failed: {detail or exc}") from exc


def gate_exit_code(gate: dict) -> int:
    """Return a CI-friendly exit code for a terminal gate payload."""
    status = gate.get("status")
    if status == "passed":
        return 0
    if status == "failed" or status == "cancelled":
        return 1
    if status == "not_configured":
        return 2
    return 3


def _load_options(path: str | None) -> dict:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("performance options file must contain a JSON object")
    return data


def default_idempotency_key(test_id: int, environment_id: int | None) -> str:
    """Use a stable CI execution identifier when available, otherwise isolate a CLI run."""

    ci_run = (
        os.environ.get("CI_PIPELINE_ID")
        or os.environ.get("GITHUB_RUN_ID")
        or os.environ.get("BUILD_BUILDID")
        or os.environ.get("BUILD_ID")
    )
    if ci_run:
        environment_part = environment_id if environment_id is not None else "none"
        return f"ci-{ci_run}-performance-{test_id}-env-{environment_part}"[:128]
    return f"cli-performance-{test_id}-{uuid.uuid4().hex}"


def build_gate_url(
    base_url: str,
    run_id: int,
    *,
    require_baseline: bool = False,
    fail_on_baseline_regression: bool = False,
) -> str:
    """Build the polling URL while keeping baseline policy opt-in."""

    params = {}
    if require_baseline:
        params["require_baseline"] = "true"
    if fail_on_baseline_regression:
        params["fail_on_baseline_regression"] = "true"
    url = f"{base_url.rstrip('/')}/api/v1/webhook/performance-runs/{run_id}/gate"
    return f"{url}?{urlencode(params)}" if params else url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("ATP_BASE_URL"), required=False)
    parser.add_argument("--test-id", type=int, default=os.environ.get("ATP_PERFORMANCE_TEST_ID"))
    parser.add_argument(
        "--api-key",
        default=os.environ.get("ATP_API_KEY") or os.environ.get("ATP_WEBHOOK_KEY"),
    )
    parser.add_argument("--environment-id", type=int, default=None)
    parser.add_argument(
        "--idempotency-key",
        default=os.environ.get("ATP_PERFORMANCE_IDEMPOTENCY_KEY"),
        help="重复执行 CI 时复用的幂等键；未提供时优先使用 CI run ID，否则每次 CLI 调用生成新键",
    )
    parser.add_argument("--options-file", default=None)
    parser.add_argument(
        "--require-baseline",
        action="store_true",
        help="没有可用基线时返回 not_configured（退出码 2）",
    )
    parser.add_argument(
        "--fail-on-baseline-regression",
        action="store_true",
        help="基线核心指标出现回归时让门禁失败",
    )
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--poll-interval", type=float, default=5)
    args = parser.parse_args()

    if not args.base_url or not args.test_id or not args.api_key:
        parser.error("--base-url/ATP_BASE_URL、--test-id/ATP_PERFORMANCE_TEST_ID 和 --api-key/ATP_API_KEY 均为必填")

    base_url = args.base_url.rstrip("/")
    idempotency_key = args.idempotency_key or default_idempotency_key(args.test_id, args.environment_id)
    try:
        trigger = _request_json(
            f"{base_url}/api/v1/webhook/trigger",
            "POST",
            args.api_key,
            {
                "target_type": "performance_test",
                "target_id": args.test_id,
                "env_id": args.environment_id,
                "idempotency_key": idempotency_key,
                "options": _load_options(args.options_file),
            },
        )
        run_id = trigger["run_id"]
        deadline = time.monotonic() + args.timeout
        while True:
            gate = _request_json(
                build_gate_url(
                    base_url,
                    run_id,
                    require_baseline=args.require_baseline,
                    fail_on_baseline_regression=args.fail_on_baseline_regression,
                ),
                "GET",
                args.api_key,
            )
            print(json.dumps(gate, ensure_ascii=False))
            if gate.get("ready"):
                return gate_exit_code(gate)
            if time.monotonic() >= deadline:
                print("ATP performance gate timed out", file=sys.stderr)
                return 3
            time.sleep(max(0.2, args.poll_interval))
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
