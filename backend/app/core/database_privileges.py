"""PostgreSQL privileges required by the long-running ATP runtime role."""

from sqlalchemy.engine import Connection


def grant_runtime_privileges(
    connection: Connection,
    *,
    database_name: str,
    runtime_user: str,
    migration_user: str,
) -> None:
    """Reconcile runtime grants after Alembic creates or restores objects.

    PostgreSQL default privileges are database-local and ``pg_dump --no-acl``
    intentionally omits grants. Reapplying this contract after every migration
    keeps an empty or restored database usable without giving the application
    role DDL privileges.
    """

    if runtime_user == migration_user:
        return
    if not database_name or not runtime_user or not migration_user:
        raise ValueError("database and PostgreSQL role names must not be empty")
    if connection.dialect.name != "postgresql":
        raise RuntimeError("runtime privilege reconciliation requires PostgreSQL")

    quote = connection.dialect.identifier_preparer.quote_identifier
    database = quote(database_name)
    runtime_role = quote(runtime_user)
    statements = (
        f"GRANT CONNECT ON DATABASE {database} TO {runtime_role}",
        f"GRANT USAGE ON SCHEMA public TO {runtime_role}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {runtime_role}",
        f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {runtime_role}",
        f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {runtime_role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {runtime_role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {runtime_role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO {runtime_role}",
    )
    for statement in statements:
        connection.exec_driver_sql(statement)
