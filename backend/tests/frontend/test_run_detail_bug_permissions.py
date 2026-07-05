import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_run_detail_gates_create_bug_action_by_role():
    content = repo_path("frontend/src/views/run/RunDetail.vue").read_text(encoding="utf-8")

    assert "useAuthStore" in content
    assert "const canCreateBug = computed(" in content
    assert 'v-if="canCreateBug && run && (run.status === \'failed\' || run.status === \'error\')"' in content


def test_run_detail_has_investigation_workspace():
    content = repo_path("frontend/src/views/run/RunDetail.vue").read_text(encoding="utf-8")
    zh = repo_path("frontend/src/locales/zh-CN.ts").read_text(encoding="utf-8")
    en = repo_path("frontend/src/locales/en-US.ts").read_text(encoding="utf-8")

    assert "investigation-panel" in content
    assert "failedOrErrorSteps" in content
    assert "screenshotCount" in content
    assert "primaryErrorSummary" in content
    assert "diagnosisStatusText" in content
    assert "focusStep(step.step_index)" in content
    assert "data-run-step" in content
    assert "排查工作台" in zh
    assert "Investigation workspace" in en
