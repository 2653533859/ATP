from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


ROOT = Path(__file__).resolve().parents[3]


def test_settings_fall_back_to_repository_root_env_file():
    env_files = Settings.model_config["env_file"]

    assert Path(env_files[0]).resolve() == ROOT / ".env"
    assert env_files[1] == ".env"
