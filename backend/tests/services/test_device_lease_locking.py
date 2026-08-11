import asyncio
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app.models import load_all_models
from app.models.device import DeviceStatus
from app.models.ios import IosDeviceStatus
from app.services.device_leases import acquire_device_lease
from app.services.ios_device_leases import acquire_ios_device_lease

load_all_models()


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _DB:
    def __init__(self, device):
        self.results = iter([device, None])
        self.statements = []
        self.added = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Result(next(self.results))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None


def _postgres_sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_android_lease_locks_device_row_before_checking_current_lease():
    device = SimpleNamespace(id=3, status=DeviceStatus.online)
    db = _DB(device)

    lease = asyncio.run(acquire_device_lease(db, 3, owner_id=4, owner_label="test"))

    assert "FOR UPDATE" in _postgres_sql(db.statements[0])
    assert lease.device_id == 3
    assert device.status is DeviceStatus.busy


def test_ios_lease_locks_device_row_before_checking_current_lease():
    device = SimpleNamespace(id=5, status=IosDeviceStatus.online)
    db = _DB(device)

    lease = asyncio.run(acquire_ios_device_lease(db, 5, owner_id=6, owner_label="test"))

    assert "FOR UPDATE" in _postgres_sql(db.statements[0])
    assert lease.device_id == 5
    assert device.status is IosDeviceStatus.busy
