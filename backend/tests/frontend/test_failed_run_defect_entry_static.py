from tests._paths import repo_path


def test_android_report_can_create_and_open_internal_defects_from_failed_runs():
    content = repo_path("frontend/src/views/mobile-special/ReportDetailView.vue").read_text(encoding="utf-8")

    assert "defectApi.createFromRun('android', runId.value)" in content
    assert "defectApi.list({ run_type: 'android'" in content
    assert "['failed', 'error', 'cancelled', 'stopped']" in content
    assert "run.task_type === 'stability'" in content
    assert "name: 'bugs'" in content
    assert "run_type: 'android'" in content


def test_performance_detail_can_create_and_open_internal_defects_from_failed_runs():
    content = repo_path("frontend/src/views/system/PerformanceCenterView.vue").read_text(encoding="utf-8")

    assert "defectApi.createFromRun('performance', record.id)" in content
    assert "defectApi.list({ run_type: 'performance'" in content
    assert "canCreateInternalDefect(selectedRun)" in content
    assert "name: 'bugs'" in content
    assert "run_type: 'performance'" in content


def test_failed_run_defect_copy_is_localized():
    zh = repo_path("frontend/src/locales/zh-CN.ts").read_text(encoding="utf-8")
    en = repo_path("frontend/src/locales/en-US.ts").read_text(encoding="utf-8")

    for content in (zh, en):
        assert "create_internal_defect" in content
        assert "internal_defects" in content
        assert "defect_duplicate" in content
        assert "defect_create_failed" in content
