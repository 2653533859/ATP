import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.worker.dispatch import is_web_lowcode_config


@pytest.mark.parametrize(
    ("cfg", "expected"),
    [
        ({"steps": [{"action": "goto"}]}, True),
        ({"steps": []}, True),
        ({"steps": None}, True),
        ({"script_path": "scripts/test_case.py"}, False),
        ({}, False),
        (None, False),
    ],
)
def test_is_web_lowcode_config(cfg, expected):
    assert is_web_lowcode_config(cfg) is expected
