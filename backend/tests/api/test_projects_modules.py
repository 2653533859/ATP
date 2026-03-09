import sys
import types
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.database"] = types.SimpleNamespace(get_db=lambda: None)
sys.modules["app.api.deps"] = types.SimpleNamespace(get_current_user=lambda: None)

from app.api.v1 import projects


class _ModuleLike:
    def __init__(self, module_id: int, name: str, project_id: int, parent_id: int | None, sort_order: int):
        self.id = module_id
        self.name = name
        self.project_id = project_id
        self.parent_id = parent_id
        self.sort_order = sort_order
        self.created_at = datetime.now(timezone.utc)

    @property
    def children(self):
        raise AssertionError("tree builder should not touch ORM children relationship")


def test_build_tree_does_not_access_lazy_children_relationship():
    root = _ModuleLike(module_id=1, name="Root", project_id=8, parent_id=None, sort_order=0)
    child = _ModuleLike(module_id=2, name="Child", project_id=8, parent_id=1, sort_order=1)

    tree = projects._build_tree([root, child])

    assert len(tree) == 1
    assert tree[0].id == 1
    assert len(tree[0].children) == 1
    assert tree[0].children[0].id == 2
