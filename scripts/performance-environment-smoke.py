"""Run production-like acceptance checks for the dedicated performance worker.

The command deliberately keeps external checks opt-in.  It can verify the ATP API,
registered performance node, target TCP/TLS reachability, Kubernetes rollout and
worker dependencies.  A real performance run or cancellation is only started when
the operator supplies an existing performance test ID.

Examples::

    python scripts/performance-environment-smoke.py \
      --api-base-url https://atp.example.test \
      --namespace atp-staging \
      --deployment atp-atp-performance-worker \
      --node-id worker-a \
      --target grpcs://grpc.example.test:443 \
      --require-tls --ca-file /etc/atp/ca.pem \
      --require-node-allowlist \
      --smoke-test-id 42 --require-metrics \
      --report docs/evidence/performance-smoke-2026-08-07.json

Credentials are read from ``ATP_TOKEN`` or ``ATP_USERNAME``/``ATP_PASSWORD``;
they are never accepted as command-line arguments and never written to the report.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import socket
import ssl
import subprocess
import sys
import time
from typing import Any, Callable
import uuid
from urllib.error import HTTPError, URLError
from http.cookiejar import CookieJar
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from urllib.request import urlopen


_SENSITIVE_KEY_RE = re.compile(
    r"(?:token|secret|password|passwd|api[_-]?key|credential|authorization|cookie)", re.IGNORECASE
)
_TERMINAL_RUN_STATES = {"success", "failed", "cancelled"}


class SmokeError(RuntimeError):
    """An acceptance check could not prove its required condition."""


@dataclass(frozen=True)
class Target:
    host: str
    port: int
    tls: bool
    server_name: str | None = None


@dataclass
class Check:
    name: str
    status: str
    detail: str


class CheckReport:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def add(self, name: str, status: str, detail: str) -> None:
        self.checks.append(Check(name=name, status=status, detail=detail))
        print(f"[{status}] {name}: {detail}")

    def passed(self, name: str, detail: str) -> None:
        self.add(name, "PASS", detail)

    def failed(self, name: str, detail: str) -> None:
        self.add(name, "FAIL", detail)

    def skipped(self, name: str, detail: str) -> None:
        self.add(name, "SKIP", detail)

    @property
    def has_failures(self) -> bool:
        return any(item.status == "FAIL" for item in self.checks)

    def write(self, path: Path, *, args: argparse.Namespace) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "command": " ".join(shlex.quote(item) for item in _safe_argv(sys.argv)),
            "inputs": _safe_cli_inputs(args),
            "status": "failed" if self.has_failures else "passed",
            "checks": [asdict(item) for item in self.checks],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _safe_cli_inputs(args: argparse.Namespace) -> dict[str, Any]:
    """Return report inputs without password/token values or full environment dumps."""
    values = vars(args).copy()
    values.pop("password", None)
    for key in ("api_base_url", "prometheus_url"):
        if isinstance(values.get(key), str):
            values[key] = _redact_url(values[key])
    return {key: str(value) if isinstance(value, Path) else value for key, value in values.items()}


def _redact_url(value: str) -> str:
    """Remove URL userinfo, query and fragment before writing command evidence."""
    raw = str(value)
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return "<redacted-url>"
    if not parsed.scheme or not parsed.netloc:
        return raw
    netloc = parsed.netloc.rsplit("@", 1)[-1] if parsed.username or parsed.password else parsed.netloc
    if parsed.username or parsed.password:
        netloc = f"<redacted>@{netloc}"
    query = "<redacted>" if parsed.query else ""
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, ""))


def _safe_argv(argv: list[str]) -> list[str]:
    """Redact URL values in the recorded command, including separate option values."""
    url_options = {"--api-base-url", "--prometheus-url"}
    safe: list[str] = []
    redact_next = False
    for item in argv:
        if redact_next:
            safe.append(_redact_url(item))
            redact_next = False
            continue
        if item in url_options:
            safe.append(item)
            redact_next = True
        elif any(item.startswith(f"{option}=") for option in url_options):
            option, raw = item.split("=", 1)
            safe.append(f"{option}={_redact_url(raw)}")
        else:
            safe.append(item)
    return safe


def _validate_idempotency_key(value: str) -> str:
    """Validate the key before sending an acceptance request to the API."""
    key = str(value or "").strip()
    if not key:
        raise SmokeError("幂等键不能为空")
    if len(key) > 128 or not re.fullmatch(r"[A-Za-z0-9._:-]+", key):
        raise SmokeError("幂等键只能包含字母、数字、点、下划线、冒号和连字符，长度不能超过 128")
    return key


def default_idempotency_key(scope: str, test_id: int, explicit: str | None = None) -> str:
    """Build a retry-safe key for one acceptance scope.

    CI reruns should reuse the same key so a lost HTTP response cannot enqueue a
    second run. Local invocations get a fresh key by default. A caller-provided
    base key is scoped so smoke and cancellation checks in one command never
    accidentally address the same Run.
    """
    base = (explicit or os.environ.get("ATP_PERFORMANCE_IDEMPOTENCY_KEY", "")).strip()
    if base:
        normalized = _validate_idempotency_key(base)
        return _validate_idempotency_key(f"{normalized}-{scope}")

    ci_run = next(
        (
            os.environ.get(name, "").strip()
            for name in ("CI_PIPELINE_ID", "GITHUB_RUN_ID", "BUILD_BUILDID", "BUILD_ID")
            if os.environ.get(name, "").strip()
        ),
        "",
    )
    if ci_run:
        return _validate_idempotency_key(f"ci-{ci_run}-acceptance-{scope}-{test_id}"[:128])
    return _validate_idempotency_key(f"cli-acceptance-{scope}-{test_id}-{uuid.uuid4().hex}")


def _safe_json(value: Any, *, key: str = "") -> Any:
    if _SENSITIVE_KEY_RE.search(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {str(item_key): _safe_json(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [_safe_json(item, key=key) for item in value]
    return value


def _safe_error(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = _safe_json(value)
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return text[:800] or "unknown error"


def parse_target(raw: str, *, require_tls: bool = False, server_name: str | None = None) -> Target:
    """Parse grpc://host:port, grpcs://host:port, or a bare host:port target."""
    value = str(raw or "").strip()
    if not value:
        raise SmokeError("目标地址不能为空")

    has_scheme = "://" in value
    parsed = urlsplit(value if has_scheme else f"//{value}")
    scheme = parsed.scheme.lower() if has_scheme else ""
    if scheme and scheme not in {"grpc", "grpcs", "http", "https"}:
        raise SmokeError(f"不支持的目标协议: {scheme}")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise SmokeError("目标地址只能包含 host:port，不能包含路径、查询参数或片段")
    try:
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise SmokeError("目标地址端口无效") from exc
    if not host or port is None or not 1 <= port <= 65535:
        raise SmokeError("目标地址必须是 host:port，端口范围为 1-65535")
    inferred_tls = scheme in {"grpcs", "https"}
    if require_tls and not (inferred_tls or has_scheme is False):
        # A TLS scheme is explicit; bare host:port is allowed because the flag
        # instructs the socket check to wrap it in TLS.
        raise SmokeError("启用 TLS 检查时目标协议必须是 grpcs/https 或裸 host:port")
    return Target(
        host=host.lower(),
        port=port,
        tls=bool(require_tls or inferred_tls),
        server_name=server_name.strip() if server_name and server_name.strip() else None,
    )


def host_allowed(host: str, allowlist: list[str] | tuple[str, ...] | set[str]) -> bool:
    """Match the same exact-or-subdomain rule used by the performance worker."""
    normalized_host = str(host).strip().lower().rstrip(".")
    values = {str(item).strip().lower().rstrip(".") for item in allowlist if str(item).strip()}
    return not values or normalized_host in values or any(normalized_host.endswith(f".{item}") for item in values)


def check_target(target: Target, *, timeout: float, ca_file: str | None = None) -> str:
    """Verify DNS, TCP connectivity and (when requested) certificate validation."""
    try:
        addresses = socket.getaddrinfo(target.host, target.port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise SmokeError(f"DNS 解析失败: {target.host}: {_safe_error(exc)}") from exc
    if not addresses:
        raise SmokeError(f"DNS 未返回地址: {target.host}")

    try:
        connection = socket.create_connection((target.host, target.port), timeout=timeout)
    except OSError as exc:
        raise SmokeError(f"TCP 连接失败 {target.host}:{target.port}: {_safe_error(exc)}") from exc

    try:
        if target.tls:
            if ca_file and not Path(ca_file).is_file():
                raise SmokeError(f"CA 文件不存在: {ca_file}")
            context = ssl.create_default_context(cafile=ca_file)
            tls_name = target.server_name or target.host
            try:
                wrapped = context.wrap_socket(connection, server_hostname=tls_name)
            except ssl.SSLError as exc:
                raise SmokeError(f"TLS 握手或证书校验失败 {tls_name}: {_safe_error(exc)}") from exc
            wrapped.close()
            return f"DNS {len(addresses)} 个地址，TCP/TLS 已连接，证书校验通过（SNI={tls_name}）"
        return f"DNS {len(addresses)} 个地址，TCP 已连接"
    finally:
        try:
            connection.close()
        except OSError:
            pass


def check_prometheus(report: CheckReport, *, base_url: str, query: str, timeout: float) -> None:
    """Verify Prometheus readiness and one API query without exposing credentials."""
    value = str(base_url or "").strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SmokeError("Prometheus URL 必须是 http(s)://host[:port][/prefix]")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SmokeError("Prometheus URL 不能包含用户名、密码、查询参数或片段")
    promql = str(query or "").strip()
    if not promql:
        raise SmokeError("Prometheus 查询不能为空")

    def get(path: str) -> tuple[int, bytes]:
        request = Request(f"{value}{path}", headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", None) or response.getcode()
                return int(status), response.read()
        except HTTPError as exc:
            raise SmokeError(f"Prometheus 请求返回 HTTP {exc.code}: {_safe_error(exc.reason)}") from exc
        except (OSError, URLError) as exc:
            raise SmokeError(f"Prometheus 请求失败: {_safe_error(exc)}") from exc

    readiness_status, _ = get("/-/ready")
    if readiness_status != 200:
        raise SmokeError(f"Prometheus readiness 返回 HTTP {readiness_status}")

    query_path = "/api/v1/query?" + urlencode({"query": promql})
    query_status, body = get(query_path)
    if query_status != 200:
        raise SmokeError(f"Prometheus query 返回 HTTP {query_status}")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SmokeError("Prometheus query 返回了非 JSON 内容") from exc
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise SmokeError("Prometheus query status 不是 success")
    data = payload.get("data")
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, list):
        raise SmokeError("Prometheus query 缺少 data.result 数组")
    report.passed("prometheus", f"readiness=200，query status=success，result_count={len(result)}")


class ApiClient:
    def __init__(self, base_url: str, *, token: str | None, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        headers: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        data = None
        headers = {"Accept": "application/json", **(headers or {})}
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            headers.setdefault("X-Requested-With", "XMLHttpRequest")
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method.upper())
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                body = response.read()
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8", errors="replace"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                detail = exc.reason
            raise SmokeError(f"API {method.upper()} {path} 返回 HTTP {exc.code}: {_safe_error(detail)}") from exc
        except (OSError, URLError) as exc:
            raise SmokeError(f"API {method.upper()} {path} 连接失败: {_safe_error(exc)}") from exc
        if not body:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SmokeError(f"API {method.upper()} {path} 返回了非 JSON 内容") from exc


def login_from_environment(base_url: str, *, timeout: float) -> ApiClient:
    username = os.environ.get("ATP_USERNAME", "").strip()
    password = os.environ.get("ATP_PASSWORD", "")
    if not username or not password:
        raise SmokeError("API 验收需要 ATP_TOKEN，或同时设置 ATP_USERNAME 与 ATP_PASSWORD")
    client = ApiClient(base_url, token=None, timeout=timeout)
    result = client.request(
        "POST",
        "/api/v1/auth/login",
        {"username": username, "password": password},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    if not isinstance(result, dict) or result.get("authenticated") is not True:
        raise SmokeError("登录响应未建立 Cookie 会话")
    return client


def _node_executors(node: dict[str, Any]) -> set[str]:
    capabilities = node.get("capabilities")
    if not isinstance(capabilities, dict):
        return {"k6"}
    declared = capabilities.get("executors")
    if isinstance(declared, str):
        return {item.strip().lower() for item in declared.split(",") if item.strip()}
    if isinstance(declared, list):
        return {str(item).strip().lower() for item in declared if str(item).strip()}
    legacy = capabilities.get("executor")
    return {str(legacy).strip().lower()} if legacy else {"k6"}


def _find_node(nodes: Any, node_id: str) -> dict[str, Any]:
    if not isinstance(nodes, list):
        raise SmokeError("性能节点接口返回格式无效")
    for item in nodes:
        if isinstance(item, dict) and str(item.get("node_id", "")) == node_id:
            return item
    raise SmokeError(f"未找到性能节点 {node_id}")


def _test_target(options: dict[str, Any], executor: str) -> str | None:
    key = "target" if executor == "grpc" else "host"
    value = options.get(key)
    return str(value).strip() if isinstance(value, str) and value.strip() else None


def _assert_test_target_matches(test: dict[str, Any], expected: Target) -> None:
    executor = str(test.get("executor", "")).lower()
    options = test.get("default_options")
    if not isinstance(options, dict):
        return
    raw = _test_target(options, executor)
    if not raw:
        return
    actual = parse_target(raw)
    if actual.host != expected.host or actual.port != expected.port:
        raise SmokeError(f"压测定义目标 {actual.host}:{actual.port} 与验收目标 {expected.host}:{expected.port} 不一致")


def wait_for_run(
    client: ApiClient,
    run_id: int,
    *,
    timeout: float,
    poll_interval: float,
    expect_cancelled: bool = False,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_status = "unknown"
    while time.monotonic() < deadline:
        payload = client.request("GET", f"/api/v1/performance/runs/{run_id}")
        if not isinstance(payload, dict):
            raise SmokeError(f"运行 {run_id} 返回格式无效")
        last_status = str(payload.get("status", "unknown"))
        if last_status in _TERMINAL_RUN_STATES:
            if expect_cancelled and last_status != "cancelled":
                raise SmokeError(f"取消验收运行 {run_id} 最终状态为 {last_status}，不是 cancelled")
            return payload
        time.sleep(max(0.2, poll_interval))
    raise SmokeError(f"运行 {run_id} 在 {timeout:.0f}s 内未结束，最后状态为 {last_status}")


def validate_metric_samples(samples: Any, *, required_sources: set[str] | None = None) -> str:
    """Require usable samples and, when requested, prove each source emitted data."""
    if not isinstance(samples, list) or not samples:
        raise SmokeError("压测运行没有资源指标采样记录")

    usable_sources: set[str] = set()
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        metrics = sample.get("metrics")
        source = str(sample.get("source") or "").strip()
        if source and isinstance(metrics, dict) and metrics:
            usable_sources.add(source)

    required = {str(source).strip() for source in (required_sources or set()) if str(source).strip()}
    missing = sorted(required - usable_sources)
    if missing:
        raise SmokeError(f"压测运行缺少有效指标来源: {', '.join(missing)}")
    if not usable_sources:
        raise SmokeError("压测运行的指标样本均为空或没有 source")
    return ", ".join(sorted(usable_sources))


def validate_baseline_comparison(
    payload: Any,
    *,
    expected_run_id: int | None = None,
    fail_on_regression: bool = False,
) -> str:
    """Validate the baseline comparison contract and optionally reject regressions."""
    if not isinstance(payload, dict) or not isinstance(payload.get("metrics"), list):
        raise SmokeError("压测基线对比响应格式无效")
    metrics = [item for item in payload["metrics"] if isinstance(item, dict)]
    if not metrics:
        raise SmokeError("压测基线对比没有指标记录")
    if expected_run_id is not None and payload.get("run_id") != expected_run_id:
        raise SmokeError(f"压测基线对比 run_id={payload.get('run_id')} 与当前 run={expected_run_id} 不一致")
    regressions = [str(item.get("metric")) for item in metrics if item.get("direction") == "regression"]
    if fail_on_regression and regressions:
        raise SmokeError(f"压测基线出现回归: {', '.join(regressions)}")
    baseline_run_id = payload.get("baseline_run_id")
    return f"baseline_run={baseline_run_id} metrics={len(metrics)} regressions={len(regressions)}"


def trigger_run(
    client: ApiClient,
    test_id: int,
    *,
    node_db_id: int | None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"options": {}}
    if node_db_id is not None:
        body["performance_node_id"] = node_db_id
    if idempotency_key:
        body["idempotency_key"] = _validate_idempotency_key(idempotency_key)
    result = client.request("POST", f"/api/v1/performance/tests/{test_id}/run", body)
    if not isinstance(result, dict) or not isinstance(result.get("id"), int):
        raise SmokeError("创建压测运行时返回了无效 run")
    return result


def check_api_and_node(
    report: CheckReport,
    client: ApiClient,
    *,
    expected_executors: set[str],
    node_id: str | None,
    expected_queue: str | None,
    target: Target | None,
    require_allowlist: bool,
    node_ready_timeout: float = 60.0,
    node_poll_interval: float = 2.0,
) -> dict[str, Any] | None:
    health = client.request("GET", "/health")
    if not isinstance(health, dict) or health.get("status") != "ok":
        raise SmokeError("/health 未返回 status=ok")
    report.passed("api-health", "ATP /health 返回 status=ok")

    executors = client.request("GET", "/api/v1/performance/executors")
    if not isinstance(executors, list):
        raise SmokeError("执行器接口返回格式无效")
    by_name = {str(item.get("name")): item for item in executors if isinstance(item, dict)}
    unavailable = sorted(
        name for name in expected_executors if not isinstance(by_name.get(name), dict) or not by_name[name].get("ready")
    )
    if unavailable:
        raise SmokeError(f"执行器未 ready: {', '.join(unavailable)}")
    report.passed("api-executors", f"执行器 ready: {', '.join(sorted(expected_executors))}")

    if not node_id:
        report.skipped("performance-node", "未指定 --node-id，跳过节点心跳与能力检查")
        return None
    deadline = time.monotonic() + max(0.0, node_ready_timeout)
    node: dict[str, Any] | None = None
    last_node_error = f"未找到性能节点 {node_id}"
    while True:
        nodes = client.request("GET", "/api/v1/performance/nodes")
        try:
            candidate = _find_node(nodes, node_id)
        except SmokeError as exc:
            last_node_error = str(exc)
        else:
            candidate_status = candidate.get("status")
            if candidate_status == "online":
                node = candidate
                break
            last_node_error = f"节点 {node_id} 当前状态为 {candidate_status}"

        if time.monotonic() >= deadline:
            raise SmokeError(last_node_error)
        time.sleep(max(0.2, node_poll_interval))

    assert node is not None
    if expected_queue and node.get("queue_name") != expected_queue:
        raise SmokeError(f"节点 {node_id} 队列为 {node.get('queue_name')}，期望 {expected_queue}")
    if expected_queue:
        report.passed("performance-node-queue", f"节点队列为 {expected_queue}")
    node_executors = _node_executors(node)
    missing = sorted(expected_executors - node_executors)
    if missing:
        raise SmokeError(f"节点 {node_id} 未声明执行器: {', '.join(missing)}")
    report.passed("performance-node", f"节点 {node_id} online，能力为 {', '.join(sorted(node_executors))}")

    if target is not None:
        allowlist = node.get("egress_allowlist")
        values = allowlist if isinstance(allowlist, list) else []
        if require_allowlist and not values:
            raise SmokeError(f"节点 {node_id} 未配置 egress allowlist")
        if values and not host_allowed(target.host, values):
            raise SmokeError(f"目标 {target.host} 不在节点 {node_id} 的 egress allowlist 中")
        report.passed("performance-node-allowlist", f"节点 allowlist 允许 {target.host}")
    return node


def check_kubernetes(
    report: CheckReport,
    *,
    context: str | None,
    namespace: str,
    deployment: str,
    pod_selector: str | None,
    container: str | None,
    verify_worker_image: bool,
    min_ready_nodes: int = 0,
    min_worker_replicas: int = 0,
    require_worker_resources: bool = False,
    timeout: float,
) -> None:
    prefix = ["kubectl"]
    if context:
        prefix.extend(["--context", context])
    prefix.extend(["-n", namespace])

    def run(command: list[str], *, command_timeout: float | None = None) -> str:
        try:
            result = subprocess.run(
                [*prefix, *command],
                capture_output=True,
                text=True,
                check=False,
                timeout=command_timeout or timeout,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise SmokeError(f"kubectl 执行失败: {_safe_error(exc)}") from exc
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            raise SmokeError(f"kubectl {' '.join(command)} 失败: {_safe_error(output)}")
        return output

    deployment_json = json.loads(run(["get", "deployment", deployment, "-o", "json"]))
    desired = int(deployment_json.get("spec", {}).get("replicas") or 0)
    available = int(deployment_json.get("status", {}).get("availableReplicas") or 0)
    if desired < 1 or available < desired:
        raise SmokeError(f"Deployment {deployment} 未 ready: available={available}, desired={desired}")
    run(["rollout", "status", f"deployment/{deployment}", f"--timeout={max(1, int(timeout))}s"])
    report.passed("kubernetes-rollout", f"Deployment {deployment} ready {available}/{desired}")

    if min_worker_replicas:
        if desired < min_worker_replicas or available < min_worker_replicas:
            raise SmokeError(
                f"Deployment {deployment} 副本不足: available={available}, desired={desired}, "
                f"required={min_worker_replicas}"
            )
        report.passed("kubernetes-replicas", f"Deployment {deployment} 副本满足 {available}/{min_worker_replicas}")

    if min_ready_nodes:
        nodes = json.loads(run(["get", "nodes", "-o", "json"]))
        items = nodes.get("items", []) if isinstance(nodes, dict) else []
        ready_nodes: list[str] = []
        for node in items:
            if not isinstance(node, dict):
                continue
            metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
            status = node.get("status") if isinstance(node.get("status"), dict) else {}
            conditions = status.get("conditions", [])
            ready = any(
                isinstance(condition, dict) and condition.get("type") == "Ready" and condition.get("status") == "True"
                for condition in conditions
            )
            spec = node.get("spec") if isinstance(node.get("spec"), dict) else {}
            if ready and spec.get("unschedulable") is not True:
                name = metadata.get("name")
                ready_nodes.append(str(name) if name else "<unnamed>")
        if len(ready_nodes) < min_ready_nodes:
            raise SmokeError(f"Kubernetes 可调度 Ready 节点不足: ready={len(ready_nodes)}, required={min_ready_nodes}")
        report.passed(
            "kubernetes-nodes",
            f"可调度 Ready 节点 {len(ready_nodes)}/{min_ready_nodes}: {', '.join(ready_nodes)}",
        )

    if require_worker_resources:
        template = deployment_json.get("spec", {}).get("template", {})
        pod_spec = template.get("spec", {}) if isinstance(template, dict) else {}
        containers = pod_spec.get("containers", []) if isinstance(pod_spec, dict) else []
        selected_container: dict[str, Any] | None = None
        for item in containers:
            if not isinstance(item, dict):
                continue
            if container and item.get("name") == container:
                selected_container = item
                break
            if not container and selected_container is None:
                selected_container = item
        if container and selected_container is None:
            raise SmokeError(f"Deployment {deployment} 未找到容器 {container}")
        resources = selected_container.get("resources") if isinstance(selected_container, dict) else None
        requests = resources.get("requests") if isinstance(resources, dict) else None
        limits = resources.get("limits") if isinstance(resources, dict) else None
        if not isinstance(requests, dict) or not isinstance(limits, dict):
            raise SmokeError(f"Deployment {deployment} 未配置 Worker resources.requests/limits")
        missing = [
            f"{section}.{key}"
            for section, values in (("requests", requests), ("limits", limits))
            for key in ("cpu", "memory")
            if not str(values.get(key, "")).strip()
        ]
        if missing:
            raise SmokeError(f"Deployment {deployment} Worker 资源配置缺少: {', '.join(missing)}")
        report.passed(
            "kubernetes-worker-resources",
            f"Worker resources.requests/limits 已配置 cpu、memory（容器={selected_container.get('name') if selected_container else 'unknown'}）",
        )

    if not pod_selector:
        labels = deployment_json.get("spec", {}).get("selector", {}).get("matchLabels", {})
        if isinstance(labels, dict):
            pod_selector = ",".join(f"{key}={value}" for key, value in labels.items())
    if not pod_selector:
        raise SmokeError("无法从 Deployment 推导 Pod selector，请显式传入 --pod-selector")
    pods = json.loads(run(["get", "pods", "-l", pod_selector, "-o", "json"]))
    items = pods.get("items", []) if isinstance(pods, dict) else []
    ready_pod = None
    for pod in items:
        status = pod.get("status", {}) if isinstance(pod, dict) else {}
        statuses = status.get("containerStatuses", [])
        if status.get("phase") == "Running" and statuses and all(item.get("ready") for item in statuses):
            ready_pod = pod
            break
    if not ready_pod:
        raise SmokeError(f"selector {pod_selector} 没有 Running 且 Ready 的 Pod")
    pod_name = ready_pod.get("metadata", {}).get("name")
    if not isinstance(pod_name, str) or not pod_name:
        raise SmokeError("Ready Pod 缺少名称")
    report.passed("kubernetes-pod", f"Pod {pod_name} Running/Ready")

    if not verify_worker_image:
        return
    exec_prefix = ["exec", pod_name]
    if container:
        exec_prefix.extend(["-c", container])
    dependency_code = "import grpc, grpc_tools, locust; print('python-dependencies-ok')"
    output = run([*exec_prefix, "--", "python", "-c", dependency_code])
    if "python-dependencies-ok" not in output:
        raise SmokeError("Worker 容器未确认 grpc/grpc_tools/locust 依赖")
    k6_output = run([*exec_prefix, "--", "k6", "version"])
    if "k6" not in k6_output.lower():
        raise SmokeError("Worker 容器未确认 k6 可执行文件")
    jmeter_output = run([*exec_prefix, "--", "jmeter", "--version"])
    if "jmeter" not in jmeter_output.lower():
        raise SmokeError("Worker 容器未确认 JMeter 可执行文件")
    browser_code = (
        "from playwright.sync_api import sync_playwright; "
        "p=sync_playwright().start(); "
        "print('chromium='+p.chromium.executable_path); "
        "print('firefox='+p.firefox.executable_path); "
        "print('webkit='+p.webkit.executable_path); p.stop()"
    )
    browser_output = run([*exec_prefix, "--", "python", "-c", browser_code])
    if not all(f"{name}=" in browser_output for name in ("chromium", "firefox", "webkit")):
        raise SmokeError("Worker 容器未确认 Chromium/Firefox/WebKit 浏览器")
    report.passed("kubernetes-worker-image", "Worker 容器包含 grpcio、Locust、k6、JMeter 和 Chromium/Firefox/WebKit")


def check_docker_worker(
    report: CheckReport,
    *,
    container: str | None,
    image: str | None,
    timeout: float,
) -> None:
    """Check a Linux Docker worker without relying on Kubernetes tooling."""

    def run(command: list[str]) -> str:
        try:
            result = subprocess.run(
                ["docker", *command],
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise SmokeError(f"docker 执行失败: {_safe_error(exc)}") from exc
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            raise SmokeError(f"docker {' '.join(command)} 失败: {_safe_error(output)}")
        return output

    def verify_runtime(exec_prefix: list[str], label: str) -> None:
        dependency_code = "import grpc, grpc_tools, locust; print('python-dependencies-ok')"
        output = run([*exec_prefix, "python", "-c", dependency_code])
        if "python-dependencies-ok" not in output:
            raise SmokeError(f"{label} 未确认 grpc/grpc_tools/locust 依赖")
        k6_output = run([*exec_prefix, "k6", "version"])
        if "k6" not in k6_output.lower():
            raise SmokeError(f"{label} 未确认 k6 可执行文件")
        jmeter_output = run([*exec_prefix, "jmeter", "--version"])
        if "jmeter" not in jmeter_output.lower():
            raise SmokeError(f"{label} 未确认 JMeter 可执行文件")
        browser_code = (
            "from playwright.sync_api import sync_playwright; "
            "p=sync_playwright().start(); "
            "print('chromium='+p.chromium.executable_path); "
            "print('firefox='+p.firefox.executable_path); "
            "print('webkit='+p.webkit.executable_path); p.stop()"
        )
        browser_output = run([*exec_prefix, "python", "-c", browser_code])
        if not all(f"{name}=" in browser_output for name in ("chromium", "firefox", "webkit")):
            raise SmokeError(f"{label} 未确认 Chromium/Firefox/WebKit 浏览器")

    if container:
        try:
            inspect = json.loads(run(["inspect", container]))
        except json.JSONDecodeError as exc:
            raise SmokeError(f"Docker 容器 inspect 返回格式无效: {container}") from exc
        if not isinstance(inspect, list) or not inspect or not isinstance(inspect[0], dict):
            raise SmokeError(f"Docker 容器不存在: {container}")
        state = inspect[0].get("State")
        if not isinstance(state, dict) or state.get("Status") != "running":
            status = state.get("Status") if isinstance(state, dict) else "unknown"
            raise SmokeError(f"Docker Worker 容器 {container} 状态为 {status}")
        report.passed("docker-worker", f"容器 {container} 正在运行")
        verify_runtime(["exec", container], f"容器 {container}")
        report.passed(
            "docker-worker-image", f"容器 {container} 包含 grpcio、Locust、k6、JMeter 和 Chromium/Firefox/WebKit"
        )

    if image:
        try:
            json.loads(run(["image", "inspect", image]))
        except json.JSONDecodeError as exc:
            raise SmokeError(f"Docker 镜像 inspect 返回格式无效: {image}") from exc
        report.passed("docker-image", f"镜像 {image} 已存在")
        dependency_code = "import grpc, grpc_tools, locust; print('python-dependencies-ok')"
        output = run(["run", "--rm", "--entrypoint", "python", image, "-c", dependency_code])
        if "python-dependencies-ok" not in output:
            raise SmokeError(f"镜像 {image} 未确认 grpc/grpc_tools/locust 依赖")
        k6_output = run(["run", "--rm", "--entrypoint", "k6", image, "version"])
        if "k6" not in k6_output.lower():
            raise SmokeError(f"镜像 {image} 未确认 k6 可执行文件")
        jmeter_output = run(["run", "--rm", "--entrypoint", "jmeter", image, "--version"])
        if "jmeter" not in jmeter_output.lower():
            raise SmokeError(f"镜像 {image} 未确认 JMeter 可执行文件")
        browser_code = (
            "from playwright.sync_api import sync_playwright; "
            "p=sync_playwright().start(); "
            "print('chromium='+p.chromium.executable_path); "
            "print('firefox='+p.firefox.executable_path); "
            "print('webkit='+p.webkit.executable_path); p.stop()"
        )
        browser_output = run(["run", "--rm", "--entrypoint", "python", image, "-c", browser_code])
        if not all(f"{name}=" in browser_output for name in ("chromium", "firefox", "webkit")):
            raise SmokeError(f"镜像 {image} 未确认 Chromium/Firefox/WebKit 浏览器")
        report.passed(
            "docker-image-dependencies", f"镜像 {image} 包含 grpcio、Locust、k6、JMeter 和 Chromium/Firefox/WebKit"
        )


def run_real_test(
    report: CheckReport,
    client: ApiClient,
    *,
    test_id: int,
    node_db_id: int | None,
    expected_executor: str | None,
    target: Target | None,
    require_tls: bool,
    timeout: float,
    poll_interval: float,
    require_metrics: bool,
    max_error_rate: float,
    label: str,
    idempotency_key: str | None = None,
    required_metric_sources: set[str] | None = None,
    require_baseline: bool = False,
    fail_on_baseline_regression: bool = False,
) -> int:
    test = client.request("GET", f"/api/v1/performance/tests/{test_id}")
    if not isinstance(test, dict):
        raise SmokeError(f"压测定义 {test_id} 返回格式无效")
    executor = str(test.get("executor", "")).lower()
    if expected_executor and executor != expected_executor:
        raise SmokeError(f"压测定义 {test_id} 使用 {executor}，期望 {expected_executor}")
    if target is not None:
        _assert_test_target_matches(test, target)
    if require_tls and executor == "grpc":
        options = test.get("default_options") if isinstance(test.get("default_options"), dict) else {}
        raw_target = str(options.get("target") or "")
        if not bool(options.get("use_tls")) and not raw_target.startswith(("grpcs://", "https://")):
            raise SmokeError(f"gRPC 压测定义 {test_id} 未启用 TLS")

    run = trigger_run(client, test_id, node_db_id=node_db_id, idempotency_key=idempotency_key)
    run_id = int(run["id"])
    final = wait_for_run(client, run_id, timeout=timeout, poll_interval=poll_interval)
    status = final.get("status")
    if status != "success":
        raise SmokeError(f"{label} run={run_id} 最终状态为 {status}: {_safe_error(final.get('error_message'))}")
    summary = final.get("summary") if isinstance(final.get("summary"), dict) else {}
    if summary.get("executor") != executor:
        raise SmokeError(f"{label} run={run_id} 摘要执行器为 {summary.get('executor')}，期望 {executor}")
    iterations = summary.get("iterations")
    error_rate = summary.get("error_rate")
    if not isinstance(iterations, (int, float)) or iterations <= 0:
        raise SmokeError(f"{label} run={run_id} 没有产生有效 iterations")
    if not isinstance(error_rate, (int, float)):
        raise SmokeError(f"{label} run={run_id} 摘要缺少数值 error_rate")
    if error_rate > max_error_rate:
        raise SmokeError(f"{label} run={run_id} error_rate={error_rate} 超过 {max_error_rate}")
    if require_metrics or required_metric_sources:
        metrics = client.request("GET", f"/api/v1/performance/runs/{run_id}/metrics?limit=2000")
        sources = validate_metric_samples(metrics, required_sources=required_metric_sources)
        report.passed("performance-metrics", f"run={run_id} samples={len(metrics)} sources={sources}")
    if require_baseline or fail_on_baseline_regression:
        comparison = client.request("GET", f"/api/v1/performance/runs/{run_id}/baseline-comparison")
        detail = validate_baseline_comparison(
            comparison,
            expected_run_id=run_id,
            fail_on_regression=fail_on_baseline_regression,
        )
        report.passed("performance-baseline", detail)
    report.passed(label, f"run={run_id} executor={executor} iterations={iterations} error_rate={error_rate}")
    return run_id


def cancel_real_test(
    report: CheckReport,
    client: ApiClient,
    *,
    test_id: int,
    node_db_id: int | None,
    wait_before_cancel: float,
    timeout: float,
    poll_interval: float,
    idempotency_key: str | None = None,
) -> int:
    run = trigger_run(client, test_id, node_db_id=node_db_id, idempotency_key=idempotency_key)
    run_id = int(run["id"])
    time.sleep(max(0.2, wait_before_cancel))
    client.request("POST", f"/api/v1/performance/runs/{run_id}/stop")
    final = wait_for_run(
        client,
        run_id,
        timeout=timeout,
        poll_interval=poll_interval,
        expect_cancelled=True,
    )
    report.passed("performance-cancel", f"run={run_id} 从运行态进入 cancelled")
    return int(final["id"])


def _run_check(report: CheckReport, name: str, callback: Callable[[], None]) -> None:
    try:
        callback()
    except (SmokeError, OSError, ValueError, json.JSONDecodeError) as exc:
        report.failed(name, _safe_error(exc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api-base-url", help="ATP API 根地址，例如 https://atp.example.test")
    parser.add_argument("--expected-executors", default="k6,locust,grpc,jmeter", help="逗号分隔的必需执行器")
    parser.add_argument("--node-id", help="性能节点的稳定 node_id，例如 worker-a")
    parser.add_argument("--expected-queue", help="要求节点登记的 Celery 队列名称")
    parser.add_argument("--target", help="目标 host:port 或 grpc(s)://host:port")
    parser.add_argument("--prometheus-url", help="Prometheus HTTP(S) 根地址；会检查 /-/ready 和 /api/v1/query")
    parser.add_argument("--prometheus-query", default="up", help="Prometheus readiness 后执行的 PromQL，默认 up")
    parser.add_argument("--require-tls", action="store_true", help="对目标执行证书校验，并要求 gRPC 测试启用 TLS")
    parser.add_argument("--ca-file", help="自定义 CA PEM 文件")
    parser.add_argument("--tls-server-name", help="TLS SNI/证书校验名称")
    parser.add_argument("--require-node-allowlist", action="store_true", help="要求节点配置非空且允许目标域名")
    parser.add_argument("--namespace", default="default", help="Kubernetes namespace")
    parser.add_argument("--deployment", help="Kubernetes performance worker Deployment 名称")
    parser.add_argument("--kube-context", help="Kubernetes context")
    parser.add_argument("--pod-selector", help="可选 Pod selector；默认从 Deployment 推导")
    parser.add_argument("--container", help="Worker Pod 容器名称")
    parser.add_argument(
        "--min-ready-nodes",
        type=int,
        default=0,
        help="要求 Kubernetes 至少有指定数量的可调度 Ready 节点；必须同时指定 --deployment",
    )
    parser.add_argument(
        "--min-worker-replicas",
        type=int,
        default=0,
        help="要求性能 Worker Deployment 至少有指定数量的 desired/available 副本",
    )
    parser.add_argument(
        "--require-worker-resources",
        action="store_true",
        help="要求性能 Worker Deployment 配置 requests/limits.cpu 和 memory",
    )
    parser.add_argument(
        "--verify-worker-image",
        action="store_true",
        help="kubectl exec 检查 grpc/Locust/k6/JMeter 和 Chromium/Firefox/WebKit 依赖",
    )
    parser.add_argument("--docker-container", help="Linux Docker Worker 容器名称")
    parser.add_argument("--docker-image", help="待验收的 Worker 镜像名称")
    parser.add_argument("--smoke-test-id", type=int, help="已有的真实性能测试定义 ID；显式传入才会产生压测流量")
    parser.add_argument("--smoke-executor", choices=("k6", "locust", "grpc", "jmeter"), help="限制 smoke 测试执行器")
    parser.add_argument("--cancel-test-id", type=int, help="已有的长时性能测试定义 ID，用于真实取消验收")
    parser.add_argument("--cancel-after-seconds", type=float, default=2.0)
    parser.add_argument(
        "--idempotency-key",
        default=os.environ.get("ATP_PERFORMANCE_IDEMPOTENCY_KEY"),
        help="验收触发幂等键基值；CI 可固定复用，本地未提供时每次生成新键",
    )
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument(
        "--node-ready-timeout-seconds",
        type=float,
        default=60.0,
        help="节点心跳注册后变为 online 的等待上限",
    )
    parser.add_argument("--request-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--require-metrics", action="store_true", help="要求真实 run 至少产生一条资源采样")
    parser.add_argument(
        "--require-metric-source",
        action="append",
        default=[],
        metavar="SOURCE",
        help="要求真实 run 至少有一条非空指标样本；可重复传入，例如 performance-worker 或 target-service-prometheus",
    )
    parser.add_argument("--require-baseline", action="store_true", help="要求真实 run 返回基线对比指标")
    parser.add_argument(
        "--fail-on-baseline-regression",
        action="store_true",
        help="基线对比出现任一核心指标 regression 时让验收失败（隐含 --require-baseline）",
    )
    parser.add_argument("--report", type=Path, help="输出 JSON 验收证据路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    selected = any(
        (
            args.api_base_url,
            args.target,
            args.prometheus_url,
            args.deployment,
            args.docker_container,
            args.docker_image,
            args.smoke_test_id,
            args.cancel_test_id,
        )
    )
    if not selected:
        parser.error("至少选择 --api-base-url、--target、--deployment、--smoke-test-id 或 --cancel-test-id 之一")
    if args.require_node_allowlist and (not args.node_id or not args.target):
        parser.error("--require-node-allowlist 必须同时指定 --node-id 和 --target")
    if args.prometheus_query != "up" and not args.prometheus_url:
        parser.error("--prometheus-query 必须同时指定 --prometheus-url")
    if (args.smoke_test_id or args.cancel_test_id) and not args.api_base_url:
        parser.error("真实压测验收需要 --api-base-url")
    if (args.smoke_test_id or args.cancel_test_id) and not args.node_id:
        parser.error("真实专用 Worker 压测验收必须指定 --node-id")
    if (args.smoke_test_id or args.cancel_test_id) and not args.target:
        parser.error("真实压测验收必须指定 --target，以验证目标连通性和 allowlist")
    if args.verify_worker_image and not args.deployment:
        parser.error("--verify-worker-image 必须同时指定 --deployment")
    if (args.min_ready_nodes or args.min_worker_replicas or args.require_worker_resources) and not args.deployment:
        parser.error("--min-ready-nodes/--min-worker-replicas/--require-worker-resources 必须同时指定 --deployment")
    if args.min_ready_nodes < 0 or args.min_worker_replicas < 0:
        parser.error("--min-ready-nodes 和 --min-worker-replicas 不能为负数")
    if args.docker_image and args.verify_worker_image:
        parser.error("Docker 镜像会自动执行依赖检查，不需要 --verify-worker-image")
    if args.max_error_rate < 0 or args.max_error_rate > 1:
        parser.error("--max-error-rate 必须在 0 到 1 之间")
    if args.fail_on_baseline_regression:
        args.require_baseline = True
    if args.require_baseline and not args.smoke_test_id:
        parser.error("--require-baseline/--fail-on-baseline-regression 必须同时指定 --smoke-test-id")
    if args.node_ready_timeout_seconds < 0:
        parser.error("--node-ready-timeout-seconds 不能为负数")

    report = CheckReport()
    target: Target | None = None
    target_ready = not bool(args.target)
    if args.target:
        try:
            target = parse_target(args.target, require_tls=args.require_tls, server_name=args.tls_server_name)
            detail = check_target(target, timeout=args.request_timeout_seconds, ca_file=args.ca_file)
            report.passed("target-connectivity", detail)
            target_ready = True
        except (SmokeError, OSError, ValueError) as exc:
            report.failed("target-connectivity", _safe_error(exc))

    if args.prometheus_url:
        _run_check(
            report,
            "prometheus",
            lambda: check_prometheus(
                report,
                base_url=args.prometheus_url,
                query=args.prometheus_query,
                timeout=args.request_timeout_seconds,
            ),
        )

    client: ApiClient | None = None
    api_ready = False
    node: dict[str, Any] | None = None
    if args.api_base_url:
        try:
            token = os.environ.get("ATP_TOKEN")
            client = (
                ApiClient(args.api_base_url, token=token, timeout=args.request_timeout_seconds)
                if token
                else login_from_environment(args.api_base_url, timeout=args.request_timeout_seconds)
            )
            expected = {item.strip().lower() for item in args.expected_executors.split(",") if item.strip()}
            if not expected:
                raise SmokeError("--expected-executors 不能为空")
            node = check_api_and_node(
                report,
                client,
                expected_executors=expected,
                node_id=args.node_id,
                expected_queue=args.expected_queue,
                target=target,
                require_allowlist=args.require_node_allowlist,
                node_ready_timeout=args.node_ready_timeout_seconds,
                node_poll_interval=args.poll_interval_seconds,
            )
            api_ready = not args.target or target_ready
        except (SmokeError, OSError, ValueError) as exc:
            report.failed("api-and-node", _safe_error(exc))

    if args.deployment:
        _run_check(
            report,
            "kubernetes",
            lambda: check_kubernetes(
                report,
                context=args.kube_context,
                namespace=args.namespace,
                deployment=args.deployment,
                pod_selector=args.pod_selector,
                container=args.container,
                verify_worker_image=args.verify_worker_image,
                min_ready_nodes=args.min_ready_nodes,
                min_worker_replicas=args.min_worker_replicas,
                require_worker_resources=args.require_worker_resources,
                timeout=args.request_timeout_seconds,
            ),
        )

    if args.docker_container or args.docker_image:
        _run_check(
            report,
            "docker",
            lambda: check_docker_worker(
                report,
                container=args.docker_container,
                image=args.docker_image,
                timeout=args.request_timeout_seconds,
            ),
        )

    node_db_id = node.get("id") if isinstance(node, dict) and isinstance(node.get("id"), int) else None
    if (args.smoke_test_id or args.cancel_test_id) and not api_ready:
        report.failed("performance-runs", "API/节点验收未完成，跳过真实压测")
    elif args.smoke_test_id and client is not None:
        _run_check(
            report,
            "performance-smoke",
            lambda: run_real_test(
                report,
                client,
                test_id=args.smoke_test_id,
                node_db_id=node_db_id,
                expected_executor=args.smoke_executor,
                target=target,
                require_tls=args.require_tls,
                timeout=args.timeout_seconds,
                poll_interval=args.poll_interval_seconds,
                require_metrics=args.require_metrics,
                max_error_rate=args.max_error_rate,
                label="performance-smoke",
                idempotency_key=default_idempotency_key("smoke", args.smoke_test_id, args.idempotency_key),
                required_metric_sources=set(args.require_metric_source),
                require_baseline=args.require_baseline,
                fail_on_baseline_regression=args.fail_on_baseline_regression,
            ),
        )
    if args.cancel_test_id and client is not None and api_ready:
        _run_check(
            report,
            "performance-cancel",
            lambda: cancel_real_test(
                report,
                client,
                test_id=args.cancel_test_id,
                node_db_id=node_db_id,
                wait_before_cancel=args.cancel_after_seconds,
                timeout=args.timeout_seconds,
                poll_interval=args.poll_interval_seconds,
                idempotency_key=default_idempotency_key("cancel", args.cancel_test_id, args.idempotency_key),
            ),
        )

    if args.report:
        try:
            report.write(args.report, args=args)
            print(f"[PASS] evidence-report: {args.report}")
        except OSError as exc:
            report.failed("evidence-report", _safe_error(exc))

    return 1 if report.has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
