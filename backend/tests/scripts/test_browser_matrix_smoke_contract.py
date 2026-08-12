"""Static contract checks for the cross-browser evidence smoke command."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_browser_matrix_collects_cross_browser_evidence_without_query_values():
    source = (ROOT / "frontend" / "tools" / "browser-matrix-smoke.mjs").read_text(encoding="utf-8")

    assert "chromium,firefox,webkit" in source
    assert "ATP_WEB_SMOKE_BROWSERS" in source
    assert "ATP_WEB_SMOKE_ARTIFACT_DIR" in source
    assert "ATP_WEB_SMOKE_REPORT" in source
    assert "context.tracing.start" in source
    assert "context.tracing.stop" in source
    assert "recordHar" in source
    assert "page.on('console'" in source
    assert "page.on('requestfailed'" in source
    assert "page.on('response'" in source
    assert "value.search = ''" in source
    assert "value.hash = ''" in source


def test_browser_matrix_keeps_default_login_contract_and_nonzero_failure_exit():
    source = (ROOT / "frontend" / "tools" / "browser-matrix-smoke.mjs").read_text(encoding="utf-8")

    assert "http://127.0.0.1:5173/login" in source
    assert "waitForSelector('input'" in source
    assert "process.exitCode = 1" in source
    assert "status !== null && item.status < 400 && !item.error" in source
