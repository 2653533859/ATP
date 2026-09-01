"""脚本用例的受控 Python 依赖安装。"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

from app.core.minio_client import download_file

_LOCKED_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_,.-]+\])?==[A-Za-z0-9][A-Za-z0-9.*+!_-]*(?:\s*;\s*[^#]+)?$"
)


def validate_script_requirements(content: str) -> str:
    """只接受逐行精确锁定依赖，拒绝 URL、路径和 pip 参数。"""
    normalized_lines: list[str] = []
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not _LOCKED_REQUIREMENT.fullmatch(line):
            raise ValueError(f"requirements.txt 第 {line_number} 行必须使用 package==version 精确锁定")
        normalized_lines.append(line)
    if len(normalized_lines) > 100:
        raise ValueError("requirements.txt 最多允许 100 个依赖")
    return "\n".join(normalized_lines) + ("\n" if normalized_lines else "")


async def prepare_script_dependencies(requirements_path: str | None, workdir: Path, timeout: int = 180) -> Path | None:
    if not requirements_path:
        return None
    requirements_file = workdir / "requirements.txt"
    dependencies_dir = workdir / "dependencies"
    await asyncio.to_thread(download_file, requirements_path, str(requirements_file))
    content = validate_script_requirements(requirements_file.read_text(encoding="utf-8"))
    requirements_file.write_text(content, encoding="utf-8")
    if not content:
        return None
    dependencies_dir.mkdir()
    env = {
        **os.environ,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_INPUT": "1",
        "PYTHONNOUSERSITE": "1",
    }
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-input",
        "--target",
        str(dependencies_dir),
        "--requirement",
        str(requirements_file),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=str(workdir),
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=max(1, min(timeout, 600)))
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise RuntimeError("脚本依赖安装超时") from exc
    if process.returncode != 0:
        detail = (stderr or stdout).decode("utf-8", errors="replace")[-1000:]
        raise RuntimeError(f"脚本依赖安装失败: {detail}")
    return dependencies_dir


def extend_pythonpath(env: dict[str, str], dependencies_dir: Path | None, workdir: Path) -> dict[str, str]:
    entries = [str(workdir)]
    if dependencies_dir is not None:
        entries.insert(0, str(dependencies_dir))
    existing = env.get("PYTHONPATH")
    if existing:
        entries.append(existing)
    return {**env, "PYTHONPATH": os.pathsep.join(entries), "PYTHONNOUSERSITE": "1"}
