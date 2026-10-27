"""Windows Native WebView2 Desktop Host for ATP (Option A).

Launches the local standalone backend/frontend stack and displays it in a
dedicated native desktop window using Windows Microsoft Edge WebView2.
"""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PYTHON = REPO_ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
STANDALONE_PS1 = REPO_ROOT / "scripts" / "windows-standalone.ps1"


def wait_for_ready(url: str, timeout: int = 45) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def start_local_stack():
    """Ensure local ATP services are started via standalone script."""
    print("正在启动 ATP 本地独立运行环境...")
    powershell = "powershell.exe"
    res = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(STANDALONE_PS1), "-Action", "up"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(f"启动本地环境失败:\n{res.stderr}\n{res.stdout}")
        sys.exit(1)
    print("本地服务已就绪 (Backend 8001 / Frontend 5174)。")


def stop_local_stack():
    """Stop local ATP services when the desktop window is closed."""
    print("\n正在安全退出 ATP 本地服务...")
    powershell = "powershell.exe"
    subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(STANDALONE_PS1), "-Action", "down"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    print("ATP 本地服务已安全退出。")


def main():
    import webview

    # 1. 启动并校验本地后端
    start_local_stack()

    # 2. 检查前端入口 (优先使用 5174 Vite 或 8001 静态前端)
    app_url = "http://127.0.0.1:5174/"
    if not wait_for_ready("http://127.0.0.1:5174/", timeout=5):
        if wait_for_ready("http://127.0.0.1:8001/health", timeout=5):
            app_url = "http://127.0.0.1:8001/"
        else:
            print("ERROR: 未探测到就绪的前端入口 (5174 / 8001)")
            stop_local_stack()
            sys.exit(1)

    print(f"正在启动原生 Edge WebView2 独立窗口 ({app_url})...")

    # 3. 创建原生 WebView2 独立桌面窗口
    window = webview.create_window(
        title="ATP 自动化测试平台 · Windows 桌面独立端",
        url=app_url,
        width=1320,
        height=850,
        min_size=(1024, 700),
        resizable=True,
        confirm_close=False,
    )

    try:
        # 启动原生 WebView2 事件循环
        webview.start(gui="edgechromium", debug=False)
    finally:
        # 窗口关闭后自动退出后台服务
        stop_local_stack()


if __name__ == "__main__":
    main()
