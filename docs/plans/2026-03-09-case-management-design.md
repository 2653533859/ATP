# Standardized Case Management Design

**Date:** 2026-03-09
**Scope:** Redesign the case module around standardized test case management, with project-scoped authoring and execution selection built on top of the existing ATP architecture.

## Goal

Turn the current case module from a mostly execution-config-driven structure into a standardized test case management system. Users should create cases under projects and modules, maintain normalized case content such as case code, preconditions, steps, and expected results, and then select approved cases for execution.

## Current State

The repository already has a usable case domain, but it is lightweight and execution-oriented:
- `TestCase` currently stores `name`, `description`, `case_type`, `status`, `tags`, `module_id`, `creator_id`, and a generic `config` JSON payload.
- Case execution is already supported through `POST /api/v1/cases/{id}/run` and Celery workers.
- Case snapshots and rollback already exist.
- Frontend case management already has list and drawer-based editing flows.

This means the execution backbone is present, but standardized management fields are not yet modeled as first-class data.

## Approved Direction

The module should be optimized for **test case management first**, with execution as a downstream action.

The target workflow is:
- Project
- Module
- Standardized test case
- Review / activate
- Select for execution

Automation configuration remains important, but it should not define the core structure of a test case.

## Recommended Approach

### Scheme A: Management-first standardized cases (Approved)

- Normalize common management fields directly on the case domain.
- Store structured steps as explicit records rather than one large text blob.
- Keep type-specific execution configuration in `config` during the transition.
- Continue using `TestRun` and `StepResult` for actual execution outcomes.

### Why this scheme

- Fits the current repository with minimal architectural churn.
- Preserves existing execution flows and worker routing.
- Makes cases reviewable, reusable, filterable, and exportable.
- Leaves room for a later split between “standard case” and “automation implementation” if needed.

## Non-Goals

- No full redesign of suite, plan, or worker architecture in this phase.
- No replacement of the current execution config model for all case types.
- No introduction of a separate automation-implementation aggregate yet.
- No large workflow engine for approvals beyond basic status transitions.

## Domain Design

### Core concept split

The case module should clearly separate:
- **Case definition**: what should be tested
- **Execution record**: what happened in one run

Case definition includes:
- case code
- case name
- preconditions
- structured steps
- expected results
- review and lifecycle metadata

Execution record includes:
- run status
- step-by-step runtime outcomes
- screenshots
- error messages
- duration
- environment and trigger metadata

This preserves one-to-many relationships between one standard case and many execution runs.

## Data Model

### `TestCase`

Keep the current table and add standardized management fields:
- `case_code`: unique case identifier
- `summary`: scenario/goal summary
- `preconditions`: JSON array of strings
- `postconditions`: JSON array of strings
- `priority`: enum-like string (`P0/P1/P2/P3`)
- `case_level`: enum-like string (`smoke/core/regression/extended`)
- `review_status`: enum-like string (`pending/approved/rejected`)
- `owner_id`: nullable user reference
- `automation_status`: enum-like string (`manual/semi_auto/auto`)
- `submitted_at`: nullable timestamp
- `reviewed_at`: nullable timestamp
- `reviewed_by`: nullable user reference
- `review_comment`: nullable text

Keep existing fields:
- `name`
- `description`
- `case_type`
- `status`
- `tags`
- `module_id`
- `creator_id`
- `config`

### `CaseStep`

Add a new table for structured steps:
- `id`
- `case_id`
- `step_no`
- `action`
- `test_data`
- `expected_result`
- `is_key_step`
- `remarks`
- `created_at`
- `updated_at`

This table is the core of standardization. It enables ordered display, filtering, future export, and step-level mapping to runtime output.

### `CaseSnapshot`

Preserve the current snapshot capability, but expand it so snapshots capture the standardized shape as a complete historical view.

Recommended additions:
- `snapshot_data`: JSON payload containing the full case definition at snapshot time

That payload should include:
- standardized case fields
- steps
- tags
- config

This avoids maintaining a separate snapshot-step relational structure unless future reporting needs it.

### Existing execution tables remain authoritative

Keep these responsibilities unchanged:
- `TestRun`: run-level result and metadata
- `StepResult`: runtime result of each executed step

The definition layer and the execution layer should remain separate.

## Case Code Standard

Recommended format:

`[PROJECT_CODE]-[MODULE_CODE]-[TYPE]-[SEQUENCE]`

Examples:
- `ATP-LOGIN-WEB-0001`
- `ATP-USER-API-0012`
- `ATP-ORDER-AND-0008`

Recommendations:
- add `project_code` on project domain
- add `module_code` on module domain
- maintain sequence per module + type

Case code should be:
- required
- unique
- stable after approval except through controlled rename/renumber flow

## Lifecycle Design

### Case status

Recommended lifecycle:
- `draft`
- `active`
- `deprecated`

### Review status

Recommended review status:
- `pending`
- `approved`
- `rejected`

### Operational rules

- Newly created cases start as `draft` + `pending`
- Only approved cases can become operationally active for normal execution selection
- Deprecated cases remain queryable and historical, but should not be selected by default
- Editing an approved case should produce a new review cycle and snapshot

## API Design

Reuse the existing `/cases` surface and extend it into a management-oriented API.

### Query and detail

- `GET /api/v1/cases`
  - filters: `project_id`, `module_id`, `case_type`, `priority`, `status`, `review_status`, `owner_id`, `tag`, `keyword`
- `GET /api/v1/cases/{id}`
  - returns full standardized definition including steps

### Mutation

- `POST /api/v1/cases`
  - create case with standardized fields and steps
- `PATCH /api/v1/cases/{id}`
  - update standardized fields, steps, and execution config
- `POST /api/v1/cases/{id}/copy`
  - duplicate case into a new draft

### Workflow actions

- `POST /api/v1/cases/{id}/submit-review`
- `POST /api/v1/cases/{id}/approve`
- `POST /api/v1/cases/{id}/reject`
- `POST /api/v1/cases/{id}/deprecate`
- `POST /api/v1/cases/{id}/reactivate`

### Execution

Keep current single-case execution endpoint:
- `POST /api/v1/cases/{id}/run`

Execution selection should be gated by business rules in later UI/API validation:
- case must be active
- review should be approved
- automation status should allow execution

## Frontend Design

### Case list page

Primary role: manage the standardized case library.

Columns:
- case code
- case name
- type
- project
- module
- priority
- case level
- status
- review status
- latest run status
- updated time

Filters:
- project
- module
- case type
- priority
- status
- review status
- tags
- owner
- automation status
- keyword search

Actions:
- view
- edit
- copy
- submit for review
- deprecate
- add to execution selection
- view history

### Case editor

Recommended sections:
- basic info
- case content
- structured steps
- automation binding
- additional metadata

The structured step editor should be tabular and orderable.

### Case detail page

Tabs:
- standard content
- automation configuration
- version history

Side panel:
- latest run result
- latest run time
- quick execute
- add to suite or plan

### Execution selection flow

Recommended flow:
- choose project
- filter by module and metadata
- multi-select standardized cases
- choose environment
- choose execution destination (`run now`, `add to suite`, `add to plan`)

Only approved active cases should be shown by default in the selection flow.

## Migration Strategy

To avoid breaking existing cases:
- keep `config` for type-specific execution settings
- make new standardized fields backward-compatible where possible
- default existing cases to a migration-safe review state
- allow empty step data temporarily for legacy cases, but require standardized fields for newly created cases

This should be a staged transition rather than a big-bang rewrite.

## Testing Strategy

- Add backend regression tests for the new schemas and workflow actions first
- Add API tests for create/update/filter/review transitions
- Add tests for step ordering and snapshot preservation
- Use focused frontend validation on case list and editor behavior
- Reuse existing execution regression paths to ensure run behavior remains intact

## Success Criteria

This design is considered delivered when:
- cases have unique standardized codes
- preconditions and steps are structured, not just free-form config
- cases can be reviewed and activated before execution
- project/module based filtering works for case management
- execution continues to work through the existing worker pipeline

## Future Extensions

- split standard cases from automation implementations if complexity grows
- add richer review/audit workflows
- add import/export templates for external case management systems
- add requirement linkage and defect linkage as first-class entities
