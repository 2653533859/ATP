import asyncio
import types

from app.models.bootstrap import load_all_models
from app.models.defect import Defect, DefectRunLink
from app.services.plan_auto_defect import auto_create_internal_defects_for_plan_run

load_all_models()


class _FakeResult:
    def __init__(self, values):
        self._values = list(values)

    def scalar_one_or_none(self):
        return self._values[0] if self._values else None

    def first(self):
        return self._values[0] if self._values else None


class _FakeDB:
    def __init__(self, objects=None, execute_results=None):
        self._objects = dict(objects or {})
        self._execute_results = list(execute_results or [])
        self.added = []
        self._next_id = 300

    async def get(self, model, key):
        return self._objects.get((model.__name__, key))

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                self._next_id += 1
                obj.id = self._next_id

    async def execute(self, _stmt):
        if self._execute_results:
            return self._execute_results.pop(0)
        return _FakeResult([])


def test_auto_create_internal_defects_creates_new_defect_and_run_link():
    plan = types.SimpleNamespace(id=11, project_id=111)
    plan_run = types.SimpleNamespace(id=13, triggered_by=None)
    suite_run = types.SimpleNamespace(
        id=17,
        case_run_ids=[{"case_id": 109, "run_id": 245, "status": "failed", "error": "断言失败: 缺少关键字"}],
    )
    case_run = types.SimpleNamespace(
        id=245,
        case_id=109,
        status="failed",
        environment="default",
        trace_id="trace-245",
        error_message=None,
    )
    case = types.SimpleNamespace(id=109, name="正文断言验证")

    db = _FakeDB(
        objects={
            ("SuiteRun", 17): suite_run,
            ("TestRun", 245): case_run,
            ("TestCase", 109): case,
        },
        execute_results=[
            _FakeResult([]),  # _find_active_duplicate
            _FakeResult([]),  # _ensure_run_link
        ],
    )

    results = asyncio.run(
        auto_create_internal_defects_for_plan_run(
            db,
            plan=plan,
            plan_run=plan_run,
            suite_run_results=[{"suite_run_id": 17}],
        )
    )

    defects = [item for item in db.added if isinstance(item, Defect)]
    links = [item for item in db.added if isinstance(item, DefectRunLink)]
    assert len(defects) == 1
    assert defects[0].project_id == 111
    assert defects[0].title == "[ATP] 正文断言验证 执行失败"
    assert defects[0].labels == ["auto-plan"]
    assert defects[0].creator_id is None
    assert len(links) == 1
    assert links[0].run_type == "case" and links[0].run_id == 245
    assert results == [
        {
            "case_id": 109,
            "run_id": 245,
            "defect_id": defects[0].id,
            "bug_id": f"DEF-{defects[0].id}",
            "source": "internal",
            "duplicate": False,
        }
    ]


def test_auto_create_internal_defects_deduplicates_existing_active_defect():
    plan = types.SimpleNamespace(id=11, project_id=111)
    plan_run = types.SimpleNamespace(id=14, triggered_by=2)
    suite_run = types.SimpleNamespace(
        id=18,
        case_run_ids=[{"case_id": 109, "run_id": 246, "status": "error"}],
    )
    case_run = types.SimpleNamespace(
        id=246,
        case_id=109,
        status="error",
        environment="default",
        trace_id="trace-246",
        error_message="Connection refused",
    )
    case = types.SimpleNamespace(id=109, name="正文断言验证")
    existing_defect = Defect(
        id=88,
        project_id=111,
        case_id=109,
        title="[ATP] 正文断言验证 执行失败",
        status="open",
        occurrence_count=2,
    )

    db = _FakeDB(
        objects={
            ("SuiteRun", 18): suite_run,
            ("TestRun", 246): case_run,
            ("TestCase", 109): case,
        },
        execute_results=[
            _FakeResult([existing_defect]),  # _find_active_duplicate
            _FakeResult([]),  # _ensure_run_link
        ],
    )

    results = asyncio.run(
        auto_create_internal_defects_for_plan_run(
            db,
            plan=plan,
            plan_run=plan_run,
            suite_run_results=[{"suite_run_id": 18}],
        )
    )

    assert existing_defect.occurrence_count == 3
    links = [item for item in db.added if isinstance(item, DefectRunLink)]
    assert len(links) == 1
    assert links[0].defect_id == 88 and links[0].linked_by == 2
    assert results == [
        {
            "case_id": 109,
            "run_id": 246,
            "defect_id": 88,
            "bug_id": "DEF-88",
            "source": "internal",
            "duplicate": True,
        }
    ]


def test_auto_create_internal_defects_does_not_recount_existing_run_link():
    plan = types.SimpleNamespace(id=11, project_id=111)
    plan_run = types.SimpleNamespace(id=15, triggered_by=2)
    suite_run = types.SimpleNamespace(
        id=19,
        case_run_ids=[{"case_id": 109, "run_id": 246, "status": "error"}],
    )
    case_run = types.SimpleNamespace(
        id=246,
        case_id=109,
        status="error",
        environment="default",
        trace_id="trace-246",
        error_message="Connection refused",
    )
    case = types.SimpleNamespace(id=109, name="正文断言验证")
    existing_defect = Defect(
        id=88,
        project_id=111,
        case_id=109,
        title="[ATP] 正文断言验证 执行失败",
        status="open",
        occurrence_count=3,
    )
    existing_link = DefectRunLink(defect_id=88, run_type="case", run_id=246, case_id=109, evidence={})

    db = _FakeDB(
        objects={
            ("SuiteRun", 19): suite_run,
            ("TestRun", 246): case_run,
            ("TestCase", 109): case,
        },
        execute_results=[
            _FakeResult([existing_defect]),
            _FakeResult([existing_link]),
        ],
    )

    asyncio.run(
        auto_create_internal_defects_for_plan_run(
            db,
            plan=plan,
            plan_run=plan_run,
            suite_run_results=[{"suite_run_id": 19}],
        )
    )

    assert existing_defect.occurrence_count == 3
    assert existing_link.linked_by == 2
