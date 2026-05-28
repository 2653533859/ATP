import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_dashboard_alert_route_and_menu_registered():
    router = repo_path("frontend/src/router/index.ts").read_text(encoding="utf-8")
    layout = repo_path("frontend/src/layouts/MainLayout.vue").read_text(encoding="utf-8")

    assert "system/dashboard-alerts" in router
    assert "DashboardAlertRulesView.vue" in router
    assert "/system/dashboard-alerts" in layout


def test_dashboard_alert_api_client_registered():
    api = repo_path("frontend/src/api/index.ts").read_text(encoding="utf-8")

    assert "export const dashboardAlertApi" in api
    assert "/dashboard-alert-rules" in api
    assert "/dashboard-alert-events" in api


def test_dashboard_page_loads_project_scoped_alert_events():
    dashboard = repo_path("frontend/src/views/dashboard/DashboardView.vue").read_text(encoding="utf-8")

    assert "dashboardAlertApi.listEvents" in dashboard
    assert "project_id: projectId.value" in dashboard
    assert "system-dashboard-alerts" in dashboard
