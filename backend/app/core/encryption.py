"""
敏感配置加密/解密工具

使用 Fernet 对称加密。密钥从 ENCRYPTION_KEY 环境变量读取，
若未配置则从 APP_SECRET_KEY 派生。
"""
import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.ENCRYPTION_KEY
        if not key:
            # 从 APP_SECRET_KEY 派生 32 字节 key
            derived = hashlib.sha256(settings.APP_SECRET_KEY.encode()).digest()
            key = base64.urlsafe_b64encode(derived).decode()
        _fernet = Fernet(key)
    return _fernet


def encrypt(plaintext: str) -> str:
    """加密明文字符串，返回 base64 编码密文"""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """解密密文字符串，返回明文"""
    return _get_fernet().decrypt(ciphertext.encode()).decode()


# 各配置类型中需要加密的字段
SENSITIVE_KEYS = {
    "api_token", "password", "secret", "token",
    "webhook_url",  # webhook URL 包含 access_token
}


def mask_config(config: dict) -> dict:
    """将配置中的敏感字段脱敏为 ******"""
    masked = {}
    for k, v in config.items():
        if k in SENSITIVE_KEYS and isinstance(v, str) and v:
            masked[k] = "******"
        else:
            masked[k] = v
    return masked


def encrypt_config(config: dict) -> dict:
    """对配置中的敏感字段进行 Fernet 加密"""
    result = dict(config)
    for k in SENSITIVE_KEYS:
        v = result.get(k)
        if isinstance(v, str) and v and v != "******":
            result[k] = encrypt(v)
    return result


def decrypt_config(config: dict) -> dict:
    """对配置中的加密敏感字段进行解密"""
    result = dict(config)
    for k in SENSITIVE_KEYS:
        v = result.get(k)
        if isinstance(v, str) and v:
            try:
                result[k] = decrypt(v)
            except Exception:
                pass  # 未加密的旧数据，保持原值
    return result


def decrypt_env_vars(variables) -> dict:
    """将 EnvVariable 列表转为 key→value 字典，自动解密 is_secret 字段"""
    result = {}
    for v in variables:
        if v.is_secret and v.value:
            try:
                result[v.key] = decrypt(v.value)
            except Exception:
                result[v.key] = v.value
        else:
            result[v.key] = v.value
    return result
