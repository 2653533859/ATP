"""Unit tests for P3.1 Kubernetes Dynamic Performance Shard Operator.

Tests:
1. build_k8s_performance_job generates compliant batch/v1 Job manifests
2. dispatch_k8s_performance_shards splits load options and creates multi-shard manifests
3. Label propagation, environment variables, resource limits, and auto-cleanup TTL
4. extract_shard_job_names extraction
"""

from __future__ import annotations

import json

from app.services.k8s_performance_operator import (
    DEFAULT_JOB_TTL_SECONDS,
    DEFAULT_K8S_NAMESPACE,
    DEFAULT_PERF_IMAGE,
    build_k8s_performance_job,
    dispatch_k8s_performance_shards,
    extract_shard_job_names,
)


def test_build_k8s_performance_job_manifest():
    shard_options = {"vus": 5, "duration": "30s"}
    job = build_k8s_performance_job(
        run_id=101,
        shard_index=1,
        total_shards=3,
        shard_options=shard_options,
        executor="k6",
        script_object_name="scripts/load_test.js",
        namespace="atp-production",
        image="registry.local/atp/worker:v2.5.0",
    )

    assert job["apiVersion"] == "batch/v1"
    assert job["kind"] == "Job"
    assert job["metadata"]["name"] == "atp-perf-shard-101-1"
    assert job["metadata"]["namespace"] == "atp-production"

    labels = job["metadata"]["labels"]
    assert labels["app.kubernetes.io/component"] == "performance-shard"
    assert labels["atp.run/id"] == "101"
    assert labels["atp.shard/index"] == "1"
    assert labels["atp.shard/total"] == "3"
    assert labels["atp.executor"] == "k6"

    spec = job["spec"]
    assert spec["backoffLimit"] == 0
    assert spec["ttlSecondsAfterFinished"] == DEFAULT_JOB_TTL_SECONDS

    pod_spec = spec["template"]["spec"]
    assert pod_spec["restartPolicy"] == "Never"

    container = pod_spec["containers"][0]
    assert container["image"] == "registry.local/atp/worker:v2.5.0"
    assert container["imagePullPolicy"] == "Never"

    env_map = {item["name"]: item["value"] for item in container["env"]}
    assert env_map["ATP_RUN_ID"] == "101"
    assert env_map["ATP_SHARD_INDEX"] == "1"
    assert env_map["ATP_SHARD_COUNT"] == "3"
    assert env_map["ATP_EXECUTOR"] == "k6"
    assert env_map["ATP_SCRIPT_OBJECT"] == "scripts/load_test.js"
    assert json.loads(env_map["ATP_OPTIONS_JSON"]) == shard_options

    resources = container["resources"]
    assert resources["limits"]["memory"] == "1Gi"
    assert resources["requests"]["cpu"] == "200m"


def test_dispatch_k8s_performance_shards_multi_node_split():
    aggregate_options = {"vus": 20, "duration": "60s"}
    manifests = dispatch_k8s_performance_shards(
        run_id=200,
        aggregate_options=aggregate_options,
        shard_count=4,
        executor="locust",
        script_object_name="locustfile.py",
    )

    assert len(manifests) == 4
    job_names = extract_shard_job_names(manifests)
    assert job_names == [
        "atp-perf-shard-200-0",
        "atp-perf-shard-200-1",
        "atp-perf-shard-200-2",
        "atp-perf-shard-200-3",
    ]

    total_vus_dispatched = 0
    for idx, m in enumerate(manifests):
        container = m["spec"]["template"]["spec"]["containers"][0]
        env_map = {item["name"]: item["value"] for item in container["env"]}
        opts = json.loads(env_map["ATP_OPTIONS_JSON"])
        assert opts["__shard_index"] == idx
        assert opts["__shard_count"] == 4
        total_vus_dispatched += opts["vus"]

    # 20 VUs split into 4 shards = 5 VUs per shard
    assert total_vus_dispatched == 20


def test_dispatch_k8s_performance_shards_single_shard():
    opts = {"vus": 8, "duration": "10s"}
    manifests = dispatch_k8s_performance_shards(
        run_id=300,
        aggregate_options=opts,
        shard_count=1,
        executor="k6",
    )

    assert len(manifests) == 1
    m = manifests[0]
    assert m["metadata"]["name"] == "atp-perf-shard-300-0"
    assert m["metadata"]["namespace"] == DEFAULT_K8S_NAMESPACE
    container = m["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == DEFAULT_PERF_IMAGE
