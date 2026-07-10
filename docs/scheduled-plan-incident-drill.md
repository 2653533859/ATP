# Scheduled Plan Failure Incident Drill

> Updated: 2026-07-10
> Scope: failed or stuck cron-triggered `PlanRun` execution in staging or production.
> Safety: inject failures only in staging. Production use is triage and recovery, not fault injection.

## Purpose And Success Criteria

This drill proves that an operator can trace one scheduled plan from Celery Beat through Redis, worker execution, database state, notifications, and bug-tracker side effects without creating duplicate runs or external tickets.

The drill succeeds when the operator can:

- Identify the plan, `PlanRun`, `trace_id`, expected schedule, and first failing child run.
- Distinguish scheduler, broker, worker, test-target, notification, and bug-tracker failures.
- Preserve the original failed row and collect evidence before recovery.
- Recover with a fresh supported trigger only after proving the original task cannot still execute.
- Account for notification and bug side effects, including partial failures and duplicates.

## Runtime Contract

The current implementation has these invariants:

- Celery Beat runs `check_cron_plans` every 60 seconds.
- `check_cron_plans` creates a `plan_runs` row with `trigger_type=cron` and `status=pending`, advances `test_plans.next_run_at`, then enqueues `run_test_plan` on the `default` queue.
- Redis DB 0 is the Celery broker, Redis DB 1 is the result backend, and Redis DB 2 is used for best-effort run events and JSON caches.
- PostgreSQL `plan_runs`, `suite_runs`, and `test_runs` rows are the execution source of truth. Redis pub/sub is not a durable execution ledger.
- `run_test_plan` has no automatic retry because replay can duplicate child runs, notifications, reports, or bugs.
- Stale `pending` rows can be marked `error` by `cleanup_stale_pending_runs`; stale `running` rows have no automatic recovery.
- Auto bug creation runs before the terminal plan transaction is committed. Results appear in `result_summary.auto_bugs`; failures appear in `result_summary.auto_bugs_error`.
- Notifications run after the terminal plan commit. Delivery is best-effort and failures are logged; there is currently no persistent notification-delivery table.

## Drill Preparation

Use a staging project with disposable integrations:

- One enabled cron plan containing a deterministic passing case and a deterministic failing case.
- A short, known cron window and a valid `next_run_at`.
- A sandbox email/webhook notification config scoped to the plan and including `failed` in `status_filters`.
- A sandbox bug tracker when `auto_create_bugs` is enabled.
- An incident owner, observer, start time, expected plan ID, and rollback contact.

Record identifiers:

```bash
export PLAN_ID=<PLAN_ID>
export PLAN_RUN_ID=<PLAN_RUN_ID>
export TRACE_ID=<TRACE_ID>
```

Do not use production recipients, production issue projects, or destructive target systems for the drill.

## First Five Minutes

1. Freeze changes to the affected plan and do not trigger it again.
2. Record the detection time, plan ID, run ID, trace ID, environment, and expected schedule window.
3. Check whether a cron `PlanRun` exists. No row points to Beat/schedule selection; `pending` points to broker/worker pickup; `running` points to worker/target execution; terminal `failed` or `error` points to child results or orchestration.
4. Check Celery Beat and worker health before restarting anything.
5. Capture notification and bug-tracker evidence before attempting recovery.

## Celery And Beat Checks

Run from a backend container or environment with the ATP settings loaded:

```bash
celery -A app.worker.celery_app inspect ping
celery -A app.worker.celery_app inspect active_queues
celery -A app.worker.celery_app inspect registered
celery -A app.worker.celery_app inspect active
celery -A app.worker.celery_app inspect reserved
celery -A app.worker.celery_app inspect scheduled
```

Confirm:

- Exactly one Beat instance is active.
- Beat logs show `check_cron_plans` near the expected minute.
- At least one worker consumes the `default` queue.
- `check_cron_plans` and `run_test_plan` are registered.
- The affected `run_test_plan` is not simultaneously active and reserved on different workers.
- Worker logs can be searched by `PlanRun <PLAN_RUN_ID>` or `TRACE_ID`.

Interpretation:

| Observation | Likely boundary | Next check |
| --- | --- | --- |
| No `PlanRun` row after two Beat intervals | Beat stopped, plan not due, disabled plan, invalid schedule, or empty suite list | Plan metadata and Beat logs |
| `pending`, task visible in Redis/default queue | Worker unavailable or not consuming `default` | Worker queues and capacity |
| `pending`, task absent from queue/active/reserved | Dispatch failure or task already lost/consumed | Beat logs, broker logs, stale-pending cleanup |
| `running` with active task | Target, environment, suite, or case execution | Child run rows and worker trace |
| `running` with no active task | Worker crash or hard timeout after state transition | Timeout logs/metrics and controlled remediation |
| `failed` | Test failures completed normally | Child rows, notification, and bug effects |
| `error` | Orchestration error or stale-pending cleanup | `error_message`, worker, and cleanup logs |

## Redis Checks

Use the configured password through the normal secret mechanism; never paste it into incident notes.

```bash
redis-cli -n 0 PING
redis-cli -n 0 TYPE default
redis-cli -n 0 LLEN default
redis-cli -n 1 PING
redis-cli -n 2 PING
redis-cli -n 2 PUBSUB NUMSUB "atp:run:<CASE_RUN_ID>"
```

Confirm:

- DB 0 responds and the `default` queue length is not growing without active consumers.
- DB 1 responds; result-backend loss may reduce Celery diagnostics but does not override PostgreSQL run state.
- DB 2 responds; zero pub/sub subscribers can explain missing live UI updates but does not explain a missing or stuck `PlanRun`.
- Redis memory pressure, eviction, reconnect, and blocked-client logs are captured for the incident window.

Do not delete Celery keys, flush a Redis database, or manually requeue serialized messages during triage.

## Database State Checks

Open a read-only `psql` session and replace placeholders explicitly:

```sql
SELECT id, project_id, status, schedule_type, cron_expression, is_enabled,
       last_run_at, next_run_at, auto_create_bugs
FROM test_plans
WHERE id = <PLAN_ID>;

SELECT id, plan_id, trigger_type, status, trace_id, created_at, updated_at,
       duration_ms, error_message, suite_run_ids, result_summary
FROM plan_runs
WHERE plan_id = <PLAN_ID>
ORDER BY created_at DESC
LIMIT 10;

SELECT id, suite_id, status, trace_id, error_message, case_run_ids
FROM suite_runs
WHERE id IN (<SUITE_RUN_IDS>);

SELECT id, case_id, status, trace_id, error_message, result_summary
FROM test_runs
WHERE id IN (<CASE_RUN_IDS>);
```

Validate:

- The incident row has `trigger_type=cron` and the expected `trace_id`.
- `next_run_at` advanced only once for the schedule window; multiple runs for the same window indicate duplicate Beat or dispatch behavior.
- `suite_run_ids` and child `case_run_ids` account for every executed suite/case; `skipped` entries match the plan fail strategy.
- `result_summary.total/passed/failed/error` agrees with child terminal states.
- `pending` older than `STALE_PENDING_TIMEOUT_MINUTES` is eligible for cleanup; `running` is not repaired by that cleanup task.

PostgreSQL remains authoritative if UI state, Celery result state, or Redis events disagree.

## Notification Side Effects

Check enabled `notification_configs` for the project without exposing decrypted secrets:

- `scope=plans` targets the affected plan, or `scope=all` is intended.
- `plan_ids` is empty or contains `PLAN_ID`.
- `status_filters` is empty or includes the terminal status.
- Email recipients or sandbox webhooks are the expected drill destinations.

Search worker logs for:

- `Plan notification failed`
- `通知发送失败`
- `Plan report HTML build failed`
- Channel-specific SMTP, WeCom, or DingTalk errors

A terminal `PlanRun` does not prove delivery. Because delivery attempts are not persisted, retain provider/webhook logs or the received test message as evidence. Do not rerun the plan solely to resend a notification; use the notification test-send endpoint after fixing the channel.

## Bug-Tracker Side Effects

When `auto_create_bugs=true`, inspect `plan_runs.result_summary`:

- `auto_bugs` lists created or deduplicated bugs and attachment status.
- `auto_bugs_error` records a best-effort integration failure.
- Absence of both means auto bug creation was disabled, no tracker was enabled, or no eligible failed/error child run was found.

Cross-check each entry against the sandbox tracker:

- The bug title matches `[ATP] <case name> 执行失败`.
- `duplicate=true` references the existing issue rather than creating another.
- New bugs contain the ATP run ID and expected environment/error context.
- `attachment_uploaded=false` is classified separately from bug creation failure.

Do not replay `run_test_plan` to repair bug creation. Use the supported manual bug-link/create workflow after the tracker is healthy, and record any orphan or duplicate external issue in the incident.

## Recovery Decision

Before any rerun, prove all of the following:

- The original task is absent from Celery `active`, `reserved`, and `scheduled` output.
- No worker is still writing child rows for the original trace.
- The original row and side effects have been captured.
- The scheduler/broker/worker/target root cause has been fixed.
- The next cron window will not collide with the recovery run.

Recovery rules:

- For stale `pending`, allow `cleanup_stale_pending_runs` to mark the old row `error`, then trigger a fresh run through the API/UI or wait for the next cron window.
- For orphaned `running`, quiesce the worker first. There is no automatic stale-running recovery; use an approved transaction to mark the row `error` only after proving the task cannot resume.
- Never call `run_test_plan.delay` manually against the same `PLAN_RUN_ID`.
- Never rewrite a `failed` run to `passed`; fix the cause and create a new run.
- Disable the plan temporarily when duplicate Beat instances, an invalid cron, or a dangerous target would make the next window unsafe.

## Controlled Drill Scenarios

Run at least the first scenario quarterly in staging:

1. Deterministic case failure: confirm `PlanRun=failed`, child states reconcile, notification strategy matches, and bug dedup/create evidence is complete.
2. Notification endpoint failure: use a sandbox endpoint returning an error; confirm the plan remains terminal and notification failure is visible in logs.
3. Worker pickup delay: isolate a staging worker from `default`, observe `pending` and broker depth, restore the worker before the stale timeout, and confirm one execution only.
4. Worker loss after `running`: isolated staging only; confirm the lack of automatic stale-running recovery and execute the approved manual remediation path.

Do not inject PostgreSQL, Redis, SMTP, or tracker outages into production.

## Exit Criteria And Incident Record

Close the drill or incident only when:

- Root cause and failure boundary are recorded.
- Original and recovery run IDs are linked.
- Celery, Redis, database, notification, and bug-tracker checks each have evidence or an explicit not-applicable reason.
- No task remains orphaned and no duplicate run/bug remains unowned.
- The next scheduled execution is enabled, safe, and observed or assigned to an owner.
- Follow-up actions have an owner and due date.

Record:

```text
Incident/drill ID:
Environment and time window:
Owner / observer:
Plan ID / PlanRun ID / trace_id:
Expected cron / observed next_run_at:
Detection source:
Celery/Beat evidence:
Redis evidence:
Database state and child reconciliation:
Notification evidence:
Bug-tracker evidence:
Root cause:
Recovery action / recovery run ID:
Duplicate or orphan cleanup:
Next schedule observation:
Follow-up owner / due date:
```

Related references: `docs/worker-lifecycle.md`, `docs/celery-queues.md`, `docs/slo-guide.md`, and `docs/flaky-governance.md`.
