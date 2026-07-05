import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests._paths import repo_path


def test_disaster_recovery_runbook_covers_database_and_object_storage():
    content = repo_path("docs/disaster-recovery.md").read_text(encoding="utf-8")

    assert "scripts/backup-postgres.sh" in content
    assert "scripts/restore-postgres.sh" in content
    assert "Object Storage Backup" in content
    assert "Object Storage Restore" in content
    assert 'mc mirror --overwrite --exclude "pg-backups/*"' in content
    assert "mc mirror --overwrite --remove" in content
    assert "dr-minio/${DR_MINIO_BUCKET}/atp-objects/" in content


def test_disaster_recovery_runbook_has_drill_verification_steps():
    content = repo_path("docs/disaster-recovery.md").read_text(encoding="utf-8")

    assert "Kubernetes Drill" in content
    assert "alembic upgrade head" in content
    assert "curl -fsS https://atp.example.com/health" in content
    assert "A recent daily backup exists in MinIO." in content
    assert "A recent MinIO application object backup exists outside the primary bucket." in content
    assert "One restored object key was opened or fetched successfully." in content
    assert "docs/backup-restore-drill-record.md" in content


def test_backup_restore_drill_record_template_tracks_required_evidence():
    content = repo_path("docs/backup-restore-drill-record.md").read_text(encoding="utf-8")

    assert "Drill Record Template" in content
    assert "PostgreSQL backup object" in content
    assert "MinIO object backup location" in content
    assert "Restored object key checked" in content
    assert "Required Evidence" in content
    assert "scripts/restore-postgres.sh" in content
    assert "mc mirror --overwrite --remove" in content
    assert "2026-07-05 Repository Verification" in content


def test_s4_06_is_marked_complete_in_roadmap():
    roadmap = repo_path("docs/optimization-roadmap-2026.md").read_text(encoding="utf-8")

    assert "| S4-06 | 备份恢复演练 | P1 | [x] 已完成 |" in roadmap
