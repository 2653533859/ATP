"""M2 真机验证：隔离数据目录 + 现场库副本升级（v16 -> v21）。

本地模式只接受 _LOCAL_PROFILE_KEYS 白名单内的进程环境变量，因此这里显式从
仓库 .env 读取密钥后注入，绝不修改 .env 本身。
"""

import os, shutil, sys
from pathlib import Path

sys.path.insert(0, "backend")

REPO = Path(".").resolve()
SRC = REPO / ".local-data" / "atp.sqlite3"
DST_DIR = REPO / ".local-run" / "android-agent-m2-live-20261111" / "data"
DST = DST_DIR / "atp.sqlite3"
DST_DIR.mkdir(parents=True, exist_ok=True)
if not DST.exists():
    shutil.copy2(SRC, DST)
    print("copied source db ->", DST.name, DST.stat().st_size, "bytes")
else:
    print("reusing copy", DST.name, DST.stat().st_size, "bytes")


def load_env_file(path: Path) -> dict:
    values = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


env_values = load_env_file(REPO / ".env")
from importlib import import_module

config_mod = import_module("app.core.config") if False else None

# 白名单键（与 app.core.config._LOCAL_PROFILE_KEYS 对齐的必需项）
for key in ("APP_SECRET_KEY", "FIRST_ADMIN_PASSWORD", "FIRST_ADMIN_USERNAME", "FIRST_ADMIN_EMAIL", "ENCRYPTION_KEY"):
    if key in env_values:
        os.environ[key] = env_values[key]
        print("injected", key, "len", len(env_values[key]))
os.environ["APP_ENV"] = "local"
os.environ["ATP_LOCAL_MODE"] = "true"
os.environ["ATP_LOCAL_DATA_DIR"] = str(DST_DIR)
os.environ.setdefault("ADB_SCAN_ENABLED", "true")

from app.core.config import settings

print("APP_ENV:", settings.APP_ENV, "| local:", settings.ATP_LOCAL_MODE)
print("db path:", settings.LOCAL_DATABASE_PATH)

from app.core.local_schema import CURRENT_LOCAL_SCHEMA_VERSION, ensure_local_schema
from sqlalchemy import create_engine

engine = create_engine(f"sqlite:///{DST.as_posix()}")
version = ensure_local_schema(engine)
print("target:", CURRENT_LOCAL_SCHEMA_VERSION, "| migrated to:", version)

import sqlite3

c = sqlite3.connect(DST)
print(
    "agent tables:",
    sorted(r[0] for r in c.execute("select name from sqlite_master where type='table' and name like 'android_agent%'")),
)
print("projects:", c.execute("select id,name from projects").fetchall())
print("llm:", c.execute("select id,name,provider,model_name,supports_vision,endpoint from ai_llm_configs").fetchall())
print("devices:", c.execute("select id,serial,status from devices").fetchall())
