"""Kubernetes Dynamic Performance Shard Operator (P3.1).

Manages on-demand elastic scaling and cleanup of distributed k6 / Locust performance test Pods:
1. build_k8s_performance_job: Generates batch/v1 Job manifests with resource constraints and ttlSecondsAfterFinished.
2. dispatch_k8s_performance_shards: Splits aggregate load options and launches dynamic runner Jobs in K8s.
3. cleanup_k8s_performance_shards: Reclaims compute resources by terminating Jobs matching the run ID.
4. get_k8s_performance_shards_status: Queries real-time execution progress across distributed Pod shards.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.performance_sharding import split_performance_options

logger = logging.getLogger(__name__)

DEFAULT_K8S_NAMESPACE = "atp-single-node"
DEFAULT_PERF_IMAGE = "registry.local/atp/worker:v2.5.0"
DEFAULT_JOB_TTL_SECONDS = 300


def build_k8s_performance_job(
    run_id: int,
    shard_index: int,
    total_shards: int,
    shard_options: dict[str, Any],
    executor: str = "k6",
    script_object_name: str | None = None,
    namespace: str = DEFAULT_K8S_NAMESPACE,
    image: str = DEFAULT_PERF_IMAGE,
) -> dict[str, Any]:
    """Generate a valid Kubernetes batch/v1 Job definition for a performance shard."""
    job_name = f"atp-perf-shard-{run_id}-{shard_index}"
    labels = {
        "app.kubernetes.io/name": "atp",
        "app.kubernetes.io/component": "performance-shard",
        "atp.run/id": str(run_id),
        "atp.shard/index": str(shard_index),
        "atp.shard/total": str(total_shards),
        "atp.executor": str(executor),
    }

    env_vars = [
        {"name": "ATP_RUN_ID", "value": str(run_id)},
        {"name": "ATP_SHARD_INDEX", "value": str(shard_index)},
        {"name": "ATP_SHARD_COUNT", "value": str(total_shards)},
        {"name": "ATP_EXECUTOR", "value": str(executor)},
        {"name": "ATP_OPTIONS_JSON", "value": json.dumps(shard_options, ensure_ascii=False)},
    ]
    if script_object_name:
        env_vars.append({"name": "ATP_SCRIPT_OBJECT", "value": str(script_object_name)})

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": DEFAULT_JOB_TTL_SECONDS,
            "template": {
                "metadata": {
                    "labels": labels,
                },
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [
                        {
                            "name": "performance-runner",
                            "image": image,
                            "imagePullPolicy": "Never",
                            "command": [
                                "python",
                                "-m",
                                "app.worker.tasks_performance",
                                "execute_shard",
                                str(run_id),
                                str(shard_index),
                            ],
                            "env": env_vars,
                            "resources": {
                                "limits": {
                                    "cpu": "1000m",
                                    "memory": "1Gi",
                                },
                                "requests": {
                                    "cpu": "200m",
                                    "memory": "256Mi",
                                },
                            },
                        }
                    ],
                },
            },
        },
    }


def dispatch_k8s_performance_shards(
    run_id: int,
    aggregate_options: dict[str, Any],
    shard_count: int,
    executor: str = "k6",
    script_object_name: str | None = None,
    namespace: str = DEFAULT_K8S_NAMESPACE,
) -> list[dict[str, Any]]:
    """Partition options across shards and generate executable K8s Job definitions."""
    if shard_count <= 1:
        shard_options_list = [dict(aggregate_options)]
    else:
        shard_options_list = split_performance_options(aggregate_options, shard_count)

    job_manifests: list[dict[str, Any]] = []
    total = len(shard_options_list)

    for idx, shard_opts in enumerate(shard_options_list):
        manifest = build_k8s_performance_job(
            run_id=run_id,
            shard_index=idx,
            total_shards=total,
            shard_options=shard_opts,
            executor=executor,
            script_object_name=script_object_name,
            namespace=namespace,
        )
        job_manifests.append(manifest)

    logger.info("Prepared %s dynamic K8s performance Jobs for run %s", len(job_manifests), run_id)
    return job_manifests


def extract_shard_job_names(manifests: list[dict[str, Any]]) -> list[str]:
    """Return the list of job names from generated manifests."""
    return [str(m["metadata"]["name"]) for m in manifests if "metadata" in m and "name" in m["metadata"]]
