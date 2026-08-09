"""Performance executor capabilities and dispatch contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from collections.abc import Mapping

from app.core.config import settings


class PerformanceExecutorError(ValueError):
    """Raised when a performance executor is unknown or unavailable."""


@dataclass(frozen=True)
class PerformanceExecutorCapability:
    name: str
    label: str
    ready: bool
    script_extensions: tuple[str, ...]
    supports_visual: bool
    supports_dataset: bool
    supports_http: bool
    supports_grpc: bool
    description: str

    def public_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["script_extensions"] = list(self.script_extensions)
        return value


_CAPABILITIES: dict[str, PerformanceExecutorCapability] = {
    "k6": PerformanceExecutorCapability(
        name="k6",
        label="k6",
        ready=True,
        script_extensions=(".js", ".mjs"),
        supports_visual=True,
        supports_dataset=True,
        supports_http=True,
        supports_grpc=False,
        description="JavaScript HTTP 压测，支持阈值、数据集和可视化场景。",
    ),
    "locust": PerformanceExecutorCapability(
        name="locust",
        label="Locust",
        ready=True,
        script_extensions=(".py",),
        supports_visual=False,
        supports_dataset=True,
        supports_http=True,
        supports_grpc=False,
        description="Python HTTP 压测，适合复杂用户行为和自定义编排。",
    ),
    "grpc": PerformanceExecutorCapability(
        name="grpc",
        label="gRPC",
        ready=True,
        script_extensions=(".proto",),
        supports_visual=False,
        supports_dataset=False,
        supports_http=False,
        supports_grpc=True,
        description="Proto/TLS/Metadata/Streaming 压测，支持并发、取消和统一结果摘要。",
    ),
    "jmeter": PerformanceExecutorCapability(
        name="jmeter",
        label="JMeter",
        ready=True,
        script_extensions=(".jmx",),
        supports_visual=False,
        supports_dataset=False,
        supports_http=True,
        supports_grpc=False,
        description="JMX 非 GUI 压测，解析 JTL 并统一输出吞吐、百分位和错误率。",
    ),
}


def list_executor_capabilities(*, include_unready: bool = True) -> list[PerformanceExecutorCapability]:
    values = list(_CAPABILITIES.values())
    if include_unready:
        return values
    return [item for item in values if item.ready]


def get_executor_capability(name: str) -> PerformanceExecutorCapability:
    normalized = str(name or "").strip().lower()
    capability = _CAPABILITIES.get(normalized)
    if capability is None:
        raise PerformanceExecutorError(f"不支持的性能执行器: {name}")
    return capability


def ensure_ready_executor(name: str) -> PerformanceExecutorCapability:
    capability = get_executor_capability(name)
    if not capability.ready:
        raise PerformanceExecutorError(f"性能执行器 {capability.label} 尚未启用")
    return capability


def configured_performance_executors() -> list[str]:
    """Return executors this worker advertises in its heartbeat."""
    configured = [item.strip().lower() for item in settings.PERFORMANCE_EXECUTORS.split(",") if item.strip()]
    return [name for name in configured if name in _CAPABILITIES and _CAPABILITIES[name].ready] or ["k6"]


def node_supports_executor(node: object, executor: str) -> bool:
    """Check a registered node capability without breaking old k6 nodes."""
    capabilities = getattr(node, "capabilities", None)
    if not isinstance(capabilities, Mapping):
        return executor == "k6"
    declared = capabilities.get("executors")
    if isinstance(declared, str):
        declared_values = {item.strip().lower() for item in declared.split(",") if item.strip()}
    elif isinstance(declared, (list, tuple, set)):
        declared_values = {str(item).strip().lower() for item in declared if str(item).strip()}
    else:
        legacy = capabilities.get("executor")
        declared_values = {str(legacy).strip().lower()} if legacy else set()
    return executor.lower() in declared_values if declared_values else executor.lower() == "k6"


def run_performance_executor(*, executor: str, **kwargs):
    """Dispatch through the shared executor contract."""
    capability = ensure_ready_executor(executor)
    if capability.name == "k6":
        from app.services.performance import run_k6_script

        return run_k6_script(**kwargs)
    if capability.name == "locust":
        from app.services.performance_locust import run_locust_script

        return run_locust_script(**kwargs)
    if capability.name == "grpc":
        from app.services.performance_grpc import run_grpc_script

        return run_grpc_script(**kwargs)
    if capability.name == "jmeter":
        from app.services.performance_jmeter import run_jmeter_script

        return run_jmeter_script(**kwargs)
    raise PerformanceExecutorError(f"性能执行器 {executor} 尚未实现")
