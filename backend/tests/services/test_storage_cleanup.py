import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

sys.modules["app.core.minio_client"] = types.SimpleNamespace(
    list_objects=lambda prefix: [],
    delete_file=lambda object_name: None,
)

from app.services import storage_cleanup


class _FakeObject:
    def __init__(self, object_name: str, last_modified: datetime | None, size: int = 0):
        self.object_name = object_name
        self.last_modified = last_modified
        self.size = size


class _FakeSession:
    def __init__(self, responses=None, get_map=None):
        self._responses = list(responses or [])
        self._get_map = get_map or {}
        self.commit_calls = 0

    def execute(self, _stmt):
        return types.SimpleNamespace(all=lambda: self._responses.pop(0) if self._responses else [])

    def get(self, model, record_id):
        return self._get_map.get((getattr(model, "__name__", str(model)), record_id))

    def commit(self):
        self.commit_calls += 1


def test_get_storage_stats_aggregates_objects_by_prefix(monkeypatch):
    monkeypatch.setattr(storage_cleanup.settings, "MINIO_BUCKET", "atp")
    monkeypatch.setattr(
        storage_cleanup.minio_client,
        "list_objects",
        lambda prefix: {
            "screenshots/": [
                _FakeObject("screenshots/runs/1/a.png", None, size=5),
                _FakeObject("screenshots/runs/1/b.png", None, size=7),
            ],
            "reports/": [_FakeObject("reports/runs/1/report.html", None, size=11)],
            "apks/": [],
            "scripts/": [_FakeObject("scripts/cases/1/test.py", None, size=13)],
            "performance/": [_FakeObject("performance/runs/8/summary.json", None, size=17)],
        }.get(prefix, []),
    )

    result = storage_cleanup.get_storage_stats(object())

    assert result.bucket == "atp"
    assert result.total_object_count == 5
    assert result.total_bytes == 53
    assert [(item.prefix, item.object_count, item.total_bytes) for item in result.prefixes] == [
        ("screenshots/", 2, 12),
        ("reports/", 1, 11),
        ("apks/", 0, 0),
        ("scripts/", 1, 13),
        ("performance/", 1, 17),
    ]


def test_preview_storage_cleanup_separates_deletable_blocked_and_orphan(monkeypatch):
    now = datetime(2026, 4, 3, tzinfo=timezone.utc)
    old = now - timedelta(days=31)
    new = now - timedelta(days=1)

    monkeypatch.setattr(storage_cleanup.settings, "FILE_RETENTION_DAYS", 30)
    monkeypatch.setattr(
        storage_cleanup.minio_client,
        "list_objects",
        lambda prefix: {
            "screenshots/": [
                _FakeObject("screenshots/runs/1/old.png", old),
                _FakeObject("screenshots/runs/1/new.png", new),
            ],
            "scripts/": [_FakeObject("scripts/cases/3/script.py", old)],
            "apks/": [],
            "reports/": [],
        }.get(prefix, []),
    )
    monkeypatch.setattr(storage_cleanup, "_cutoff", lambda retention_days=None: now - timedelta(days=30))

    responses = [
        [],
        [(11, "http://minio:9000/atp/screenshots/runs/1/orphan.png")],
        [(3, {"script_path": "scripts/cases/3/script.py"})],
        [],
        [],
        [],
    ]
    session = _FakeSession(responses=responses)

    result = storage_cleanup.preview_storage_cleanup(session)

    assert result.scanned_object_count == 3
    assert result.expired_object_count == 2
    assert [item.object_name for item in result.deletable_objects] == ["screenshots/runs/1/old.png"]
    assert [item.object_name for item in result.blocked_objects] == ["scripts/cases/3/script.py"]
    assert result.orphan_reference_count == 1
    assert result.orphan_references[0].object_name == "screenshots/runs/1/orphan.png"


def test_preview_storage_cleanup_includes_additional_db_reference_types(monkeypatch):
    now = datetime(2026, 4, 3, tzinfo=timezone.utc)
    old = now - timedelta(days=31)

    monkeypatch.setattr(storage_cleanup.settings, "FILE_RETENTION_DAYS", 30)
    monkeypatch.setattr(
        storage_cleanup.minio_client,
        "list_objects",
        lambda prefix: {
            "screenshots/": [],
            "scripts/": [_FakeObject("scripts/suites/2/data.csv", old)],
            "apks/": [_FakeObject("apks/projects/7/build.apk", old)],
            "reports/": [],
        }.get(prefix, []),
    )
    monkeypatch.setattr(storage_cleanup, "_cutoff", lambda retention_days=None: now - timedelta(days=30))

    responses = [
        [],
        [],
        [(9, {"apk_object_name": "apks/projects/7/build.apk"})],
        [(2, {"type": "csv", "object_name": "scripts/suites/2/data.csv"})],
        [],
        [],
    ]
    session = _FakeSession(responses=responses)

    result = storage_cleanup.preview_storage_cleanup(session)

    assert [item.object_name for item in result.blocked_objects] == [
        "apks/projects/7/build.apk",
        "scripts/suites/2/data.csv",
    ]
    assert result.deletable_count == 0


def test_performance_artifacts_are_scanned_blocked_and_repairable(monkeypatch):
    now = datetime(2026, 5, 29, tzinfo=timezone.utc)
    old = now - timedelta(days=31)
    deleted = []

    monkeypatch.setattr(storage_cleanup.settings, "FILE_RETENTION_DAYS", 30)
    monkeypatch.setattr(
        storage_cleanup.minio_client,
        "list_objects",
        lambda prefix: {
            "performance/": [
                _FakeObject("performance/scripts/2/homepage.js", old),
                _FakeObject("performance/runs/8/delete-me-summary.json", old),
            ],
        }.get(prefix, []),
    )
    monkeypatch.setattr(storage_cleanup.minio_client, "delete_file", lambda object_name: deleted.append(object_name))
    monkeypatch.setattr(storage_cleanup, "_cutoff", lambda retention_days=None: now - timedelta(days=30))

    performance_run = types.SimpleNamespace(raw_result_object_name="performance/runs/8/missing-summary.json")
    responses = [
        [],
        [],
        [],
        [],
        [(2, "performance/scripts/2/homepage.js")],
        [(8, "performance/runs/8/missing-summary.json")],
        [],
        [],
        [],
        [],
        [],
        [],
        [(2, "performance/scripts/2/homepage.js")],
        [(8, "performance/runs/8/missing-summary.json")],
    ]
    session = _FakeSession(
        responses=responses,
        get_map={("PerformanceRun", 8): performance_run},
    )

    preview = storage_cleanup.preview_storage_cleanup(session, prefixes=["performance/"])
    execute = storage_cleanup.execute_storage_cleanup(
        session,
        object_names=[item.object_name for item in preview.deletable_objects],
        repair_orphan_references=True,
    )

    assert [item.object_name for item in preview.blocked_objects] == ["performance/scripts/2/homepage.js"]
    assert [item.object_name for item in preview.deletable_objects] == ["performance/runs/8/delete-me-summary.json"]
    assert [item.object_name for item in preview.orphan_references] == ["performance/runs/8/missing-summary.json"]
    assert deleted == ["performance/runs/8/delete-me-summary.json"]
    assert execute.repaired_reference_count == 1
    assert performance_run.raw_result_object_name is None


def test_preview_and_execute_cleanup_remain_consistent(monkeypatch):
    now = datetime(2026, 4, 3, tzinfo=timezone.utc)
    old = now - timedelta(days=31)

    deleted = []
    monkeypatch.setattr(storage_cleanup.settings, "FILE_RETENTION_DAYS", 30)
    monkeypatch.setattr(
        storage_cleanup.minio_client,
        "list_objects",
        lambda prefix: {
            "screenshots/": [
                _FakeObject("screenshots/runs/1/delete-me.png", old),
                _FakeObject("screenshots/runs/1/blocked.png", old),
            ],
            "reports/": [],
            "apks/": [],
            "scripts/": [],
        }.get(prefix, []),
    )
    monkeypatch.setattr(storage_cleanup.minio_client, "delete_file", lambda object_name: deleted.append(object_name))
    monkeypatch.setattr(storage_cleanup, "_cutoff", lambda retention_days=None: now - timedelta(days=30))

    responses = [
        [],
        [(11, "screenshots/runs/1/blocked.png"), (12, "screenshots/runs/1/orphan.png")],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [(11, "screenshots/runs/1/blocked.png"), (12, "screenshots/runs/1/orphan.png")],
        [],
        [],
        [],
        [],
    ]
    step_blocked = types.SimpleNamespace(screenshot_url="screenshots/runs/1/blocked.png")
    step_orphan = types.SimpleNamespace(screenshot_url="screenshots/runs/1/orphan.png")
    get_map = {
        ("StepResult", 11): step_blocked,
        ("StepResult", 12): step_orphan,
    }
    session = _FakeSession(responses=responses, get_map=get_map)

    preview = storage_cleanup.preview_storage_cleanup(session)
    execute = storage_cleanup.execute_storage_cleanup(
        session,
        object_names=[item.object_name for item in preview.deletable_objects],
        repair_orphan_references=True,
    )

    assert [item.object_name for item in preview.deletable_objects] == ["screenshots/runs/1/delete-me.png"]
    assert [item.object_name for item in preview.blocked_objects] == ["screenshots/runs/1/blocked.png"]
    assert [item.object_name for item in preview.orphan_references] == ["screenshots/runs/1/orphan.png"]
    assert deleted == ["screenshots/runs/1/delete-me.png"]
    assert execute.requested_count == preview.deletable_count
    assert execute.deleted_count == preview.deletable_count
    assert execute.skipped_referenced_count == 0
    assert execute.repaired_reference_count == preview.orphan_reference_count
    assert step_blocked.screenshot_url == "screenshots/runs/1/blocked.png"
    assert step_orphan.screenshot_url is None
    assert session.commit_calls == 1


def test_execute_storage_cleanup_deletes_only_unreferenced_and_repairs_orphans(monkeypatch):
    deleted = []
    monkeypatch.setattr(
        storage_cleanup.minio_client,
        "list_objects",
        lambda prefix: {
            "screenshots/": [_FakeObject("screenshots/runs/1/old.png", None)],
            "reports/": [],
            "apks/": [_FakeObject("apks/projects/1/app.apk", None)],
            "scripts/": [],
        }.get(prefix, []),
    )
    monkeypatch.setattr(storage_cleanup.minio_client, "delete_file", lambda object_name: deleted.append(object_name))

    step_result = types.SimpleNamespace(screenshot_url="http://minio:9000/atp/screenshots/runs/1/orphan.png")
    responses = [
        [(8, "apks/projects/1/app.apk")],
        [(11, "http://minio:9000/atp/screenshots/runs/1/orphan.png")],
        [],
        [],
        [],
        [],
    ]
    get_map = {
        ("StepResult", 11): step_result,
    }
    session = _FakeSession(responses=responses, get_map=get_map)

    result = storage_cleanup.execute_storage_cleanup(
        session,
        object_names=["screenshots/runs/1/old.png", "apks/projects/1/app.apk", "reports/missing.html"],
        repair_orphan_references=True,
    )

    assert deleted == ["screenshots/runs/1/old.png"]
    assert result.deleted_count == 1
    assert result.skipped_referenced_count == 1
    assert result.missing_count == 1
    assert result.repaired_reference_count == 1
    assert step_result.screenshot_url is None
    assert session.commit_calls == 1


def test_execute_storage_cleanup_repairs_case_and_suite_orphans(monkeypatch):
    monkeypatch.setattr(
        storage_cleanup.minio_client,
        "list_objects",
        lambda prefix: {
            "screenshots/": [],
            "reports/": [],
            "apks/": [],
            "scripts/": [],
        }.get(prefix, []),
    )

    case_row = types.SimpleNamespace(
        config={"script_path": "scripts/cases/3/script.py", "apk_object_name": "apks/projects/7/build.apk"}
    )
    suite_row = types.SimpleNamespace(parameterization={"type": "csv", "object_name": "scripts/suites/2/data.csv"})
    responses = [
        [],
        [],
        [(3, {"script_path": "scripts/cases/3/script.py", "apk_object_name": "apks/projects/7/build.apk"})],
        [(2, {"type": "csv", "object_name": "scripts/suites/2/data.csv"})],
        [],
        [],
    ]
    get_map = {
        ("TestCase", 3): case_row,
        ("TestSuite", 2): suite_row,
    }
    session = _FakeSession(responses=responses, get_map=get_map)

    result = storage_cleanup.execute_storage_cleanup(
        session,
        object_names=[],
        repair_orphan_references=True,
    )

    assert result.repaired_reference_count == 3
    assert case_row.config == {}
    assert suite_row.parameterization == {"type": "csv"}
    assert session.commit_calls == 1


def test_execute_storage_cleanup_repairs_mobile_orphans(monkeypatch):
    monkeypatch.setattr(
        storage_cleanup.minio_client,
        "list_objects",
        lambda prefix: {
            "screenshots/": [],
            "reports/": [],
            "apks/": [],
            "scripts/": [],
        }.get(prefix, []),
    )

    incident_row = types.SimpleNamespace(artifact_path="reports/mobile/1/crash.log")
    artifact_row = types.SimpleNamespace(file_path="reports/mobile/1/metrics.json")
    responses = [
        [],
        [],
        [],
        [],
        [],
        [],
        [(5, "reports/mobile/1/crash.log")],
        [(6, "reports/mobile/1/metrics.json")],
    ]
    get_map = {
        ("MobileIncident", 5): incident_row,
        ("MobileRunArtifact", 6): artifact_row,
    }
    session = _FakeSession(responses=responses, get_map=get_map)

    result = storage_cleanup.execute_storage_cleanup(
        session,
        object_names=[],
        repair_orphan_references=True,
    )

    assert result.repaired_reference_count == 2
    assert incident_row.artifact_path is None
    assert artifact_row.file_path == ""
    assert session.commit_calls == 1


def test_execute_storage_cleanup_does_not_count_delete_failures_as_referenced_skips(monkeypatch):
    monkeypatch.setattr(
        storage_cleanup.minio_client,
        "list_objects",
        lambda prefix: {
            "screenshots/": [_FakeObject("screenshots/runs/1/delete-fail.png", None)],
            "reports/": [],
            "apks/": [],
            "scripts/": [],
        }.get(prefix, []),
    )

    def fake_delete_file(_object_name: str):
        raise RuntimeError("delete failed")

    monkeypatch.setattr(storage_cleanup.minio_client, "delete_file", fake_delete_file)

    responses = [[], [], [], [], [], []]
    session = _FakeSession(responses=responses)

    result = storage_cleanup.execute_storage_cleanup(
        session,
        object_names=["screenshots/runs/1/delete-fail.png"],
        repair_orphan_references=False,
    )

    assert result.deleted_count == 0
    assert result.skipped_referenced_count == 0
    assert result.skipped_objects == ["screenshots/runs/1/delete-fail.png"]
    assert result.missing_count == 0
    assert session.commit_calls == 1


def test_select_size_eviction_returns_empty_when_under_limit():
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    objects = [
        ("a", now - timedelta(days=2), 1024**3),
        ("b", now - timedelta(days=1), 1024**3),
    ]

    # 总量 2GB，上限 5GB，无需淘汰
    assert storage_cleanup._select_size_eviction(objects, 5 * 1024**3) == set()


def test_select_size_eviction_returns_empty_when_max_zero():
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    objects = [("a", now, 1024**3)]

    assert storage_cleanup._select_size_eviction(objects, 0) == set()


def test_select_size_eviction_picks_oldest_first():
    base = datetime(2026, 5, 18, tzinfo=timezone.utc)
    objects = [
        ("newest", base - timedelta(days=1), 1024**3),
        ("oldest", base - timedelta(days=10), 1024**3),
        ("middle", base - timedelta(days=5), 1024**3),
    ]

    # 总量 3GB，上限 1GB → 需要淘汰 2GB（两个最旧的）
    evicted = storage_cleanup._select_size_eviction(objects, 1 * 1024**3)
    assert evicted == {"oldest", "middle"}


def test_preview_storage_cleanup_evicts_when_size_exceeds_max(monkeypatch):
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    new = now - timedelta(days=1)  # 在 retention 范围内
    older = now - timedelta(days=5)

    monkeypatch.setattr(storage_cleanup.settings, "FILE_RETENTION_DAYS", 30)
    monkeypatch.setattr(
        storage_cleanup.minio_client,
        "list_objects",
        lambda prefix: {
            "screenshots/": [
                _FakeObject("screenshots/keep.png", new, size=512 * 1024**2),
                _FakeObject("screenshots/evict-1.png", older, size=512 * 1024**2),
                _FakeObject("screenshots/evict-2.png", older - timedelta(days=1), size=512 * 1024**2),
            ],
        }.get(prefix, []),
    )
    monkeypatch.setattr(storage_cleanup, "_cutoff", lambda retention_days=None: now - timedelta(days=30))

    # 3 个对象总 1.5GB，max_size_gb=0.5 → 需要淘汰 1GB（最旧的 2 个）
    policy = storage_cleanup.PolicyEntry(prefix="screenshots/", retention_days=30, max_size_gb=0.5)
    responses = [[], [], [], [], [], []]
    session = _FakeSession(responses=responses)

    result = storage_cleanup.preview_storage_cleanup(session, policies=[policy])

    assert result.size_evicted_count == 2
    assert result.expired_object_count == 0  # 都在 retention 内
    deletable_names = {item.object_name for item in result.deletable_objects}
    assert deletable_names == {"screenshots/evict-1.png", "screenshots/evict-2.png"}


def test_preview_storage_cleanup_unions_retention_and_size_eviction(monkeypatch):
    now = datetime(2026, 5, 18, tzinfo=timezone.utc)
    expired = now - timedelta(days=40)  # 超 retention
    fresh = now - timedelta(days=1)

    monkeypatch.setattr(storage_cleanup.settings, "FILE_RETENTION_DAYS", 30)
    monkeypatch.setattr(
        storage_cleanup.minio_client,
        "list_objects",
        lambda prefix: {
            "screenshots/": [
                _FakeObject("screenshots/expired.png", expired, size=100 * 1024**2),
                _FakeObject("screenshots/fresh-big-a.png", fresh, size=600 * 1024**2),
                _FakeObject("screenshots/fresh-big-b.png", fresh - timedelta(hours=1), size=600 * 1024**2),
            ],
        }.get(prefix, []),
    )
    monkeypatch.setattr(storage_cleanup, "_cutoff", lambda retention_days=None: now - timedelta(days=30))

    # expired.png 因 retention 淘汰；fresh-big-* 总 1.2GB > max 0.5GB → fresh-big-b 是最旧加入 size eviction
    policy = storage_cleanup.PolicyEntry(prefix="screenshots/", retention_days=30, max_size_gb=0.5)
    responses = [[], [], [], [], [], []]
    session = _FakeSession(responses=responses)

    result = storage_cleanup.preview_storage_cleanup(session, policies=[policy])

    deletable_names = {item.object_name for item in result.deletable_objects}
    # expired 因 retention 淘汰；fresh-big-a 不该被淘汰（最新的且未超过 retention 与 size 综合后）；fresh-big-b 因 size eviction 淘汰
    # 单单 size eviction：max_size_bytes = 0.5GB ≈ 537MB；total = 100+600+600 = 1300MB
    # 按 last_modified 升序排：expired(40d) → fresh-big-b(1d-1h) → fresh-big-a(1d)
    # 累计：expired 100MB → total 1200，仍 > 537 → fresh-big-b 600MB → total 600，仍 > 537 → fresh-big-a 600 → total 0 ≤ 537 stop
    # 所以 size_evicted = {expired, fresh-big-b, fresh-big-a}（但 expired 也已经在 retention 集合）
    # 并集 = {expired, fresh-big-a, fresh-big-b}
    assert deletable_names == {
        "screenshots/expired.png",
        "screenshots/fresh-big-a.png",
        "screenshots/fresh-big-b.png",
    }
    assert result.expired_object_count == 1
    assert result.size_evicted_count == 3  # 包含 expired 也参与了 size eviction
