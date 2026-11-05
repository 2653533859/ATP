"""Exercise both remote-agent revisions and the Linux upgrade path."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text


VERSIONS = Path(__file__).parents[2] / "alembic" / "versions"


def _load(filename: str):
    spec = spec_from_file_location(filename.replace(".py", ""), VERSIONS / filename)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_site_revision_is_ancestor_of_single_head():
    config = Config()
    config.set_main_option("script_location", str(VERSIONS.parent))
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["20261104_0085"]
    revisions = [revision.revision for revision in scripts.iterate_revisions("head", "20261026_0082")]
    assert revisions == ["20261104_0085", "20261102_0084", "20261102_0083", "20261029_0083"]


def test_remote_agent_upgrade_preserves_existing_site_data(tmp_path):
    legacy = _load("20261029_0083_restore_remote_agents_revision.py")
    current = _load("20261102_0083_add_remote_agent_tables.py")
    engine = create_engine(f"sqlite:///{(tmp_path / 'migration.db').as_posix()}")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            legacy.upgrade()
            legacy.upgrade()
            connection.execute(text("INSERT INTO remote_agents (id, name, status) VALUES (1, 'agent', 'online')"))
            connection.execute(
                text(
                    "INSERT INTO remote_agent_devices (id, agent_id, usb_serial, tunnel_port) "
                    "VALUES (1, 1, 'device', 10001)"
                )
            )
            current.upgrade()
            assert connection.execute(text("SELECT count(*) FROM remote_agents")).scalar_one() == 1
            assert connection.execute(text("SELECT count(*) FROM remote_agent_devices")).scalar_one() == 1
            current.downgrade()
            assert inspect(connection).has_table("remote_agents")
            assert connection.execute(text("SELECT count(*) FROM remote_agent_devices")).scalar_one() == 1
            legacy.downgrade()
            assert not inspect(connection).has_table("remote_agents")
            assert not inspect(connection).has_table("remote_agent_devices")
    engine.dispose()
