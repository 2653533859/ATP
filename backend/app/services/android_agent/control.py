"""M0 write gate: lease, control epoch and cancellation are rechecked per write."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.device_leases import get_active_device_lease


class ControlRejected(ValueError):
    """Stable codes: write_cancelled, control_epoch_changed, lease_lost."""


@dataclass
class ControlState:
    epoch: int = 0
    cancelled: bool = False

    def pause(self) -> None:
        self.epoch += 1

    def cancel(self) -> None:
        self.cancelled = True
        self.epoch += 1


class DeviceControlGate:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        *,
        device_id: int,
        lease_token: str,
        state: ControlState,
    ):
        self.session_factory = session_factory
        self.device_id = device_id
        self.lease_token = lease_token
        self.state = state

    async def check(self, captured_epoch: int) -> None:
        if self.state.cancelled:
            raise ControlRejected("write_cancelled")
        if captured_epoch != self.state.epoch:
            raise ControlRejected("control_epoch_changed")
        async with self.session_factory() as db:
            lease = await get_active_device_lease(db, self.device_id, self.lease_token)
        if lease is None:
            raise ControlRejected("lease_lost")
        # The DB await above may have yielded to a pause or cancel request.
        if self.state.cancelled or captured_epoch != self.state.epoch:
            raise ControlRejected("control_epoch_changed")

    def sync_check(self, captured_epoch: int, loop: asyncio.AbstractEventLoop) -> Callable[[], None]:
        """Callback for adapter calls running in a worker thread."""

        def check() -> None:
            asyncio.run_coroutine_threadsafe(self.check(captured_epoch), loop).result(timeout=10)

        return check
