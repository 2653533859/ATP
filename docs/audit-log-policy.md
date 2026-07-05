# Audit Log Policy

ATP audit logs are for traceability of security-sensitive and operations-sensitive actions. They should help answer: who changed what, in which project, and when, without exposing secrets.

## Required Audit Categories

| Category | Examples | Current Actions |
| --- | --- | --- |
| Permissions | project access denied, role boundary violations | `access_denied` |
| Case authoring | create, delete, batch move/delete/copy, workflow, rollback | `create`, `delete`, `case_batch_*`, `case_workflow`, `case_rollback` |
| Execution defect linkage | link existing bug, create bug, duplicate bug found | `run_bug_link`, `run_bug_create`, `run_bug_create_duplicate` |
| Notification config | create, update, delete notification channels and strategy filters | `notification_config_create`, `notification_config_update`, `notification_config_delete` |
| Bug tracker config | create, update, delete external defect tracker settings | `bug_tracker_create`, `bug_tracker_update`, `bug_tracker_delete` |
| AI config | create, update, delete model/provider configuration | `ai_llm_config_create`, `ai_llm_config_update`, `ai_llm_config_delete` |
| AI generation funnel | generation success/failure and saved drafts | `ai_case_generate`, `ai_case_generate_failed`, `ai_case_draft_saved` |

## Sensitive Data Rules

Never write the following into `AuditLog.detail`:

- API keys, tokens, passwords, webhook URLs, signing secrets, SMTP credentials.
- Full request/response bodies from test steps.
- Raw LLM prompts containing user data unless a separate redaction policy is applied.
- Uploaded file contents or object storage pre-signed URLs.

Use names, IDs, provider/type labels, status, and short non-secret summaries instead.

## Implementation Rules

1. Write audit logs after authorization succeeds and before the final commit when possible.
2. Use `project_id` whenever the resource belongs to a project.
3. Use stable `resource_type` values such as `notification_config`, `bug_tracker`, `ai_llm_config`, `test_run`, and `test_case`.
4. For delete actions, capture `name` / `project_id` before deleting the ORM object.
5. Do not let audit failures break user actions; `write_audit_log` intentionally swallows audit write exceptions.
6. Add or update a static regression test for every new audit category.

## Review Checklist

Before adding a new config, permission, execution, or delete operation:

1. Identify whether the action is audit-worthy using the category table.
2. Confirm `detail` is useful but secret-free.
3. Confirm the API has access to `user_id`, `username`, and `project_id`.
4. Confirm the audit log list can filter the resulting action by `project_id`, `action`, or `user_id`.
