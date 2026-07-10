# Worker State, Retry, Timeout, and Recovery Policy

This document defines the runtime policy for Celery workers and persisted run state. Use it when changing `backend/app/worker/*`, execution models, or cleanup tasks.

## State Model

### Case / Suite / Plan Execution

| State | Meaning | Owner | Next States |
| --- | --- | --- | --- |
| `pending` | API created a run record and queued a Celery task. | API route | `running`, `error` by stale pending cleanup |
| `running` | Worker has accepted the run and started execution. | Worker task | `passed`, `failed`, `error` |
| `passed` | Execution completed and all required checks passed. | Executor / suite / plan orchestration | terminal |
| `failed` | Execution completed but assertions, child cases, or pass-rate policy failed. | Executor / suite / plan orchestration | terminal |
| `error` | Infrastructure, configuration, missing resource, timeout cleanup, or unhandled exception prevented normal execution. | Worker / cleanup / executor | terminal |
| `skipped` | Child item was not run because fail-fast or policy stopped a parent run. | Suite / plan orchestration | terminal child item only |

`PerformanceRun` uses its own string enum but follows the same pattern: `pending -> running -> success|failed|cancelled`.

## Retry Policy

| Task Type | Retry Rule | Reason |
| --- | --- | --- |
| `run_test_case`, `run_test_suite`, `run_test_plan` | Do not auto-retry. | They mutate run records and may call external systems; retrying can duplicate child runs, reports, or bug creation. |
| `diagnose_step_failure`, `diagnose_run_failure` | Do not auto-retry. | LLM diagnosis is best-effort and non-idempotent from the user's perspective. |
| `aggregate_healing_feedback` | Retry once after 300 seconds. | Aggregation is idempotent and safe to rerun. |
| `backup_postgres_daily`, `backup_postgres_weekly` | Retry twice after 300 seconds. | Backup script failure is operational and retryable. |
| cleanup / alert / scan tasks | Return structured failure summaries or log and continue unless explicitly declared retryable. | Maintenance tasks should not poison queues on persistent external failures. |

New tasks must choose one of these categories and document the choice in the task docstring or this file.

## Timeout Policy

Celery worker defaults are defined in `backend/app/worker/celery_app.py`:

- `task_soft_time_limit = 1500` seconds.
- `task_time_limit = 1800` seconds.
- `task_track_started = True`.
- `worker_prefetch_multiplier = 1`.
- `worker_max_tasks_per_child = 50`.

Soft timeouts emit `celery_soft_timeout` logs and `atp_celery_timeouts_total{kind="soft"}`. Hard terminations emit `celery_hard_timeout` logs and `atp_celery_timeouts_total{kind="hard"}` through `backend/app/worker/timeout_alerts.py`.

Timeout signals do not directly mutate run rows because Celery signal payloads do not reliably include ATP run IDs for every task. Recovery is handled by stale run cleanup and terminal-state cleanup.

## Recovery Policy

| Scenario | Recovery Path |
| --- | --- |
| Celery task never starts after API created a run | `cleanup_stale_pending_runs` marks old `pending` `TestRun`, `SuiteRun`, and `PlanRun` rows as `error`. |
| Worker crashes before commit to `running` | Same stale pending cleanup path. |
| Worker crashes after setting `running` | Operator investigates via worker logs/metrics; manual remediation may mark or rerun. Future automatic stale-running recovery must be added with heartbeat evidence before mutating rows. |
| Soft/hard timeout | Timeout alert/metric is emitted; run row recovery follows the stale-state policy above. |
| Maintenance task failure | Task returns a structured summary or logs an exception; it should not leave partial user-facing run state without a compensating cleanup path. |

## Cancellation Policy

There is no general user-facing cancel endpoint for case/suite/plan execution yet. Until it exists:

- Do not set case/suite/plan runs to a `cancelled` state; those enums do not include it.
- Use `error` with a clear `error_message` for forced operational termination.
- If a future cancel endpoint is added, add enum/model/API support and a cleanup contract in this document first.

## Implementation Checklist

When adding or changing a worker task:

1. Pick the queue in `task_routes`.
2. Define retry behavior explicitly.
3. Ensure persisted rows follow the state model.
4. Commit state transitions before long-running external work starts.
5. Catch exceptions and write a terminal status for user-facing runs.
6. Add cleanup/recovery behavior if a task can leave `pending`.
7. Add tests for route, retry, timeout, and stale-state behavior.

## Known Follow-Ups

- Split suite/plan execution orchestration out of `worker/tasks.py` into service helpers before adding richer cancellation or stale-running recovery.
- Add task/run correlation metadata for timeout signals if automatic stale-running recovery becomes necessary.
- Consider a dedicated `cancelled` state only after API, worker, and reporting semantics are designed together.

Scheduled plan incident triage and controlled recovery are documented in `docs/scheduled-plan-incident-drill.md`.
