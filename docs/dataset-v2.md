# Dataset v2 Thin Slice

Dataset v2 starts with schema validation as a non-breaking capability. Existing
dataset CRUD and parameterized execution continue to read database-backed
`rows` exactly as they do today. Large datasets can explicitly use the MinIO
reference mode described below.

## Validation API

`POST /api/v1/datasets/validate`

Request:

```json
{
  "schema_fields": [
    { "name": "username", "type": "string", "required": true },
    { "name": "age", "type": "integer", "required": false, "default": 18 }
  ],
  "rows": [
    { "username": "alice" },
    { "username": "bob", "age": "old" }
  ],
  "preview_limit": 5
}
```

Response:

```json
{
  "valid": false,
  "row_count": 2,
  "normalized_rows": [
    { "username": "alice", "age": 18 },
    { "username": "bob", "age": "old" }
  ],
  "issues": [
    { "row_index": 1, "field": "age", "message": "expected integer, got str" }
  ]
}
```

## Field Types

- `string`
- `number`
- `integer`
- `boolean`
- `object`
- `array`

## Current Scope

- Dataset schema is persisted as `test_datasets.schema_fields`.
- Dataset upload supports `validation_policy`:
  - `soft` (default): preview reports schema issues, but upload can still overwrite after confirmation.
  - `hard`: upload is rejected when schema validation finds issues.
- Dataset version snapshots have a dedicated `test_dataset_versions` model/table
  with `rows`, `schema_fields`, `format`, `validation_policy`, `change_type`, and
  `created_by` fields. Migration `20260812_0055` adds `storage_mode`,
  `object_name`, and `row_count` so snapshots can also reference MinIO objects.
- AI-generated test cases persist the selected `dataset_id` and immutable
  `dataset_version`. Legacy cases with a null version continue to use the
  current dataset, while a pinned version is loaded by the case Worker.
- Dataset rollback API/UI is available from Dataset Library version history.
- Dataset reference impact query is available from Dataset Library. It reports
  directly bound cases, suites that contain those cases or reference the dataset
  in parameterization, and plans that contain affected suites.
- Parameterized execution supports strict schema enforcement. A case can set
  `config.dataset_strict_schema=true`; datasets with `validation_policy=hard`
  also enforce strict validation automatically before child runs are dispatched.
- Soft validation still records `dataset_schema_valid`, `dataset_schema_issue_count`,
  and `dataset_strict_schema` in the parent run summary while preserving the
  previous behavior of continuing execution.
- Dataset upload now has a non-mutating preview step in the UI: the file is parsed
  and validated against the dataset schema before the user confirms overwrite.
- Defaults are applied only to the normalized preview returned by validation.
- Database row limits remain 500 rows and 256KB serialized. MinIO mode accepts up
  to 50MB of compact JSON and stores only an object reference plus row count in
  PostgreSQL. The current object and immutable version objects use the prefix
  `datasets/{project_id}/{dataset_id}/`.

## MinIO reference mode

The Dataset Library exposes `数据库` and `MinIO 对象存储` as the storage choice.
Use MinIO for large CSV/JSON datasets or data that should not be duplicated in
PostgreSQL. Reads, parameterized case/performance execution, AI samples and
project export resolve the object reference through the shared storage helper;
the API still returns rows when a detail/editor view explicitly requests them.
Project export/import snapshots also carry the storage mode: MinIO rows are
materialized for the transfer payload, validated against the 50MB object limit,
and uploaded into the destination project's MinIO prefix during import.

When switching storage mode, the current rows are copied to the new backend and
the old current object is removed after the database commit. Replacing an
existing MinIO current object first writes a unique object name; if the database
commit or version snapshot fails, the new objects are cleaned up and the old
reference remains usable. Version objects are kept for rollback and all
current/version objects are removed when the dataset is deleted. A MinIO outage
fails the write/read explicitly; it does not silently replace the dataset with
an empty row set.

A metadata-only edit of a MinIO-backed dataset still returns the current rows to
the editor by reading the referenced object after the database update. This keeps
the detail response consistent with `GET /datasets/{id}` and avoids making a
successful rename appear to have erased the dataset.

### MinIO object reconciliation

Administrators can audit MinIO objects for one project with:

```http
POST /api/v1/projects/{project_id}/datasets/storage/reconcile
{}
```

The default is a dry run. The response compares objects below
`datasets/{project_id}/` with current and version references stored in
PostgreSQL, and reports scanned, referenced, orphan, deleted and error counts.
To explicitly purge unreferenced objects, send `{ "purge": true }`. The purge
is restricted to that project's exact prefix; deletion failures are returned in
`errors` and do not cause referenced objects to be removed. Each operation is
recorded in the audit log. Review the dry-run result and take a MinIO backup
before enabling purge in a production environment.

## Run-scoped data preparation

An API case that is bound to a dataset can set `config.dataset_prepare_actions`.
These actions run once before parameterized child runs are created. They do not
modify the dataset or its MinIO objects; variables extracted from a seed response
are merged into every child run, and row fields take precedence over shared
variables when names collide.

The restricted DSL supports `set_variable`, `delete_variable`, `assert`, and a
bounded `request` action. A request can use `GET`, `POST`, `PUT`, `PATCH`, or
`DELETE`, JSON/raw bodies, `{{variable}}` substitution, status/header/body
assertions, and `post_actions` for response extraction. Each run allows at most
20 preparation actions, each request is limited to 60 seconds, and response
content is limited to 1MB. Python and JavaScript are never executed. Every
request URL is resolved and must point to a public HTTP(S) address; localhost,
private/link-local/reserved addresses and DNS names resolving to them are
rejected. The action payload must be a JSON list, so malformed objects cannot
silently skip preparation. A failed preparation stops the run before any child
iteration is created and records a secret-free summary in the parent run.

Example:

```json
[
  {"action": "set_variable", "variable": "tenant", "value": "demo"},
  {
    "action": "request",
    "name": "seed user",
    "method": "POST",
    "url": "{{base_url}}/users",
    "body_type": "json",
    "body": {"name": "{{username}}", "tenant": "{{tenant}}"},
    "assertions": [{"source": "status", "operator": "eq", "expected": 201}],
    "post_actions": [{"action": "extract", "variable": "user_id", "expression": "$.id"}]
  }
]
```

## Next Step

Use the new governance data in Q9 acceptance evidence and continue with
Performance Center production hardening.
