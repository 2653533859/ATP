"""尝试用候选 APP_SECRET_KEY 解密库中的模型凭据（只报告成功与否，不打印密钥）。"""

import base64, hashlib, os, sqlite3, sys
from pathlib import Path

sys.path.insert(0, "backend")
from cryptography.fernet import Fernet

REPO = Path(".").resolve()
DB = REPO / ".local-run" / "android-agent-m2-live-20261111" / "data" / "atp.sqlite3"


def read_env(path):
    vals = {}
    if not path.exists():
        return vals
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


c = sqlite3.connect(DB)
cipher = c.execute("select api_key_encrypted from ai_llm_configs where id=1").fetchone()[0]

candidates = {}
root_env = read_env(REPO / ".env")
if root_env.get("APP_SECRET_KEY"):
    candidates["repo .env"] = root_env["APP_SECRET_KEY"]
m0 = read_env(REPO / ".local-run" / "android-replay-e2e" / "secrets.env")
if m0.get("APP_SECRET_KEY"):
    candidates["m0 secrets.env"] = m0["APP_SECRET_KEY"]

print("ciphertext prefix:", cipher[:12], "len:", len(cipher))
for label, secret in candidates.items():
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()).decode()
    try:
        plain = Fernet(key).decrypt(cipher.encode()).decode()
        print(f"DECRYPT OK via {label} (secret len {len(secret)}), api key len {len(plain)}, prefix {plain[:3]}...")
    except Exception as exc:
        print(f"fail via {label} (secret len {len(secret)}): {type(exc).__name__}")
