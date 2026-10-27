"""The bundled backend must reject direct starts before loading server settings."""

import os
import subprocess
import sys
from pathlib import Path


ENTRY = Path(__file__).resolve().parents[2] / "frozen_entry.py"


def test_direct_start_explains_launcher_requirement() -> None:
    env = os.environ.copy()
    env.pop("ATP_LOCAL_MODE", None)
    result = subprocess.run(
        [sys.executable, str(ENTRY)],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 2
    assert "ATP_LOCAL_MODE=true is required" in result.stderr
    assert "Traceback" not in result.stderr
