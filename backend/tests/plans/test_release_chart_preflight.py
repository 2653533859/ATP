"""The release preflight must reject stale Flower charts and unreviewed changes."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "validate-deployment-readiness.py"


def _module():
    spec = importlib.util.spec_from_file_location("deployment_readiness_preflight", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _flower(*, bounded: bool = True, safe_strategy: bool = True) -> dict:
    spec = {
        "replicas": 1,
        "template": {
            "spec": {
                "hostNetwork": True,
                "containers": [
                    {
                        "name": "flower",
                        "image": "registry.local/atp/worker:fixed",
                        "args": [
                            "--max_tasks=1000",
                            "--max_workers=100",
                            "--purge_offline_workers=300",
                        ]
                        if bounded
                        else [],
                        "resources": {"limits": {"memory": "512Mi"}},
                    }
                ],
            }
        },
        "strategy": {"type": "Recreate"} if safe_strategy else {"type": "RollingUpdate"},
    }
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "atp-single-node-atp-flower",
            "labels": {"app.kubernetes.io/component": "flower"},
        },
        "spec": spec,
    }


def test_flower_manifest_rejects_default_retention_and_unsafe_host_rollout():
    module = _module()
    identity = "Deployment/atp-single-node-atp-flower"

    assert module._check_flower_manifest({identity: _flower()}) == []
    assert "--max_tasks" in " ".join(module._check_flower_manifest({identity: _flower(bounded=False)}))
    assert "port 5555" in " ".join(module._check_flower_manifest({identity: _flower(safe_strategy=False)}))
    flower = _flower()
    flower["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]["memory"] = "256Mi"
    assert "512Mi" in " ".join(module._check_flower_manifest({identity: flower}))


def test_chart_fingerprint_rejects_stale_staged_file(tmp_path):
    module = _module()
    source = tmp_path / "source"
    staged = tmp_path / "staged"
    source.mkdir()
    staged.mkdir()
    (source / "values.yaml").write_text("flower: bounded\n", encoding="utf-8")
    (staged / "values.yaml").write_text("flower: default\n", encoding="utf-8")
    assert module._chart_fingerprint(source) != module._chart_fingerprint(staged)


def test_image_tag_overrides_accept_only_unique_immutable_tags():
    module = _module()
    assert module._image_tag_overrides(["backend=ab12cd34", "worker=ef56gh78"]) == {
        "backend": "ab12cd34",
        "worker": "ef56gh78",
    }
    for invalid in (["backend=latest"], ["backend=latest,secret=x"], ["other=ab12"], ["backend=a", "backend=b"]):
        with pytest.raises(ValueError):
            module._image_tag_overrides(invalid)


def test_release_preflight_requires_explicit_resource_and_migration_review(monkeypatch):
    module = _module()
    identity = "Deployment/atp-single-node-atp-flower"
    hook_id = "Job/atp-single-node-atp-migrate"
    old = _flower(bounded=False)
    new = _flower()
    hook_old = {"apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": hook_id.split("/", 1)[1]}}
    hook_new = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": hook_id.split("/", 1)[1], "annotations": {"helm.sh/hook": "pre-upgrade"}},
    }
    secret_old = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "runtime"},
        "data": {"password": "sensitive-before"},
    }
    secret_new = {
        **secret_old,
        "data": {"password": "sensitive-after"},
    }

    rendered_commands = []

    def fake_capture(command, *, input_text=None):
        if command[1:3] == ["get", "values"]:
            return "{}\n"
        if command[1:3] == ["get", "manifest"]:
            return yaml.safe_dump_all([old, secret_old])
        if command[1:3] == ["get", "hooks"]:
            return yaml.safe_dump(hook_old)
        assert command[1] == "template" and input_text == "{}\n"
        rendered_commands.append(command)
        return yaml.safe_dump_all([new, secret_new, hook_new])

    monkeypatch.setattr(module, "_helm_capture", fake_capture)
    monkeypatch.setattr(module.shutil, "which", lambda _name: "/usr/bin/helm")
    chart = module.ROOT / "deploy" / "helm" / "atp"
    failures, report = module._check_release_chart(
        release="atp-single-node",
        namespace="atp-single-node",
        chart=chart,
        allowed_changes=set(),
        allowed_hooks=set(),
        skip_hooks=False,
    )
    assert "unreviewed resource change: " + identity in failures
    assert "unreviewed resource change: Secret/runtime" in failures
    assert "unreviewed migration hook change: " + hook_id in failures
    assert all("sensitive-" not in line for line in failures + report)

    failures, _ = module._check_release_chart(
        release="atp-single-node",
        namespace="atp-single-node",
        chart=chart,
        allowed_changes={identity, "Secret/runtime"},
        allowed_hooks={hook_id},
        skip_hooks=False,
        image_tags={"backend": "newtag"},
    )
    assert failures == []
    assert rendered_commands[-1][-2:] == ["--set-string", "image.backend.tag=newtag"]
