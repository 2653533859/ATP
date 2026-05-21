"""跨 cwd 健壮的仓库根定位 helper（P2.1 / P2.2 共用）。

历史问题：多个测试用 `Path("frontend/...")` 或 `Path("backend/...")` 字面量，
假设 cwd 为仓库根。从 backend 目录运行 pytest 时全部失败。

本 helper 一次性定位仓库根（含 backend 与 frontend 两个子目录），
使受影响的测试不依赖 cwd。
"""
from pathlib import Path


def repo_root() -> Path:
    """仓库根目录：含 backend/ 与 frontend/ 两个子目录的最近父目录。

    通过查找当前文件向上的目录链上同时包含 backend/ 和 frontend/ 的层。
    """
    here = Path(__file__).resolve()
    for ancestor in [here.parent, *here.parents]:
        if (ancestor / "backend").is_dir() and (ancestor / "frontend").is_dir():
            return ancestor
    raise RuntimeError("无法定位仓库根：未找到同时含 backend/ 与 frontend/ 的目录")


def repo_path(*parts: str) -> Path:
    """以仓库根为起点拼接路径。"""
    return repo_root().joinpath(*parts)
