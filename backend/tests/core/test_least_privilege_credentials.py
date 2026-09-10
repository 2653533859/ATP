from pathlib import Path

from alembic.config import Config
import pytest
from pydantic import ValidationError
import yaml

from app.core.config import Settings


def test_migration_database_url_falls_back_to_runtime_credentials():
    configured = Settings(
        _env_file=None,
        POSTGRES_HOST="database.example.test",
        POSTGRES_DB="atp",
        POSTGRES_USER="atp_runtime",
        POSTGRES_PASSWORD="runtime-secret",
    )

    assert configured.MIGRATION_DATABASE_URL == configured.DATABASE_URL


def test_migration_database_url_uses_separate_encoded_credentials():
    configured = Settings(
        _env_file=None,
        POSTGRES_HOST="database.example.test",
        POSTGRES_DB="atp",
        POSTGRES_USER="atp_runtime",
        POSTGRES_PASSWORD="runtime-secret",
        POSTGRES_MIGRATION_USER="atp owner",
        POSTGRES_MIGRATION_PASSWORD="ddl:@/secret",
    )

    assert configured.DATABASE_URL.startswith("postgresql+asyncpg://atp_runtime:runtime-secret@")
    assert configured.MIGRATION_DATABASE_URL.startswith("postgresql+asyncpg://atp%20owner:ddl%3A%40%2Fsecret@")
    alembic_config = Config()
    sync_url = configured.MIGRATION_DATABASE_URL.replace("postgresql+asyncpg", "postgresql+psycopg2")
    alembic_config.set_main_option("sqlalchemy.url", sync_url.replace("%", "%%"))
    assert alembic_config.get_main_option("sqlalchemy.url") == sync_url


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"POSTGRES_MIGRATION_USER": "owner"}, "POSTGRES_MIGRATION_USER"),
        ({"MINIO_ACCESS_KEY": "atp-app"}, "MINIO_ACCESS_KEY"),
    ],
)
def test_split_credentials_require_complete_pairs(overrides, message):
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **overrides)


def test_redis_url_supports_acl_username_and_encodes_credentials():
    legacy = Settings(
        _env_file=None,
        REDIS_HOST="redis.example.test",
        REDIS_PORT=6379,
        REDIS_PASSWORD="legacy:@/secret",
    )
    acl = Settings(
        _env_file=None,
        REDIS_HOST="redis.example.test",
        REDIS_PORT=6379,
        REDIS_USERNAME="atp runtime",
        REDIS_PASSWORD="acl:@/secret",
    )

    assert legacy.redis_url(2) == "redis://:legacy%3A%40%2Fsecret@redis.example.test:6379/2"
    assert acl.CELERY_BROKER_URL == "redis://atp%20runtime:acl%3A%40%2Fsecret@redis.example.test:6379/0"
    assert acl.CELERY_RESULT_BACKEND.endswith("/1")


def test_minio_application_credentials_override_legacy_root_fields():
    legacy = Settings(_env_file=None, MINIO_ROOT_USER="legacy", MINIO_ROOT_PASSWORD="legacy-secret")
    scoped = Settings(
        _env_file=None,
        MINIO_ROOT_USER="legacy",
        MINIO_ROOT_PASSWORD="legacy-secret",
        MINIO_ACCESS_KEY="atp-app",
        MINIO_SECRET_KEY="app-secret",
    )

    assert (legacy.MINIO_CLIENT_ACCESS_KEY, legacy.MINIO_CLIENT_SECRET_KEY) == ("legacy", "legacy-secret")
    assert (scoped.MINIO_CLIENT_ACCESS_KEY, scoped.MINIO_CLIENT_SECRET_KEY) == ("atp-app", "app-secret")


def test_alembic_and_redis_clients_use_split_credential_helpers():
    backend = Path(__file__).resolve().parents[2]
    alembic = backend.joinpath("alembic", "env.py").read_text(encoding="utf-8")
    redis_clients = [
        backend.joinpath("app", "core", "redis_client.py"),
        backend.joinpath("app", "services", "performance_control.py"),
        backend.joinpath("app", "services", "performance_metrics.py"),
        backend.joinpath("app", "services", "web_run_control.py"),
    ]

    assert "settings.MIGRATION_DATABASE_URL" in alembic
    assert 'sync_url.replace("%", "%%")' in alembic
    for path in redis_clients:
        assert "settings.redis_url(" in path.read_text(encoding="utf-8")


def test_helm_mounts_migration_credentials_only_in_hook_job():
    root = Path(__file__).resolve().parents[3]
    chart = root.joinpath("deploy", "helm", "atp")
    values = yaml.safe_load(chart.joinpath("values.yaml").read_text(encoding="utf-8"))
    migration = chart.joinpath("templates", "migrate-job.yaml").read_text(encoding="utf-8")

    assert values["migrationSecret"] == {"existingName": ""}
    assert "POSTGRES_MIGRATION_USER" not in values["secrets"]
    assert "POSTGRES_MIGRATION_PASSWORD" not in values["secrets"]
    assert ".Values.migrationSecret.existingName" in migration
    assert "POSTGRES_MIGRATION_USER" in migration
    assert "POSTGRES_MIGRATION_PASSWORD" in migration

    for deployment in chart.joinpath("templates").glob("*-deployment.yaml"):
        content = deployment.read_text(encoding="utf-8")
        assert "POSTGRES_MIGRATION_USER" not in content
        assert "POSTGRES_MIGRATION_PASSWORD" not in content
