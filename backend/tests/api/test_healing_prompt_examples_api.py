from pathlib import Path


def repo_path(path: str) -> Path:
    return Path(__file__).resolve().parents[2] / path


def test_healing_prompt_examples_router_registered():
    content = repo_path("app/api/v1/router.py").read_text(encoding="utf-8")

    assert "healing_prompt_examples" in content
    assert "router.include_router(healing_prompt_examples.router)" in content


def test_healing_prompt_examples_endpoints_require_admin():
    content = repo_path("app/api/v1/healing_prompt_examples.py").read_text(encoding="utf-8")

    assert "require_admin" in content
    assert 'APIRouter(prefix="/ai-healing/examples"' in content
    assert '@router.post("/from-step/{step_result_id}"' in content
    assert '@router.patch("/{example_id}"' in content
    assert '@router.delete("/{example_id}"' in content
