# Dataset v2 Thin Slice

Dataset v2 starts with schema validation as a non-breaking capability. Existing
dataset CRUD and parameterized execution continue to read `rows` exactly as they
do today.

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
  `created_by` fields.
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
- Row limits reuse the existing MVP constraints: 500 rows and 256KB serialized.

## Next Step

Use the new governance data in Q9 acceptance evidence and continue with
Performance Center production hardening.
