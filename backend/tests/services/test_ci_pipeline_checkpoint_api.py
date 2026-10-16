"""Unit tests for CI Pipeline Checkpoint Service & CLI (S4.3)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import pytest

from app.services.change_risk_scorer import reset_change_risk_registry
from app.services.ci_pipeline_checkpoint_api import (
    PipelineStageStatus,
    execute_ci_pipeline_checkpoint,
    get_checkpoint_report,
    list_checkpoint_reports,
    reset_checkpoint_registry,
)
from app.services.code_to_test_mapping_indexer import get_mapping_indexer
from app.services.flaky_test_suppression_filter import reset_flaky_filter_registry
from app.services.git_diff_ast_analyzer import reset_diff_ast_registry
from app.services.pr_quality_gatekeeper import reset_pr_gate_registry
from app.services.smart_test_selection_engine import reset_test_selection_registry


@pytest.fixture(autouse=True)
def clean_all_ci_services():
    reset_diff_ast_registry()
    reset_test_selection_registry()
    reset_change_risk_registry()
    reset_flaky_filter_registry()
    reset_pr_gate_registry()
    reset_checkpoint_registry()
    get_mapping_indexer().clear()
    yield
    reset_diff_ast_registry()
    reset_test_selection_registry()
    reset_change_risk_registry()
    reset_flaky_filter_registry()
    reset_pr_gate_registry()
    reset_checkpoint_registry()
    get_mapping_indexer().clear()


SAMPLE_DIFF = """diff --git a/app/service.py b/app/service.py
--- a/app/service.py
+++ b/app/service.py
@@ -1,2 +1,2 @@
-def greet(): return "hello"
+def greet(): return "hello world"
"""


def test_execute_checkpoint_passed():
    report = execute_ci_pipeline_checkpoint(
        diff_text=SAMPLE_DIFF,
        pipeline_name="GitHub-Actions-Smoke",
        commit_sha="c0ffee11",
        pr_id="101",
        mock_test_pass_rate_pct=100.0,
        mock_test_failed_cases_count=0,
        mutation_score_pct=90.0,
    )

    assert report.exit_code == 0
    assert report.overall_status == PipelineStageStatus.PASSED
    assert len(report.stages) == 4
    assert "✅ [ATP CI 门禁检查点通过]" in report.console_log_output
    assert report.commit_sha == "c0ffee11"


def test_execute_checkpoint_blocked():
    report = execute_ci_pipeline_checkpoint(
        diff_text=SAMPLE_DIFF,
        pipeline_name="Jenkins-Production-Gate",
        commit_sha="deadbeef",
        pr_id="102",
        mock_test_pass_rate_pct=85.0,
        mock_test_failed_cases_count=3,
        mutation_score_pct=40.0,  # 严重不足硬阻断
    )

    assert report.exit_code == 1
    assert report.overall_status == PipelineStageStatus.BLOCKED
    assert "❌ [ATP CI 门禁硬性阻断]" in report.console_log_output
    assert len(report.remediation_summary) > 0


def test_execute_checkpoint_warning():
    report = execute_ci_pipeline_checkpoint(
        diff_text=SAMPLE_DIFF,
        pipeline_name="GitLab-MR-Check",
        commit_sha="12345678",
        pr_id="103",
        mock_test_pass_rate_pct=100.0,
        mock_test_failed_cases_count=0,
        mutation_score_pct=65.0,  # 在 50%~70% 之间次要警告
    )

    assert report.exit_code == 2
    assert report.overall_status == PipelineStageStatus.WARNING
    assert "⚠️ [ATP CI 门禁警告放行]" in report.console_log_output


def test_get_and_list_checkpoint_reports():
    report = execute_ci_pipeline_checkpoint(diff_text=SAMPLE_DIFF)
    fetched = get_checkpoint_report(report.checkpoint_id)
    assert fetched is not None
    assert fetched.checkpoint_id == report.checkpoint_id

    reports = list_checkpoint_reports()
    assert len(reports) == 1
    assert reports[0].checkpoint_id == report.checkpoint_id


def test_cli_script_execution():
    cli_path = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "ci_atp_checkpoint.py"
    cmd = [
        sys.executable,
        str(cli_path),
        "--commit-sha",
        "aabbccdd",
        "--pr-id",
        "555",
        "--diff-text",
        SAMPLE_DIFF,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "ATP CI Checkpoint" in proc.stdout
    assert "aabbccdd" in proc.stdout
