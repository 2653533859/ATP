from types import SimpleNamespace
import os
from pathlib import Path
import signal
import sys
import time

import pytest

from app.services import performance_process


def test_terminate_process_kills_windows_process_tree(monkeypatch):
    commands = []
    waits = []
    process = SimpleNamespace(
        pid=1234,
        poll=lambda: None,
        wait=lambda timeout: waits.append(timeout),
        kill=lambda: None,
    )

    monkeypatch.setattr(performance_process.os, "name", "nt")
    monkeypatch.setattr(
        performance_process.subprocess,
        "run",
        lambda command, **kwargs: commands.append((command, kwargs)),
    )

    performance_process._terminate_process(process)

    assert commands == [
        (
            ["taskkill", "/PID", "1234", "/T", "/F"],
            {
                "stdout": performance_process.subprocess.DEVNULL,
                "stderr": performance_process.subprocess.DEVNULL,
                "check": False,
            },
        )
    ]
    assert waits == [5]


@pytest.mark.parametrize("leader_exits", [False, True])
def test_terminate_process_kills_unix_group_even_when_wrapper_exits_first(monkeypatch, leader_exits):
    calls = []

    class FakeProcess:
        pid = 1234

        def poll(self):
            return None

        def wait(self, timeout):
            calls.append(("wait", timeout))
            if len(calls) == 2 and not leader_exits:
                raise performance_process.subprocess.TimeoutExpired(cmd="test", timeout=timeout)

    monkeypatch.setattr(performance_process.os, "name", "posix")
    monkeypatch.setattr(performance_process.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(performance_process.os, "killpg", lambda pid, sig: calls.append((pid, sig)), raising=False)

    performance_process._terminate_process(FakeProcess())

    assert calls == [
        (1234, performance_process.signal.SIGTERM),
        ("wait", 5),
        (1234, performance_process.signal.SIGKILL),
        ("wait", 5),
    ]


def test_terminate_process_tolerates_group_already_gone(monkeypatch):
    waits = []

    def missing_group(*_args):
        raise ProcessLookupError

    monkeypatch.setattr(performance_process.os, "name", "posix")
    monkeypatch.setattr(performance_process.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(performance_process.os, "killpg", missing_group, raising=False)
    performance_process._terminate_process(SimpleNamespace(pid=1234, wait=lambda timeout: waits.append(timeout)))
    assert waits == [5, 5]


@pytest.mark.parametrize("platform", ["posix", "nt"])
def test_runner_isolates_posix_session_without_changing_windows_launch(monkeypatch, tmp_path, platform):
    launches = []

    def factory(command, **kwargs):
        launches.append(kwargs)
        return SimpleNamespace(poll=lambda: 0, wait=lambda: 0, returncode=0)

    monkeypatch.setattr(performance_process, "os", SimpleNamespace(name=platform))
    performance_process.run_performance_process(["injector"], cwd=tmp_path, env={}, popen_factory=factory)
    assert launches[0]["start_new_session"] is (platform == "posix")


@pytest.mark.skipif(sys.platform != "linux", reason="Real process-group check requires Linux /proc")
def test_cancellation_stops_sigterm_resistant_child_of_wrapper(tmp_path):
    marker = tmp_path / "child.pid"
    child = (
        "import os,signal,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"Path({str(marker)!r}).write_text(str(os.getpid())); time.sleep(60)"
    )
    wrapper = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(60)"
    child_pid = None
    try:
        with pytest.raises(performance_process.PerformanceRunCancelled):
            performance_process.run_performance_process(
                [sys.executable, "-c", wrapper],
                cwd=tmp_path,
                env=os.environ.copy(),
                timeout_seconds=10,
                cancel_check=marker.exists,
            )
        child_pid = int(marker.read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            stat = Path(f"/proc/{child_pid}/stat")
            if not stat.exists() or stat.read_text().split(") ", 1)[1].split()[0] == "Z":
                return
            time.sleep(0.1)
        pytest.fail("Load-injector child survived cancellation")
    finally:
        if child_pid is None and marker.exists():
            child_pid = int(marker.read_text())
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
