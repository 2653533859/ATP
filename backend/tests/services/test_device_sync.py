import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.dialects import postgresql

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.adb_service import AdbDeviceInfo
from app.services.device_sync import _build_upsert_stmt


def test_build_upsert_stmt_uses_postgres_on_conflict():
    info = AdbDeviceInfo(serial="emulator-5554", status="device", model="Pixel")
    stmt = _build_upsert_stmt(info, datetime.now(timezone.utc))
    sql = str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    sql_upper = sql.upper()

    assert "ON CONFLICT (SERIAL) DO UPDATE" in sql_upper
    assert "COALESCE" in sql_upper
    assert "CASE WHEN" in sql_upper
