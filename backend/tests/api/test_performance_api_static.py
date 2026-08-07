from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_performance_router_registered():
    content = (ROOT / "backend" / "app" / "api" / "v1" / "router.py").read_text(encoding="utf-8")

    assert "performance" in content
    assert "router.include_router(performance.router)" in content


def test_performance_api_exposes_thin_slice_endpoints():
    content = (ROOT / "backend" / "app" / "api" / "v1" / "performance.py").read_text(encoding="utf-8")

    assert '"/projects/{project_id}/performance/tests"' in content
    assert '"/projects/{project_id}/performance/scripts"' in content
    assert '"/performance/tests"' in content
    assert '"/performance/tests/{test_id}/run"' in content
    assert '"/performance/runs/{run_id}"' in content
    assert '"/performance/runs/{run_id}/stop"' in content
    assert '"/performance/runs/{run_id}/gate"' in content
    assert '"/performance/runs/{run_id}/baseline-comparison"' in content
    assert '"/performance/runs/{run_id}/metrics"' in content
    assert '"/performance/runs/{run_id}/export/json"' in content
    assert '"/performance/runs/{run_id}/export/csv"' in content
    assert '"/performance/runs/{run_id}/raw-result"' in content
    assert "upload_bytes(object_name, content" in content
    assert "presigned_url(run.raw_result_object_name" in content
    assert "enqueue_performance_run(run_performance_test" in content
    assert '"/performance/nodes"' in content
    assert '"/performance/nodes/{node_id}"' in content
    assert '"/performance/tests/{test_id}/baseline"' in content
    assert '"/performance/tests/{test_id}/schedule"' in content


def test_performance_models_loaded_for_migrations_and_bootstrap():
    bootstrap = (ROOT / "backend" / "app" / "models" / "bootstrap.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend" / "alembic" / "versions" / "20260529_0036_add_performance_tests.py").read_text(
        encoding="utf-8"
    )

    assert "PerformanceTest" in bootstrap
    assert "PerformanceRun" in bootstrap
    assert "PerformanceMetricSample" in bootstrap
    assert "PerformanceNode" in bootstrap
    assert "performance_tests" in migration
    assert "performance_runs" in migration


def test_storage_cleanup_knows_performance_artifacts():
    content = (ROOT / "backend" / "app" / "services" / "storage_cleanup.py").read_text(encoding="utf-8")

    assert '"performance/"' in content
    assert "PerformanceTest.script_object_name" in content
    assert "PerformanceRun.raw_result_object_name" in content
