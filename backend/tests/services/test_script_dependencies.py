import os
from pathlib import Path

import pytest

from app.services.script_dependencies import extend_pythonpath, validate_script_requirements


def test_validate_script_requirements_normalizes_locked_dependencies():
    assert validate_script_requirements("\nrequests==2.32.3\nfoo[bar]==1.0; python_version >= '3.12'\n") == (
        "requests==2.32.3\nfoo[bar]==1.0; python_version >= '3.12'\n"
    )


@pytest.mark.parametrize("content", ["requests", "requests>=2", "../package", "git+https://example.test/repo"])
def test_validate_script_requirements_rejects_unlocked_sources(content):
    with pytest.raises(ValueError):
        validate_script_requirements(content)


def test_extend_pythonpath_keeps_dependencies_isolated_and_preserves_existing():
    env = extend_pythonpath({"PYTHONPATH": "/existing"}, Path("/tmp/deps"), Path("/tmp/run"))
    assert env["PYTHONPATH"].split(os.pathsep) == ["/tmp/deps", "/tmp/run", "/existing"]
    assert env["PYTHONNOUSERSITE"] == "1"
