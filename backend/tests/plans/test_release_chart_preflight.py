"""The release preflight must reject stale Flower charts and unreviewed changes."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
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


def test_worker_image_override_changes_only_ordinary_worker_manifest():
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("helm is not installed")
    module = _module()
    chart = ROOT / "deploy" / "helm" / "atp"
    overlay = chart / "values-performance-single-node.example.yaml"
    command = [helm, "template", "atp-single-node", str(chart), "-f", str(overlay)]
    baseline = module._manifest_index(
        subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8").stdout
    )
    candidate = module._manifest_index(
        subprocess.run(
            [*command, "--set-string", "worker.imageTag=b1828220"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout
    )

    assert [(status, identity) for status, identity, *_ in module._changes(baseline, candidate)] == [
        ("changed", "Deployment/atp-single-node-atp-worker")
    ]
    assert module._image_tags(candidate["Deployment/atp-single-node-atp-worker"]) == (("worker", "b1828220"),)


def test_rev56_hotfix_chart_worker_override_changes_only_ordinary_worker_manifest():
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("helm is not installed")
    module = _module()
    chart = ROOT / "deploy" / "helm" / "atp-rev56-hotfix"
    overlay = chart / "values-performance-single-node.example.yaml"
    command = [helm, "template", "atp-single-node", str(chart), "-f", str(overlay)]
    baseline = module._manifest_index(
        subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8").stdout
    )
    candidate = module._manifest_index(
        subprocess.run(
            [*command, "--set-string", "worker.imageTag=6755ed9f-runmetrics-b1828220"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout
    )

    assert [(status, identity) for status, identity, *_ in module._changes(baseline, candidate)] == [
        ("changed", "Deployment/atp-single-node-atp-worker")
    ]
    worker = candidate["Deployment/atp-single-node-atp-worker"]
    assert module._changed_paths(baseline["Deployment/atp-single-node-atp-worker"], worker) == [
        "spec.template.spec.containers[0].image"
    ]
    assert module._image_tags(worker) == (("worker", "6755ed9f-runmetrics-b1828220"),)


@pytest.mark.parametrize("chart_name", ["atp", "atp-rev57-heartbeat-hotfix"])
def test_performance_worker_image_override_changes_only_performance_deployment(chart_name):
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("helm is not installed")
    module = _module()
    chart = ROOT / "deploy" / "helm" / chart_name
    overlay = chart / "values-performance-single-node.example.yaml"
    command = [helm, "template", "atp-single-node", str(chart), "-f", str(overlay)]
    baseline = module._manifest_index(
        subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8").stdout
    )
    candidate = module._manifest_index(
        subprocess.run(
            [*command, "--set-string", "performanceWorker.imageTag=heartbeat-fixed"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout
    )

    identity = "Deployment/atp-single-node-atp-performance-worker"
    assert [(status, name) for status, name, *_ in module._changes(baseline, candidate)] == [("changed", identity)]
    assert module._changed_paths(baseline[identity], candidate[identity]) == ["spec.template.spec.containers[0].image"]
    assert module._image_tags(candidate[identity]) == (("performance-worker", "heartbeat-fixed"),)


def test_rev57_hotfix_chart_uses_unique_performance_worker_hostname():
    chart = ROOT / "deploy" / "helm" / "atp-rev57-heartbeat-hotfix"
    template = (chart / "templates" / "performance-worker-deployment.yaml").read_text(encoding="utf-8")
    assert '--hostname="performance@${POD_NAMESPACE}.${POD_NAME}"' in template
    assert "fieldPath: metadata.name" in template
    assert "fieldPath: metadata.namespace" in template


def test_repository_chart_source_must_stay_inside_deploy_helm(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    source = tmp_path / "deploy" / "helm" / "rev56"
    source.mkdir(parents=True)
    (source / "Chart.yaml").write_text("name: atp\nversion: 0.1.0\n", encoding="utf-8")
    assert module._repository_chart(Path("deploy/helm/rev56")) == source
    with pytest.raises(ValueError, match="deploy/helm"):
        module._repository_chart(tmp_path / "outside")
    (source / "Chart.yaml").unlink()
    with pytest.raises(ValueError, match="Chart directory"):
        module._repository_chart(source)


def test_image_only_rejects_non_image_fields_and_added_resources():
    module = _module()
    old = _flower()
    new = yaml.safe_load(yaml.safe_dump(old))
    new["spec"]["template"]["spec"]["containers"][0]["image"] = "registry.local/atp/worker:new"
    assert module._is_image_only_change(old, new)
    new["spec"]["template"]["metadata"] = {"annotations": {"checksum/config": "new"}}
    assert not module._is_image_only_change(old, new)
    assert not module._is_image_only_change(None, new)
    assert not module._is_image_only_change(old, None)


def test_release_preflight_snapshot_baseline_and_image_only(monkeypatch, tmp_path):
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    source = tmp_path / "deploy" / "helm" / "atp-rev56-hotfix"
    source.mkdir(parents=True)
    (source / "Chart.yaml").write_text("name: atp\nversion: 0.1.0\n", encoding="utf-8")
    staged = tmp_path / "staged"
    shutil.copytree(source, staged)
    worker_id = "Deployment/atp-single-node-atp-worker"
    worker = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": worker_id.split("/", 1)[1]},
        "spec": {"template": {"spec": {"containers": [{"name": "worker", "image": "worker:old"}]}}},
    }
    updated_worker = yaml.safe_load(yaml.safe_dump(worker))
    updated_worker["spec"]["template"]["spec"]["containers"][0]["image"] = "worker:new"
    hook = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": "migrate", "annotations": {"helm.sh/hook": "pre-upgrade"}},
    }
    secret = {"apiVersion": "v1", "kind": "Secret", "metadata": {"name": "runtime"}, "data": {"key": "hidden"}}
    baseline = yaml.safe_dump_all([_flower(), worker, hook, secret])
    candidate = yaml.safe_dump_all([_flower(), updated_worker, hook, secret])
    templates = []

    def fake_capture(command, *, input_text=None):
        if command[1:3] == ["get", "values"]:
            return "{}\n"
        if command[1:3] == ["get", "manifest"]:
            return yaml.safe_dump_all([_flower(), worker, secret])
        if command[1:3] == ["get", "hooks"]:
            return yaml.safe_dump(hook)
        assert command[1] == "template" and input_text == "{}\n"
        templates.append(command.copy())
        return baseline if len(templates) == 1 else candidate

    monkeypatch.setattr(module, "_helm_capture", fake_capture)
    monkeypatch.setattr(module.shutil, "which", lambda _name: "/usr/bin/helm")
    failures, report = module._check_release_chart(
        release="atp-single-node",
        namespace="atp-single-node",
        chart=staged,
        repo_chart=Path("deploy/helm/atp-rev56-hotfix"),
        require_baseline_match=True,
        image_only=True,
        allowed_changes={worker_id},
        allowed_hooks=set(),
        skip_hooks=True,
        image_tags={"worker": "new"},
    )
    assert failures == []
    assert any("unmodified Chart matches release resources and hooks" in line for line in report)
    assert len(templates) == 2
    assert templates[0][-2:] == ["-f", "-"]
    assert templates[1][-2:] == ["--set-string", "image.worker.tag=new"]
    assert all("hidden" not in line for line in report)


def test_release_preflight_baseline_rejects_hook_drift_even_when_skipping_hooks(monkeypatch, tmp_path):
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    source = tmp_path / "deploy" / "helm" / "atp-rev56-hotfix"
    source.mkdir(parents=True)
    (source / "Chart.yaml").write_text("name: atp\nversion: 0.1.0\n", encoding="utf-8")
    old_hook = {"kind": "Job", "metadata": {"name": "migrate", "annotations": {"helm.sh/hook": "pre-upgrade"}}}
    new_hook = yaml.safe_load(yaml.safe_dump(old_hook))
    new_hook["spec"] = {"changed": True}

    def fake_capture(command, *, input_text=None):
        if command[1:3] == ["get", "values"]:
            return "{}\n"
        if command[1:3] == ["get", "manifest"]:
            return yaml.safe_dump(_flower())
        if command[1:3] == ["get", "hooks"]:
            return yaml.safe_dump(old_hook)
        assert command[1] == "template"
        return yaml.safe_dump_all([_flower(), new_hook])

    monkeypatch.setattr(module, "_helm_capture", fake_capture)
    monkeypatch.setattr(module.shutil, "which", lambda _name: "/usr/bin/helm")
    failures, _ = module._check_release_chart(
        release="atp-single-node",
        namespace="atp-single-node",
        chart=source,
        repo_chart=source,
        require_baseline_match=True,
        image_only=True,
        allowed_changes=set(),
        allowed_hooks={"Job/migrate"},
        skip_hooks=True,
    )
    assert failures == ["baseline render differs from release: Job/migrate"]


def test_release_preflight_image_only_rejects_extra_fields_and_hook_changes(monkeypatch, tmp_path):
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    source = tmp_path / "deploy" / "helm" / "atp-rev56-hotfix"
    source.mkdir(parents=True)
    (source / "Chart.yaml").write_text("name: atp\nversion: 0.1.0\n", encoding="utf-8")
    flower_id = "Deployment/atp-single-node-atp-flower"
    hook_id = "Job/migrate"
    flower = _flower()
    changed_flower = yaml.safe_load(yaml.safe_dump(flower))
    container = changed_flower["spec"]["template"]["spec"]["containers"][0]
    container["image"] = "registry.local/atp/worker:new"
    container["args"].append("--extra=1")
    hook = {"kind": "Job", "metadata": {"name": "migrate", "annotations": {"helm.sh/hook": "pre-upgrade"}}}
    changed_hook = yaml.safe_load(yaml.safe_dump(hook))
    changed_hook["spec"] = {"changed": True}
    templates = 0

    def fake_capture(command, *, input_text=None):
        nonlocal templates
        if command[1:3] == ["get", "values"]:
            return "{}\n"
        if command[1:3] == ["get", "manifest"]:
            return yaml.safe_dump(flower)
        if command[1:3] == ["get", "hooks"]:
            return yaml.safe_dump(hook)
        assert command[1] == "template"
        templates += 1
        return yaml.safe_dump_all([flower, hook] if templates == 1 else [changed_flower, changed_hook])

    monkeypatch.setattr(module, "_helm_capture", fake_capture)
    monkeypatch.setattr(module.shutil, "which", lambda _name: "/usr/bin/helm")
    failures, _ = module._check_release_chart(
        release="atp-single-node",
        namespace="atp-single-node",
        chart=source,
        repo_chart=source,
        require_baseline_match=True,
        image_only=True,
        allowed_changes={flower_id},
        allowed_hooks={hook_id},
        skip_hooks=True,
    )
    assert "non-image-only resource change: " + flower_id in failures
    assert "hook change is forbidden by --image-only: " + hook_id in failures


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
