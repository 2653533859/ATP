import asyncio
from types import SimpleNamespace

from app.api.v1 import devices as devices_api
from app.models.bootstrap import load_all_models
from app.models.device import Device
from app.schemas.device import DeviceGroupSave

load_all_models()


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _DB:
    def __init__(self, devices):
        self.devices = devices
        self.added = []

    async def scalar(self, _query):
        return None

    async def execute(self, _query):
        return _Result(self.devices)

    def add(self, item):
        item.id = 9
        self.added.append(item)

    async def commit(self):
        return None

    async def refresh(self, _item):
        return None


def test_create_device_group_resolves_managed_members():
    rows = [Device(id=1, serial="A"), Device(id=2, serial="B")]
    db = _DB(rows)

    group = asyncio.run(
        devices_api.create_device_group(
            DeviceGroupSave(name="主力机型", description="release", device_ids=[1, 2]),
            db,
            SimpleNamespace(id=7),
        )
    )

    assert group.name == "主力机型"
    assert [device.serial for device in group.devices] == ["A", "B"]
    assert db.added == [group]
