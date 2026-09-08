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

The five user-facing long-running tasks (`run_test_case`, `run_test_suite`, `run_test_plan`, `run_mobile_special_task`, and `run_performance_test`) explicitly set both Celery limits to `0`. They use renewable database leases instead, so legitimate runs longer than 30 minutes are not killed by a wall-clock threshold. Other tasks keep the defaults above.

Soft timeouts emit `celery_soft_timeout` logs and `atp_celery_timeouts_total{kind="soft"}`. Hard terminations emit `celery_hard_timeout` logs and `atp_celery_timeouts_total{kind="hard"}` through `backend/app/worker/timeout_alerts.py`.

Timeout signals for tasks that retain the defaults do not directly mutate run rows because Celery signal payloads do not reliably include ATP run IDs for every task. Long-running execution recovery is driven by its persisted lease and fencing token.

## Recovery Policy

| Scenario | Recovery Path |
| --- | --- |
| Celery task never starts after API created a run | `cleanup_stale_pending_runs` marks old `pending` `TestRun`, `SuiteRun`, and `PlanRun` rows as `error`. |
| Worker crashes before commit to `running` | Same stale pending cleanup path. |
| Worker crashes after setting `running` | `reconcile_expired_execution_run_leases` locks the expired lease and changes a still-active run to its domain-safe terminal failure state. |
| Duplicate or delayed Celery delivery | The permanent `(task_type, run_id)` lease record rejects it; an explicit retry must use a newly created run ID. |
| Old Worker returns after lease recovery | Its fencing token can no longer release the lease; the exit guard restores the lost-worker failure state instead of accepting the stale result. |
| Soft/hard timeout on a non-execution task | Timeout alert/metric is emitted; task-specific cleanup remains responsible for persisted state. |
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
6. Add cleanup/recovery behavior if a task can leave `pending` or `running`.
7. Long-running execution tasks must use `execution_run_lease`; never add a fixed duration as a substitute for worker-loss evidence.
8. Add tests for route, retry, timeout, and stale-state behavior.

## Known Follow-Ups

- Split suite/plan execution orchestration out of `worker/tasks.py` into service helpers before adding richer cancellation.
- Add an operations page or metric for active/expired execution leases if production triage needs direct visibility.
- Consider a dedicated `cancelled` state only after API, worker, and reporting semantics are designed together.

Scheduled plan incident triage and controlled recovery are documented in `docs/scheduled-plan-incident-drill.md`.
