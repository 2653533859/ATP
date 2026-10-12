"""Hermes 命令回读不能把其他项目的用例或运行标记为可用。"""

from types import SimpleNamespace

import pytest

from app.models.bootstrap import load_all_models
from app.models.case import TestCase, TestRun
from app.models.project import Module
from app.services.hermes_commands import command_resource

load_all_models()


@pytest.mark.asyncio
@pytest.mark.parametrize("action, resource_id", [("update_case", 40), ("run_case", 30)])
async def test_case_command_requires_matching_project_and_identity(action, resource_id):
    case = TestCase(id=40, module_id=10)
    run = TestRun(id=30, case_id=40)
    module = Module(id=10, project_id=2)

    class FakeDB:
        async def get(self, model, obj_id):
            return {
                (TestCase, 40): case,
                (TestRun, 30): run,
                (Module, 10): module,
            }.get((model, obj_id))

    command = SimpleNamespace(
        action=action,
        resource_id=resource_id,
        project_id=1,
        resource_identity=f"{action}-{resource_id}",
    )
    assert await command_resource(FakeDB(), command) == (None, "replaced")

    module.project_id = 1
    assert await command_resource(FakeDB(), command) == (case if action == "update_case" else run, "available")

    command.resource_identity = "wrong-identity"
    assert await command_resource(FakeDB(), command) == (None, "replaced")
