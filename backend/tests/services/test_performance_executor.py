from types import SimpleNamespace

from app.services.performance_executor import (
    get_executor_capability,
    list_executor_capabilities,
    node_supports_executor,
)


def test_capability_matrix_exposes_ready_executors():
    capabilities = {item.name: item for item in list_executor_capabilities()}

    assert capabilities["k6"].ready is True
    assert capabilities["k6"].supports_visual is True
    assert capabilities["locust"].ready is True
    assert capabilities["locust"].script_extensions == (".py",)
    assert capabilities["grpc"].ready is True
    assert capabilities["grpc"].script_extensions == (".proto",)


def test_grpc_executor_can_be_selected_for_a_run():
    from app.services.performance_executor import ensure_ready_executor

    assert ensure_ready_executor("grpc").name == "grpc"

    assert get_executor_capability("LOCUST").name == "locust"


def test_node_capabilities_support_legacy_and_multi_executor_shapes():
    assert node_supports_executor(SimpleNamespace(capabilities={"executor": "k6"}), "k6") is True
    assert node_supports_executor(SimpleNamespace(capabilities={"executor": "k6"}), "locust") is False
    assert node_supports_executor(SimpleNamespace(capabilities={"executors": ["k6", "locust"]}), "locust") is True
    assert node_supports_executor(SimpleNamespace(capabilities={}), "locust") is False
