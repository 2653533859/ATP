import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.object_refs import extract_object_name
from app.core.tracing import build_trace_context, reset_trace_id, set_trace_id


def test_extract_object_name_supports_object_key_and_presigned_url():
    assert extract_object_name("screenshots/runs/1/step_0.png") == "screenshots/runs/1/step_0.png"
    assert (
        extract_object_name("http://minio:9000/atp/screenshots/runs/1/step_0.png?X-Amz-Expires=1")
        == "screenshots/runs/1/step_0.png"
    )


def test_extract_object_name_trims_leading_slash_and_handles_empty():
    assert extract_object_name("/reports/run-1/report.html") == "reports/run-1/report.html"
    assert extract_object_name("") is None
    assert extract_object_name(None) is None


def test_build_trace_context_reuses_existing_trace_id_and_merges_metadata():
    token = set_trace_id("trace-abc")
    try:
        result = build_trace_context(run_id=12, suite_run_id=None, status="running")
    finally:
        reset_trace_id(token)

    assert result == {
        "trace_id": "trace-abc",
        "run_id": 12,
        "status": "running",
    }
