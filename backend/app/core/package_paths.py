"""Locate resources in source checkouts, container images and PyInstaller one-folder builds."""

from pathlib import Path
import sys


def _app_root() -> Path:
    """Directory that contains the ``app`` package (``backend/`` or a container's ``/app``)."""
    return Path(__file__).resolve().parents[2]


def installation_root() -> Path:
    if getattr(sys, "frozen", False):
        # The packaged backend lives at <install>/backend/atp-backend.exe.
        return Path(sys.executable).resolve().parent.parent
    app_root = _app_root()
    repo_root = app_root.parent
    # Source checkout: backend/ sits inside the repository root, next to scripts/.
    # Container images install the backend subtree itself as the app root.
    if (repo_root / "backend" / "assets").is_dir():
        return repo_root
    return app_root


def _resolve_in(root: Path, relative_path: str) -> Path:
    """Resolve ``relative_path`` under ``root``, tolerating a stripped ``backend/`` prefix.

    Repository-relative resources are addressed as ``backend/assets/...``; container
    images copy ``backend/`` to ``/app``, so the same file lives at ``assets/...``.
    """
    direct = root / relative_path
    if direct.exists():
        return direct
    parts = Path(relative_path).parts
    if parts and parts[0] == "backend" and len(parts) > 1:
        stripped = root.joinpath(*parts[1:])
        if stripped.exists():
            return stripped
    return direct


def bundled_resource(relative_path: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / relative_path  # type: ignore[attr-defined]
    return _resolve_in(installation_root(), relative_path)
