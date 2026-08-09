from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_performance_thin_slice_documents_k6_contract():
    content = (ROOT / "docs" / "performance-testing-thin-slice.md").read_text(encoding="utf-8")

    assert "k6" in content
    assert "run_performance_test" in content
    assert "performance" in content
    assert "http_req_duration" in content
    assert "http_req_failed" in content
    assert "http_reqs" in content
    assert "不混入功能测试通过率" in content
    assert "examples/performance/k6-smoke.js" in content
    assert "docs/fixtures/performance-k6-summary.sample.json" in content


def test_performance_queue_is_documented_in_helm_guide():
    content = (ROOT / "docs" / "deploy-helm.md").read_text(encoding="utf-8")

    assert "default,mobile_special,ios,ai,maintenance,performance" in content
    assert "`performance`：HTTP 压测任务" in content
    assert "Worker（含 Playwright Chromium + ADB + k6）" in content
