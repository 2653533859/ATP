"""Runtime PostgreSQL grant reconciliation tests."""

from unittest.mock import Mock

import pytest

from app.core.database_privileges import grant_runtime_privileges


def _connection(*, dialect_name: str = "postgresql") -> Mock:
    connection = Mock()
    connection.dialect.name = dialect_name
    connection.dialect.identifier_preparer.quote_identifier.side_effect = (
        lambda value: f'"{value.replace(chr(34), chr(34) * 2)}"'
    )
    return connection


def test_grant_runtime_privileges_reconciles_current_and_default_grants():
    connection = _connection()

    grant_runtime_privileges(
        connection,
        database_name="atp_restore",
        runtime_user="atp_runtime",
        migration_user="atp_migrator",
    )

    statements = [call.args[0] for call in connection.exec_driver_sql.call_args_list]
    assert statements == [
        'GRANT CONNECT ON DATABASE "atp_restore" TO "atp_runtime"',
        'GRANT USAGE ON SCHEMA public TO "atp_runtime"',
        'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "atp_runtime"',
        'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO "atp_runtime"',
        'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO "atp_runtime"',
        (
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE "
            'ON TABLES TO "atp_runtime"'
        ),
        ("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE " 'ON SEQUENCES TO "atp_runtime"'),
        'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO "atp_runtime"',
    ]


def test_grant_runtime_privileges_quotes_identifiers():
    connection = _connection()

    grant_runtime_privileges(
        connection,
        database_name='atp"restore',
        runtime_user='runtime"role',
        migration_user="migrator",
    )

    assert connection.exec_driver_sql.call_args_list[0].args[0] == (
        'GRANT CONNECT ON DATABASE "atp""restore" TO "runtime""role"'
    )


def test_grant_runtime_privileges_skips_shared_legacy_role():
    connection = _connection()

    grant_runtime_privileges(
        connection,
        database_name="atp",
        runtime_user="shared",
        migration_user="shared",
    )

    connection.exec_driver_sql.assert_not_called()


@pytest.mark.parametrize("field", ["database_name", "runtime_user", "migration_user"])
def test_grant_runtime_privileges_rejects_empty_identifiers(field):
    connection = _connection()
    values = {
        "database_name": "atp",
        "runtime_user": "runtime",
        "migration_user": "migrator",
    }
    values[field] = ""

    with pytest.raises(ValueError, match="must not be empty"):
        grant_runtime_privileges(connection, **values)


def test_grant_runtime_privileges_rejects_non_postgresql_connections():
    connection = _connection(dialect_name="sqlite")

    with pytest.raises(RuntimeError, match="requires PostgreSQL"):
        grant_runtime_privileges(
            connection,
            database_name="atp",
            runtime_user="runtime",
            migration_user="migrator",
        )
