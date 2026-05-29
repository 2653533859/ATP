from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def test_q9_release_checklist_covers_release_gates():
    content = (ROOT / "docs" / "q9-release-checklist.md").read_text(encoding="utf-8")

    assert "python -m pytest tests -q" in content
    assert "npm run type-check" in content
    assert "npm run build" in content
    assert "docker build -t registry.local/atp/worker:<tag> -f backend/Dockerfile.worker backend/" in content
    assert "docker run --rm --entrypoint k6 registry.local/atp/worker:<tag> version" in content
    assert "alembic upgrade head" in content
    assert "helm upgrade --install atp deploy/helm/atp/" in content
    assert "performance" in content
    assert "docs/q9-release-evidence.md" in content


def test_q9_release_evidence_records_completed_and_pending_checks():
    content = (ROOT / "docs" / "q9-release-evidence.md").read_text(encoding="utf-8")

    assert "83 passed, 3 warnings" in content
    assert "9 passed" in content
    assert "type-check passed" in content
    assert "production build passed" in content
    assert "k6 v0.52.0 smoke run completed" in content
    assert "Pending CI/Staging Evidence" in content
    assert ".github/workflows/release-readiness.yml" in content
    assert "docker run --rm --entrypoint k6 atp-worker:release-readiness version" in content
    assert "helm upgrade --install atp deploy/helm/atp/" in content


def test_release_readiness_workflow_builds_images_and_verifies_k6():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "release-readiness.yml").read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    docker_steps = jobs["docker-build"]["steps"]
    commands = "\n".join(step.get("run", "") for step in docker_steps)

    assert workflow["name"] == "Release readiness"
    assert "workflow_dispatch" in workflow[True]
    assert "schedule" in workflow[True]
    assert "docker build -t atp-backend:release-readiness backend/" in commands
    assert "docker build -t atp-worker:release-readiness -f backend/Dockerfile.worker backend/" in commands
    assert "docker run --rm --entrypoint k6 atp-worker:release-readiness version" in commands
    assert "docker build -t atp-frontend:release-readiness frontend/" in commands
