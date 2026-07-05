# ATP Domain Boundaries

This document defines the backend domain ownership rules for ATP. The codebase is still organized mostly by technical layer (`api`, `models`, `schemas`, `services`, `worker`), so this file is the boundary map to use when adding features, moving code, or reviewing cross-domain changes.

## Boundary Principles

1. API modules validate request shape, permissions, and orchestration only. Domain decisions belong in services or worker helpers.
2. Models own persisted state. A model should not import API modules, worker tasks, or notification/reporting helpers.
3. Services may call other services through explicit inputs and return values. Avoid reading another domain's private JSON details unless the contract is documented here.
4. Workers execute long-running flows and may compose domains, but reusable rules should move into services before a second caller appears.
5. Cross-domain data passed through JSON fields must be treated as a contract and covered by tests.

## Domain Map

| Domain | Owns | Primary Files | May Call | Must Not Own |
| --- | --- | --- | --- | --- |
| case | Test case authoring, workflow, case run records, step results, snapshots, dataset binding on cases | `api/v1/cases/*`, `models/case.py`, `schemas/case.py` | project/module permission checks, dataset validation summaries, execution dispatch entrypoints | suite/plan orchestration policy, report rendering, notification delivery |
| execution | Suite/plan scheduling and worker execution lifecycle | `api/v1/suites.py`, `api/v1/plans.py`, `models/suite.py`, `models/plan.py`, `worker/tasks.py`, `worker/case_dispatch.py`, `worker/executors/*` | case runtime models, environment/global variables, notifier, reporting export helpers | case authoring workflow, channel configuration UI/API, AI diagnosis policy |
| reporting | Statistics, exports, trace views, run retention summaries | `api/v1/statistics.py`, `api/v1/exports.py`, `api/v1/traces.py`, `services/run_retention.py` | case/suite/plan run records as read-only inputs, object storage helpers | mutating execution status, sending notifications, creating bugs |
| notification | Notification channel configuration and delivery | `api/v1/notifications.py`, `api/v1/dashboard_alerts.py`, `models/notification.py`, `models/dashboard_alert.py`, `services/notifier.py`, `services/dashboard_alerts.py` | reporting summaries, execution completion summaries, encrypted config helpers | deciding execution outcomes, rendering full reports beyond accepted summary payloads |
| mock | Mock rule configuration, mock server behavior, snapshots | `api/v1/mock_rules.py`, `api/v1/mock_server.py`, `models/mock.py`, `models/mock_snapshot.py`, `mock_main.py` | project permissions, audit logging | case execution state, notification policy, AI generation |
| ai | AI case generation, healing, prompt examples, LLM config and feedback stats | `api/v1/ai_*`, `api/v1/healing_prompt_examples.py`, `models/ai_llm_config.py`, `models/healing_*`, `services/ai_case/*`, `services/ai_healing*.py` | case/step/run records as explicit inputs, project LLM config, audit logging | core case CRUD ownership, execution scheduling, notification channel delivery |
| operations | Storage, devices, APKs, performance, admin cleanup, observability support | `api/v1/storage.py`, `api/v1/devices.py`, `api/v1/apks.py`, `api/v1/performance.py`, `models/storage_policy.py`, `models/device.py`, `models/performance.py`, `services/storage_*`, `services/performance.py`, `worker/tasks_*` | object storage, Redis, device/ADB helpers, reporting summaries | test case authoring, suite/plan business policy |

## Domain Contracts

### case -> execution

- `TestCase.is_ready_for_execution` is the shared readiness contract.
- `TestRun.status`, `TestRun.result_summary`, `TestRun.parent_run_id`, and `StepResult` are runtime contracts read by reporting, AI, and bug tracking.
- Execution may create `TestRun` and `StepResult`; case CRUD owns authoring fields and review state.

### execution -> reporting

- `SuiteRun.case_run_ids` contains lightweight case result rows: `case_id`, optional `case_name`, optional `run_id`, `status`, optional `error`, and optional stability hints.
- `PlanRun.suite_run_ids` contains lightweight suite result rows: `suite_id`, optional `suite_run_id`, `status`, and optional `error`.
- Export/report APIs may read these JSON contracts but should not mutate them.

### execution -> notification

- `services.notifier.send_notifications` accepts a summary payload. The current required fields are `title`, `status`, counts, `duration_ms`, and `trigger_type`.
- Optional strategy fields include `entity_type`, `suite_id`, and `plan_id`; notification filters must ignore missing optional fields safely.
- Notification services must not recompute execution status from raw runs.

### reporting -> notification

- Reporting may build an HTML report for email attachments only when `email_html_report_enabled` returns true.
- Notification owns channel config, language, delivery, and strategy filtering.

### case/execution -> ai

- AI healing reads `TestRun` and `StepResult` details and writes healing fields on step results plus aggregate feedback models.
- AI case generation produces draft case payloads; case CRUD remains the only owner of persisted case authoring.

### mock isolation

- Mock rule matching and standalone mock server behavior must stay independent from case/suite/plan execution. Test cases may call mock endpoints as external HTTP targets, but mock must not import case execution internals.

## Placement Rules For New Code

- Add a new API under the owning domain route. If it needs two domains, keep the API in the domain that owns the user action and call the other domain through a service function.
- Add reusable cross-domain logic to `services/`, not to an API route or Celery task.
- Add long-running orchestration to `worker/`; keep deterministic validation in services so APIs and workers share it.
- Add new JSON payload fields only with a schema/type update and at least one regression or static contract test.
- Prefer documenting a new domain contract here before adding a second caller.

## Known Boundary Debt

- `worker/tasks.py` still owns broad suite and plan orchestration in one file. When touching retry/cancel/recovery logic, split shared execution policy into service helpers first.
- `api/v1/exports.py` mixes report rendering and export transport. Future reporting work should separate data extraction, rendering, and response building.
- Notification strategy currently lives inside `NotificationConfig.config` JSON for compatibility. If strategy becomes more complex, promote it to typed schema/model fields with a migration.
- Flaky case detection is computed dynamically from recent `TestRun` history. Persist it only if query cost or trend reporting requires it.
