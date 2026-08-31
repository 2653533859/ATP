from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_performance_acceptance_bundle_is_allowlisted_and_auditable():
    script = (ROOT / "scripts" / "package-performance-acceptance.ps1").read_text(encoding="utf-8")

    assert "$explicitFiles" in script
    assert "backend" in script
    assert ".env.performance-acceptance.example" in script
    assert "deploy/performance-acceptance/minio-dr.env.example" in script
    assert "deploy/helm/atp/values-performance-acceptance.example.yaml" in script
    assert "sourceDirectories = @('backend', 'deploy/helm/atp')" in script
    assert "deploy/helm/atp" in script
    assert "Write-PortableZip" in script
    assert "ZipArchiveMode]::Create" in script
    assert "Replace('\\', '/')" in script
    assert "bundle-manifest.json" in script
    assert "Get-FileHash" in script
    assert "$gitOutput = @(& git" in script
    assert "worktree_dirty" in script
    assert r"\.env($|\.)" in script
    assert "Remove-Item -LiteralPath $stageRoot -Recurse -Force" in script
    assert "node_modules" not in script
    assert "frontend/dist" not in script
