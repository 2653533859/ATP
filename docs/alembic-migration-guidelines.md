# Alembic Migration Guidelines

ATP treats Alembic revisions as the source of truth for database structure. Use these rules for every new schema change.

## Required Shape

Each revision must include:

- Typed `revision`, `down_revision`, `branch_labels`, and `depends_on` declarations.
- A focused `upgrade()` that performs one logical schema change.
- A matching `downgrade()` in reverse dependency order.
- A migration-specific regression test under `backend/tests/migrations/` for enum, index, constraint, and table changes.
- Explicit names for indexes, unique constraints, foreign keys created outside `op.create_table`, and check constraints.

Use [backend/alembic/templates/migration_template.py](../backend/alembic/templates/migration_template.py) as the starting point for new revisions.

## Enum Changes

For a new PostgreSQL enum:

```python
status_enum = sa.Enum("pending", "running", "passed", name="my_status")

def upgrade() -> None:
    status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column("my_table", sa.Column("status", status_enum, nullable=False))

def downgrade() -> None:
    op.drop_column("my_table", "status")
    status_enum.drop(op.get_bind(), checkfirst=True)
```

Rules:

- Define enum objects at module scope.
- Use `checkfirst=True` on enum create/drop.
- Drop dependent columns or tables before dropping the enum.
- Extending an existing enum should be additive and should document downgrade behavior. PostgreSQL enum value removal is not safe as a normal downgrade.

## Index Changes

For a new index:

```python
def upgrade() -> None:
    op.create_index(
        "ix_test_runs_case_id_status_created_at",
        "test_runs",
        ["case_id", "status", "created_at"],
    )

def downgrade() -> None:
    op.drop_index("ix_test_runs_case_id_status_created_at", table_name="test_runs")
```

Rules:

- Name indexes as `ix_<table>_<columns_or_lookup>`.
- Use `table_name=` in `op.drop_index`.
- Composite indexes must match an observed query shape or documented dashboard/reporting query.
- Add or update a migration test that asserts both create and drop operations.

## Constraint Changes

For constraints inside a new table, prefer SQLAlchemy constraints in `op.create_table`:

```python
op.create_table(
    "test_dataset_versions",
    sa.Column("dataset_id", sa.Integer(), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(["dataset_id"], ["test_datasets.id"], ondelete="CASCADE"),
    sa.UniqueConstraint("dataset_id", "version", name="uq_test_dataset_versions_dataset_version"),
)
```

For constraints added to an existing table:

```python
def upgrade() -> None:
    op.create_unique_constraint("uq_projects_project_code", "projects", ["project_code"])
    op.create_foreign_key(
        "fk_test_cases_owner_id",
        "test_cases",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )

def downgrade() -> None:
    op.drop_constraint("fk_test_cases_owner_id", "test_cases", type_="foreignkey")
    op.drop_constraint("uq_projects_project_code", "projects", type_="unique")
```

Rules:

- Constraint names should be explicit and deterministic.
- Downgrade must drop constraints before dropping dependent columns.
- Foreign keys must declare `ondelete` intentionally. Use no cascade only when preserving child rows is required and documented.
- Add regression tests for cascade behavior and downgrade drops when the constraint protects important data.

## Test Expectations

Migration tests should be cheap and focused:

- Static tests are acceptable for naming, chain order, and downgrade coverage.
- Empty-database upgrade checks belong in CI or integration environments with PostgreSQL.
- Any migration adding an enum should assert `checkfirst=True` create/drop.
- Any migration adding indexes should assert matching `op.drop_index(..., table_name=...)`.
- Any migration adding constraints should assert the name and downgrade drop.

## Review Checklist

Before marking a migration done:

1. `alembic upgrade head` succeeds on an empty PostgreSQL database.
2. `alembic downgrade -1` is safe or the unsafe downgrade is documented.
3. New ORM models and Alembic schema agree on nullability, enum names, indexes, and constraints.
4. Migration tests cover enum/index/constraint behavior introduced by the revision.
5. The revision does not use `Base.metadata.create_all`, `command.stamp`, or ad hoc schema repair.
