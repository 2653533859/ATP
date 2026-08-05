#!/usr/bin/env python3
"""逐个运行后端测试文件，确保每个文件都能单独跑通（Q15-02）。

CLAUDE.md 把 `pytest backend/tests/api/test_auth.py` 列为文档化的入口，但只有整
套按序运行时才成立的测试会让这个入口静默失效：文件 A 顺带把 `backend/` 插进
`sys.path`、或顺带把某个 stub 补全，文件 B 才恰好能导入成功。全套绿灯掩盖了这
类耦合，只有逐文件跑才暴露。

用法：

    python scripts/pytest-standalone-sweep.py            # 全量扫描
    python scripts/pytest-standalone-sweep.py --jobs 4    # 并发扫描
    python scripts/pytest-standalone-sweep.py backend/tests/api  # 限定子树
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = REPO_ROOT / "backend" / "tests"
EXCLUDED_PARTS = {"integration"}


def discover(targets: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for target in targets:
        if target.is_file():
            files.add(target)
            continue
        for path in target.rglob("test_*.py"):
            if EXCLUDED_PARTS & set(path.relative_to(REPO_ROOT).parts):
                continue
            files.add(path)
    return sorted(files)


def run_one(path: Path, timeout: int) -> tuple[Path, int, str]:
    relative = path.relative_to(REPO_ROOT).as_posix()
    command = [sys.executable, "-m", "pytest", relative, "-q", "-p", "no:cacheprovider"]
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return path, 1, f"timed out after {timeout}s"
    if completed.returncode == 0:
        return path, 0, ""
    return path, completed.returncode, _first_signal(completed.stdout + completed.stderr)


def _first_signal(output: str) -> str:
    """挑出最有信息量的一行，避免把整份 pytest 输出灌进 CI 日志。"""
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith(("E   ", "ERROR ", "FAILED ")):
            return stripped
    for line in reversed(output.splitlines()):
        if line.strip():
            return line.strip()
    return "no output"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", type=Path, default=None)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args(argv)

    targets = [Path(target).resolve() for target in args.targets] or [DEFAULT_ROOT]
    files = discover(targets)
    if not files:
        print("no test files discovered", file=sys.stderr)
        return 2

    print(f"sweeping {len(files)} test files standalone (jobs={args.jobs})")
    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            results = list(pool.map(lambda path: run_one(path, args.timeout), files))
    else:
        results = [run_one(path, args.timeout) for path in files]

    failures = [(path, reason) for path, code, reason in results if code != 0]
    for path, reason in failures:
        print(f"FAIL {path.relative_to(REPO_ROOT).as_posix()}\n     {reason}")

    print(f"\n{len(files) - len(failures)} passed, {len(failures)} failed standalone")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
