from tests._paths import repo_path


def test_run_detail_gates_create_bug_action_by_role():
    content = repo_path("frontend/src/views/run/RunDetail.vue").read_text(encoding="utf-8")

    assert "useAuthStore" in content
    assert "const canCreateBug = computed(" in content
    assert 'v-if="canCreateBug && run && (run.status === \'failed\' || run.status === \'error\')"' in content
