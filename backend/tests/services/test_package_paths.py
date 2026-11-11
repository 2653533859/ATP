"""Resource paths must work in source, container and frozen Windows layouts."""

import sys
from pathlib import Path

from app.core.package_paths import bundled_resource, installation_root


def test_source_checkout_resources() -> None:
    repo = Path(__file__).resolve().parents[3]
    assert installation_root() == repo
    assert bundled_resource("scripts/device_agent.py") == repo / "scripts" / "device_agent.py"
    assert bundled_resource("backend/assets/scrcpy-server.jar").is_file()


def test_container_layout_strips_backend_prefix(monkeypatch, tmp_path: Path) -> None:
    """Images copy ``backend/`` to ``/app``: the jar lives at ``assets/``, not ``backend/assets/``."""
    app_root = tmp_path / "app"
    (app_root / "app" / "core").mkdir(parents=True)
    (app_root / "assets").mkdir()
    jar = app_root / "assets" / "scrcpy-server.jar"
    jar.write_bytes(b"jar")

    monkeypatch.setattr("app.core.package_paths.__file__", str(app_root / "app" / "core" / "package_paths.py"))

    assert installation_root() == app_root
    assert bundled_resource("backend/assets/scrcpy-server.jar") == jar


def test_frozen_resources_are_separate_from_installation_data(monkeypatch, tmp_path: Path) -> None:
    install = tmp_path / "ATP"
    bundle = install / "backend" / "_internal"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(install / "backend" / "atp-backend.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)

    assert installation_root() == install
    assert bundled_resource("scripts/device_agent.py") == bundle / "scripts" / "device_agent.py"
    assert bundled_resource("backend/assets/scrcpy-server.jar") == bundle / "backend" / "assets" / "scrcpy-server.jar"
