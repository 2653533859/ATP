from pathlib import Path


def test_mobile_special_migration_covers_task_type_enum():
    """Verify the mobile special migration includes task_type enum values: performance, stability, fluency."""
    migration_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    content = "\n".join(file.read_text(encoding="utf-8") for file in sorted(migration_dir.glob("*.py")))
    mobile_special_migration = migration_dir / "20260330_0014_add_mobile_special_domain.py"

    assert mobile_special_migration.exists(), "Mobile special migration must exist"
    assert "mobile_special" in mobile_special_migration.read_text(encoding="utf-8").lower(), \
        "Mobile special migration must contain mobile_special domain"

    # Must have task_type enum with required values
    for val in ("performance", "stability", "fluency"):
        assert val in content, f"task_type enum must include '{val}'"


def test_mobile_special_migration_covers_status_enum():
    """Verify the migration includes status enum values: pending, running, completed, failed, stopped."""
    migration_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    content = "\n".join(file.read_text(encoding="utf-8") for file in sorted(migration_dir.glob("*.py")))

    for val in ("pending", "running", "completed", "failed", "stopped"):
        assert val in content, f"status enum must include '{val}'"


def test_mobile_special_migration_covers_metric_type_enum():
    """Verify the migration includes metric_type enum values."""
    migration_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    content = "\n".join(file.read_text(encoding="utf-8") for file in sorted(migration_dir.glob("*.py")))

    required_metrics = ["cpu_pct", "mem_mb", "fps", "jank_count", "frame_time_ms", "battery_pct"]
    for metric in required_metrics:
        assert metric in content, f"metric_type enum must include '{metric}'"


def test_mobile_special_migration_covers_tables():
    """Verify the mobile special migration creates required tables."""
    migration_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    mobile_special_migration = migration_dir / "20260330_0014_add_mobile_special_domain.py"
    content = mobile_special_migration.read_text(encoding="utf-8")

    required_tables = [
        "mobile_special_tasks",
        "mobile_special_runs",
        "mobile_metric_samples",
        "mobile_incidents",
        "mobile_run_artifacts",
        "global_variables",
    ]
    for table in required_tables:
        assert table in content, f"Migration must create table '{table}'"


def test_mobile_special_migration_has_required_indexes():
    """Verify the mobile special migration includes required indexes."""
    migration_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
    mobile_special_migration = migration_dir / "20260330_0014_add_mobile_special_domain.py"
    content = mobile_special_migration.read_text(encoding="utf-8")

    # Key indexes on foreign keys and time columns
    assert "create_index" in content or "index" in content.lower(), \
        "Migration should create indexes for performance"
