from __future__ import annotations

import yaml


def test_release_checklist_covers_q10_release_gates(repo_file):
    content = repo_file("docs/q9-release-checklist.md")

    required_commands = (
        "make lint PYTHON=backend/.venv/bin/python",
        "make format-check PYTHON=backend/.venv/bin/python",
        "make mypy PYTHON=backend/.venv/bin/python",
        "make test-backend-coverage PYTHON=backend/.venv/bin/python",
        "make security-bandit PYTHON=backend/.venv/bin/python",
        "make security-pip-audit PYTHON=backend/.venv/bin/python",
        "make security-npm-audit",
        "make test-integration PYTHON=backend/.venv/bin/python",
        "npm --prefix frontend run test",
        "npm --prefix frontend run type-check",
        "npm --prefix frontend run build",
        "npm --prefix frontend run e2e",
        "python3 -m json.tool docker/grafana/dashboards/atp-overview.json",
    )
    for command in required_commands:
        assert command in content

    assert "docker build -t registry.local/atp/worker:<tag> -f backend/Dockerfile.worker backend/" in content
    assert "docker run --rm --entrypoint k6 registry.local/atp/worker:<tag> version" in content
    assert "alembic upgrade head" in content
    assert "helm upgrade --install atp deploy/helm/atp/" in content
    assert "Gitleaks" in content
    assert "Trivy" in content
    assert "API availability" in content
    assert "API P95" in content
    assert "run success rate" in content
    assert "API error-budget" in content
    assert "docs/q9-release-evidence.md" in content
    assert "Q18 productization extension" in content
    assert "20260812_0055" in content
    assert "Performance notification" in content
    assert "scripts/notification-channel-smoke.py" in content
    assert "provider-side delivery evidence" in content
    assert "scripts/windows-android-acceptance.ps1" in content
    assert "scripts/performance-environment-smoke.py" in content
    assert "82%" in content


def test_q9_release_evidence_records_completed_and_pending_checks(repo_file):
    content = repo_file("docs/q9-release-evidence.md")

    assert "83 passed, 3 warnings" in content
    assert "9 passed" in content
    assert "type-check passed" in content
    assert "production build passed" in content
    assert "k6 v0.52.0 smoke run completed" in content
    assert "Pending CI/Staging Evidence" in content
    assert ".github/workflows/release-readiness.yml" in content
    assert "docker run --rm --entrypoint k6 atp-worker:release-readiness version" in content
    assert "helm upgrade --install atp deploy/helm/atp/" in content
    assert "Q18 Local Gate Snapshot" in content
    assert "1944 passed" in content
    assert "Real SMTP, WeCom and DingTalk delivery" in content


def test_release_readiness_workflow_builds_images_and_verifies_k6(repo_file):
    workflow = yaml.safe_load(repo_file(".github/workflows/release-readiness.yml"))
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


def test_release_readiness_workflow_runs_checklist_contract_tests(repo_file):
    """契约字符串只在本文件定义一份；workflow 必须通过运行本文件来执行契约，
    而不是在 YAML 里维护第二份 grep 清单。"""
    workflow = yaml.safe_load(repo_file(".github/workflows/release-readiness.yml"))
    commands = "\n".join(step.get("run", "") for step in workflow["jobs"]["release-checklist-contract"]["steps"])

    assert "pytest backend/tests/worker/test_q9_release_readiness.py" in commands
