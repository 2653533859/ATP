import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_domain_boundaries_document_core_domains():
    content = repo_path("docs/domain-boundaries.md").read_text(encoding="utf-8")

    for domain in ["case", "execution", "reporting", "notification", "mock", "ai"]:
        assert f"| {domain} |" in content


def test_domain_boundaries_document_cross_domain_contracts():
    content = repo_path("docs/domain-boundaries.md").read_text(encoding="utf-8")

    assert "## Domain Contracts" in content
    assert "case -> execution" in content
    assert "execution -> reporting" in content
    assert "execution -> notification" in content
    assert "Placement Rules For New Code" in content
    assert "Known Boundary Debt" in content
