"""Common subprocess lifecycle for performance load injectors.

The runner deliberately owns only process lifecycle concerns: cancellation,
timeout, bounded diagnostic output, and resource sampling callbacks.  Each
executor remains responsible for its command line and result adapter.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path


class PerformanceRunCancelled(RuntimeError):
    """Raised when a user safely stops a performance process."""


def run_performance_process(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int = 1800,
    cancel_check: Callable[[], bool] | None = None,
    metric_callback: Callable[[], None] | None = None,
    metric_interval_seconds: float = 5.0,
    max_metric_samples: int = 7200,
    popen_factory: Callable[..., subprocess.Popen] | None = None,
) -> tuple[subprocess.CompletedProcess[str], int]:
    """Run one load-injector process with the platform lifecycle contract."""
    stdout_path = cwd / "stdout.log"
    stderr_path = cwd / "stderr.log"
    factory = popen_factory or subprocess.Popen
    with (
        stdout_path.open("w", encoding="utf-8") as stdout_file,
        stderr_path.open("w", encoding="utf-8") as stderr_file,
    ):
        process = factory(
            list(command),
            cwd=str(cwd),
            env=env,
            text=True,
            stdout=stdout_file,
            stderr=stderr_file,
        )
        started = time.monotonic()
        next_metric_at = started
        metric_count = 0
        while process.poll() is None:
            now = time.monotonic()
            if metric_callback is not None and metric_count < max_metric_samples and now >= next_metric_at:
                try:
                    metric_callback()
                except Exception:
                    # Resource collection is diagnostic only and must never fail the load test.
                    pass
                metric_count += 1
                next_metric_at = now + max(0.5, metric_interval_seconds)
            if cancel_check is not None and cancel_check():
                _terminate_process(process)
                raise PerformanceRunCancelled("Performance run cancelled by user")
            if time.monotonic() - started >= timeout_seconds:
                _terminate_process(process)
                raise RuntimeError(f"performance process timed out after {timeout_seconds} seconds")
            time.sleep(0.5)
        process.wait()

    completed = subprocess.CompletedProcess(
        args=list(command),
        returncode=process.returncode,
        stdout=stdout_path.read_text(encoding="utf-8", errors="replace") or "",
        stderr=stderr_path.read_text(encoding="utf-8", errors="replace") or "",
    )
    return completed, int((time.monotonic() - started) * 1000)


def _terminate_process(process: subprocess.Popen) -> None:
    """Terminate a process gracefully, then force kill if it ignores the request."""
    # Windows executors may launch a .bat wrapper (for example jmeter.bat), which
    # creates a cmd.exe -> java.exe process tree.  Popen.terminate() only targets
    # the wrapper and can leave Java holding stdout/stderr files open.  taskkill
    # with /T is the Windows equivalent of terminating the whole process group.
    process_pid = getattr(process, "pid", None)
    if os.name == "nt" and process_pid:
        subprocess.run(
            ["taskkill", "/PID", str(process_pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        return

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
