from pathlib import Path


def test_dashboard_avoids_unregistered_case_routes():
    content = Path("frontend/src/views/dashboard/DashboardView.vue").read_text(encoding="utf-8")

    assert "router.push('/cases')" not in content
    assert "router.push(`/cases/${params.data._caseId}`)" not in content

