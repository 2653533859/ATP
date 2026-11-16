"""探针：解密模型凭据 -> 最小视觉调用；并扫描注册真机。"""

import asyncio, os, sys
from pathlib import Path

sys.path.insert(0, "backend")

REPO = Path(".").resolve()
DST_DIR = REPO / ".local-run" / "android-agent-m2-live-20261111" / "data"


def load_env(path):
    vals = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in {"'", '"'}:
            v = v[1:-1]
        vals[k.strip()] = v
    return vals


env = load_env(REPO / ".env")
for k in ("APP_SECRET_KEY", "FIRST_ADMIN_PASSWORD", "FIRST_ADMIN_USERNAME", "FIRST_ADMIN_EMAIL", "ENCRYPTION_KEY"):
    if k in env:
        os.environ[k] = env[k]
os.environ["APP_ENV"] = "local"
os.environ["ATP_LOCAL_MODE"] = "true"
os.environ["ATP_LOCAL_DATA_DIR"] = str(DST_DIR)

from app.core.encryption import decrypt
import sqlite3

c = sqlite3.connect(DST_DIR / "atp.sqlite3")
row = c.execute(
    "select id,name,provider,model_name,supports_vision,enabled,endpoint,api_key_encrypted,default_params from ai_llm_configs where id=1"
).fetchone()
print("config:", row[:7])
try:
    key = decrypt(row[7])
    print("api key decrypted, len:", len(key), "prefix:", key[:4] + "..." if key else "(empty)")
except Exception as exc:
    print("DECRYPT FAILED:", type(exc).__name__, exc)
    sys.exit(1)

from app.services.ai_case.llm_client import LLMRequest, call_llm


async def probe():
    req = LLMRequest(
        provider=row[2],
        api_key=key,
        model_name=row[3],
        endpoint=row[6],
        prompt='Reply with exactly this JSON: {"ok": true}',
        max_tokens=64,
        timeout_seconds=45.0,
    )
    try:
        resp = await call_llm(req)
        print("MODEL OK ->", resp.text[:200].replace("\n", " "))
        return True
    except Exception as exc:
        print("MODEL FAILED:", type(exc).__name__, str(exc)[:300])
        return False


ok = asyncio.run(probe())
print("model_reachable:", ok)
