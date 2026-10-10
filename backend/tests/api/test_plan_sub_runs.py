from app.schemas.plan import PlanSubRunsPageOut, PlanSubRunsSummary


def test_plan_sub_runs_summary_calculation():
    raw_items = [
        {"suite_id": 1, "status": "pending"},
        {"suite_id": 2, "status": "passed"},
        {"suite_id": 3, "status": "failed"},
        {"suite_id": 4, "status": "error"},
        {"suite_id": 5, "status": "running"},
        {"suite_id": 6, "status": "skipped"},
    ]
    summary = PlanSubRunsSummary(
        total=len(raw_items),
        pending=sum(1 for item in raw_items if item.get("status") == "pending"),
        passed=sum(1 for item in raw_items if item.get("status") == "passed"),
        failed=sum(1 for item in raw_items if item.get("status") == "failed"),
        error=sum(1 for item in raw_items if item.get("status") == "error"),
        running=sum(1 for item in raw_items if item.get("status") == "running"),
        skipped=sum(1 for item in raw_items if item.get("status") == "skipped"),
    )
    assert summary.total == 6
    assert summary.pending == 1
    assert summary.passed == 1
    assert summary.failed == 1
    assert summary.error == 1
    assert summary.running == 1
    assert summary.skipped == 1


def test_plan_sub_runs_pagination_and_filter():
    raw_items = [{"suite_id": i, "status": "passed" if i % 2 == 0 else "failed"} for i in range(1, 101)]
    # Filter by failed
    failed_items = [item for item in raw_items if item.get("status") == "failed"]
    assert len(failed_items) == 50

    # Paginate page 1 (limit 20)
    paged = failed_items[0:20]
    out = PlanSubRunsPageOut(
        total=len(failed_items),
        offset=0,
        limit=20,
        items=paged,
        summary=PlanSubRunsSummary(
            total=len(raw_items),
            passed=50,
            failed=50,
        ),
    )
    assert out.total == 50
    assert len(out.items) == 20
    assert out.offset == 0
    assert out.limit == 20

    # Paginate page 2 (offset 20, limit 20)
    paged_2 = failed_items[20:40]
    assert len(paged_2) == 20
