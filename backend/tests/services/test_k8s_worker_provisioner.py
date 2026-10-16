"""Unit tests for D1.1 K8s Worker Provisioner Service."""

from datetime import datetime, timedelta, timezone
import pytest

from app.services.k8s_worker_provisioner import (
    ContainerRuntime,
    PodStatus,
    ResourceQuota,
    append_pod_logs,
    get_worker_pod,
    list_worker_pods,
    provision_worker_pod,
    reap_stale_worker_pods,
    reset_worker_pods_registry,
    terminate_worker_pod,
)


@pytest.fixture(autouse=True)
def clean_registry():
    reset_worker_pods_registry()
    yield
    reset_worker_pods_registry()


def test_provision_worker_pod_success():
    quota = ResourceQuota(
        cpu_limit_cores=4.0,
        memory_limit_mb=4096,
        cpu_request_cores=1.0,
        memory_request_mb=1024,
    )
    pod = provision_worker_pod(
        worker_name="k8s-worker-prod-01",
        image="atp/worker-python:3.12-v1",
        assigned_queue="performance",
        resource_quota=quota,
        runtime=ContainerRuntime.KUBERNETES,
        metadata={"region": "ap-southeast-1"},
    )

    assert pod.pod_id.startswith("pod_worker_")
    assert pod.worker_name == "k8s-worker-prod-01"
    assert pod.image == "atp/worker-python:3.12-v1"
    assert pod.status == PodStatus.RUNNING
    assert pod.assigned_queue == "performance"
    assert pod.resource_quota.cpu_limit_cores == 4.0
    assert pod.metadata["region"] == "ap-southeast-1"
    assert len(pod.logs) >= 2


def test_resource_quota_validation_failures():
    # CPU 超限
    with pytest.raises(ValueError, match="CPU 配额限制"):
        ResourceQuota(cpu_limit_cores=32.0).validate()

    # 内存超限
    with pytest.raises(ValueError, match="内存配额限制"):
        ResourceQuota(memory_limit_mb=65536).validate()

    # Request > Limit
    with pytest.raises(ValueError, match="CPU Request 不能大于 CPU Limit"):
        ResourceQuota(cpu_limit_cores=2.0, cpu_request_cores=4.0).validate()

    with pytest.raises(ValueError, match="Memory Request 不能大于 Memory Limit"):
        ResourceQuota(memory_limit_mb=1024, memory_request_mb=2048).validate()


def test_terminate_worker_pod_lifecycle():
    pod = provision_worker_pod(worker_name="k8s-worker-term-test")
    assert pod.status == PodStatus.RUNNING

    # 优雅下线
    terminated = terminate_worker_pod(pod.pod_id, exit_code=0)
    assert terminated.status == PodStatus.TERMINATED
    assert terminated.exit_code == 0
    assert terminated.terminated_at is not None

    # 不存在的 Pod 下线报错
    with pytest.raises(ValueError, match="Worker Pod 不存在"):
        terminate_worker_pod("non_existent_pod_999")


def test_append_pod_logs_and_list_filter():
    pod1 = provision_worker_pod(worker_name="worker-alpha", assigned_queue="default")
    pod2 = provision_worker_pod(worker_name="worker-beta", assigned_queue="api")
    assert pod2.pod_id.startswith("pod_worker_")

    append_pod_logs(pod1.pod_id, "Executing test scenario step 1: Login")
    append_pod_logs(pod1.pod_id, "Step 1 completed in 120ms")

    fetched = get_worker_pod(pod1.pod_id)
    assert fetched is not None
    assert any("Executing test scenario step 1" in line for line in fetched.logs)

    # 队列筛选
    default_pods = list_worker_pods(assigned_queue="default")
    assert len(default_pods) == 1
    assert default_pods[0].worker_name == "worker-alpha"

    api_pods = list_worker_pods(assigned_queue="api")
    assert len(api_pods) == 1
    assert api_pods[0].worker_name == "worker-beta"


def test_reap_stale_worker_pods():
    pod = provision_worker_pod(worker_name="stale-worker")
    # 模拟超时的创建时间 (2 小时前)
    pod.created_at = datetime.now(timezone.utc) - timedelta(seconds=7200)

    reaped_ids = reap_stale_worker_pods(max_lifetime_sec=3600.0)
    assert pod.pod_id in reaped_ids

    reaped_pod = get_worker_pod(pod.pod_id)
    assert reaped_pod is not None
    assert reaped_pod.status == PodStatus.TERMINATED
    assert reaped_pod.exit_code == 137
