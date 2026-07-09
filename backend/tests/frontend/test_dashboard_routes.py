import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_dashboard_avoids_unregistered_case_routes():
    content = repo_path("frontend/src/views/dashboard/DashboardView.vue").read_text(encoding="utf-8")

    assert "router.push('/cases')" not in content
    assert "router.push(`/cases/${params.data._caseId}`)" not in content


def test_dashboard_has_explicit_global_project_scope_toggle():
    content = repo_path("frontend/src/views/dashboard/DashboardView.vue").read_text(encoding="utf-8")

    assert "a-segmented" in content
    assert "DASHBOARD_SCOPE_KEY = 'atp:dashboard:scope'" in content
    assert "effectiveProjectId" in content
    assert "dashboardScope.value === 'project' ? projectId.value : undefined" in content


def test_dashboard_project_alerts_only_load_in_project_scope():
    content = repo_path("frontend/src/views/dashboard/DashboardView.vue").read_text(encoding="utf-8")

    assert "dashboardScope.value !== 'project' || !projectId.value" in content
    assert "dashboardAlertApi.listEvents" in content


def test_dashboard_supports_png_and_csv_exports():
    content = repo_path("frontend/src/views/dashboard/DashboardView.vue").read_text(encoding="utf-8")
    api = repo_path("frontend/src/api/index.ts").read_text(encoding="utf-8")
    card = repo_path("frontend/src/components/dashboard/LazyChartCard.vue").read_text(encoding="utf-8")

    assert "handleExportMenu(chart.exportKey" in content
    assert "downloadChartPng" in content
    assert "statisticsApi.exportCsv" in content
    assert "/statistics/export/csv" in api
    assert '<slot name="extra" />' in card


def test_dashboard_supports_custom_local_layout():
    content = repo_path("frontend/src/views/dashboard/DashboardView.vue").read_text(encoding="utf-8")

    assert "DASHBOARD_LAYOUT_KEY = 'atp:dashboard:layout'" in content
    assert "DEFAULT_DASHBOARD_LAYOUT" in content
    assert 'v-model="dashboardLayout"' in content
    assert "visibleChartConfigs" in content
    assert "resetDashboardLayout" in content


def test_dashboard_has_workbench_shortcuts():
    content = repo_path("frontend/src/views/dashboard/DashboardView.vue").read_text(encoding="utf-8")

    assert "workbench.todayRuns" in content
    assert "workbench.todayFailed" in content
    assert "workbench.pendingReviews" in content
    assert "recentRuns.length" in content
    assert "caseApi.list" in content
    assert "runApi.list" in content
    assert "goToPendingReviews" in content


def test_case_list_accepts_review_status_query_from_dashboard():
    content = repo_path("frontend/src/views/case/CaseList.vue").read_text(encoding="utf-8")
    navigation = repo_path("frontend/src/utils/caseNavigation.ts").read_text(encoding="utf-8")

    assert "readCaseRouteSelection(route)" in content
    assert "filterReviewStatus.value = routeReviewStatus" in content
    assert "reviewStatus: filterReviewStatus.value" in content
    assert "reviewStatus: parseReviewStatus(route.query.review_status)" in navigation
    assert "query.review_status = context.reviewStatus" in navigation
