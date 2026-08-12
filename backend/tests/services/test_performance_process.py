from types import SimpleNamespace

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


def test_terminate_process_uses_graceful_then_forceful_shutdown_on_unix(monkeypatch):
    calls = []

    class FakeProcess:
        pid = 1234

        def poll(self):
            return None

        def terminate(self):
            calls.append("terminate")

        def wait(self, timeout):
            calls.append(("wait", timeout))
            if len(calls) == 2:
                raise performance_process.subprocess.TimeoutExpired(cmd="test", timeout=timeout)

        def kill(self):
            calls.append("kill")

    monkeypatch.setattr(performance_process.os, "name", "posix")

    performance_process._terminate_process(FakeProcess())

    assert calls == ["terminate", ("wait", 5), "kill", ("wait", 5)]
