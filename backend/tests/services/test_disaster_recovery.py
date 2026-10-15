"""Unit tests for T4.3 Platform Core Asset Snapshot Backup and Disaster Recovery Drill.

Tests:
1. create_disaster_recovery_snapshot creates compliant tar.gz with manifest and checksums
2. perform_disaster_recovery_drill unpacks and verifies all component checksums and table counts
3. Tampered archive detection during drill
4. Corrupted archive error handling
"""

from __future__ import annotations

import io
import json
import tarfile
from typing import Any

import pytest

from app.models.bootstrap import load_all_models
from app.services.disaster_recovery import (
    create_disaster_recovery_snapshot,
    perform_disaster_recovery_drill,
)

load_all_models()


class _MockDB:
    async def scalar(self, _stmt):
        return 10


@pytest.mark.asyncio
async def test_create_and_drill_disaster_recovery_snapshot():
    db: Any = _MockDB()
    manifest, archive_bytes = await create_disaster_recovery_snapshot(
        db,
        snapshot_tag="test_drill",
        database_dump_bytes=b"CREATE TABLE sample (id INT); INSERT INTO sample VALUES (1);",
        artifact_summary={"total_artifacts": 42},
    )

    assert manifest["snapshot_id"].startswith("dr_test_drill_")
    assert manifest["platform_version"] == "v2.7.0"
    assert "database.sql" in manifest["files"]
    assert "artifacts_summary.json" in manifest["files"]
    assert len(archive_bytes) > 100

    # Execute restore drill
    drill_report = perform_disaster_recovery_drill(
        archive_bytes,
        expected_table_counts=manifest["table_counts"],
    )

    assert drill_report["status"] == "passed"
    assert drill_report["integrity_passed"] is True
    assert "database.sql" in drill_report["verified_files"]
    assert "artifacts_summary.json" in drill_report["verified_files"]
    assert len(drill_report["checksum_failures"]) == 0
    assert drill_report["table_reconciliation"]["projects"]["matched"] is True


def test_drill_detects_tampered_archive():
    # Construct an archive where manifest specifies different SHA than file contents
    manifest = {
        "snapshot_id": "tampered_1",
        "platform_version": "v2.7.0",
        "files": {
            "database.sql": {"sha256": "0000000000000000000000000000000000000000000000000000000000000000"},
        },
    }
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        m_bytes = json.dumps(manifest).encode()
        ti_m = tarfile.TarInfo("tampered_1/manifest.json")
        ti_m.size = len(m_bytes)
        tar.addfile(ti_m, io.BytesIO(m_bytes))

        sql_bytes = b"SELECT 1;"
        ti_sql = tarfile.TarInfo("tampered_1/database.sql")
        ti_sql.size = len(sql_bytes)
        tar.addfile(ti_sql, io.BytesIO(sql_bytes))

    drill_res = perform_disaster_recovery_drill(buf.getvalue())
    assert drill_res["status"] == "failed"
    assert drill_res["integrity_passed"] is False
    assert any("Checksum mismatch" in f for f in drill_res["checksum_failures"])


def test_drill_corrupted_archive_handles_gracefully():
    corrupted_bytes = b"not a valid tar.gz stream"
    res = perform_disaster_recovery_drill(corrupted_bytes)
    assert res["status"] == "failed"
    assert res["integrity_passed"] is False
    assert "corruption" in res["error"]
