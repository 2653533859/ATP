"""断点续录回放的输入全部来自请求体：单步等待/超时必须钳制，总时长必须有预算。"""

import asyncio
from types import SimpleNamespace

from app.api.v1 import web_recordings as web_recordings_module
from app.api.v1.web_recordings import WebRecordingSession


def _session(page, **overrides) -> WebRecordingSession:
    params = dict(
        session_id="replay-limits",
        owner_id=1,
        start_url="https://example.com",
        viewport_width=1280,
        viewport_height=720,
        status="starting",
        page=page,
    )
    params.update(overrides)
    return WebRecordingSession(**params)


def test_replay_single_step_clamps_timeouts_and_waits(monkeypatch):
    calls = []
    sleeps = []

    async def _fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(web_recordings_module, "asyncio", SimpleNamespace(sleep=_fake_sleep))

    class _Page:
        async def goto(self, url, **kwargs):
            calls.append(("goto", kwargs.get("timeout")))

        async def click(self, selector, **kwargs):
            calls.append(("click", kwargs.get("timeout")))

    session = _session(_Page())

    asyncio.run(session._replay_single_step("goto", {"url": "https://example.com", "timeout_ms": 10**12}))
    asyncio.run(session._replay_single_step("click", {"selector": "#submit", "timeout_ms": -5}))
    asyncio.run(session._replay_single_step("wait", {"ms": 10**10}))

    assert calls == [("goto", web_recordings_module._REPLAY_MAX_STEP_TIMEOUT_MS), ("click", 1_000)]
    # wait 被钳制到上限；每步末尾 0.2s 的稳定等待不受影响
    assert max(sleeps) == web_recordings_module._REPLAY_MAX_WAIT_MS / 1000


def test_replay_prefix_stops_when_total_budget_is_exhausted(monkeypatch):
    executed = []
    clock = iter([0.0, 0.0, 301.0, 301.0, 301.0, 301.0])

    async def _noop_sleep(_delay):
        return None

    monkeypatch.setattr(web_recordings_module, "asyncio", SimpleNamespace(sleep=_noop_sleep))
    monkeypatch.setattr(web_recordings_module, "time", SimpleNamespace(monotonic=lambda: next(clock)))

    class _Page:
        async def goto(self, url, **_kwargs):
            executed.append(url)

    session = _session(
        _Page(),
        replay_steps=[
            {"action": "goto", "params": {"url": "https://example.com/a"}},
            {"action": "goto", "params": {"url": "https://example.com/b"}},
        ],
    )

    asyncio.run(session._replay_recorded_prefix())

    # 预算耗尽后剩余前置步骤被跳过，录制仍可从已回放位置继续
    assert executed == ["https://example.com/a"]
    assert session.replayed_step_count == 1
