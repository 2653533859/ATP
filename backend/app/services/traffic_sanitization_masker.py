"""敏感数据实时脱敏与隐私字段掩码器服务 (T1.1)

在生产流量镜像采集与录制回放中提供金融级数据隐私安全脱敏保障:
1. 手机号、身份证、银行卡、邮箱、密码、JWT Token 与密钥特征正则与启发式识别;
2. 星号掩码 (MASK)、加盐哈希 (HASH_SALT) 与确定性同构合成数据置换 (SYNTHETIC_REPLACE);
3. 递归遍历 Headers、Query、Body 嵌套结构脱敏 (sanitize_traffic_payload);
4. 完整的脱敏审计元数据跟踪 (SanitizationAuditTrail)。
"""

from __future__ import annotations

import copy
import enum
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple


class SensitiveDataType(str, enum.Enum):
    PHONE = "PHONE"  # 11 位手机号
    ID_CARD = "ID_CARD"  # 18 位身份证
    BANK_CARD = "BANK_CARD"  # 16~19 位银行卡
    EMAIL = "EMAIL"  # 电子邮箱
    PASSWORD = "PASSWORD"  # 密码明文
    JWT_TOKEN = "JWT_TOKEN"  # 授权 Token / JWT
    GENERIC_SECRET = "GENERIC_SECRET"  # 通用 API Key / 密钥


class SanitizationMode(str, enum.Enum):
    MASK = "MASK"  # 星号掩码 (如 138****1234)
    HASH_SALT = "HASH_SALT"  # 加盐哈希 (如 hash_9a3f...)
    SYNTHETIC_REPLACE = "SYNTHETIC_REPLACE"  # 确定性同构假数据置换


# 敏感键名启发式模式 (小写匹配)
_SENSITIVE_KEY_PATTERNS: Dict[SensitiveDataType, List[str]] = {
    SensitiveDataType.PASSWORD: ["password", "pwd", "passwd", "passcode", "secret_key"],
    SensitiveDataType.JWT_TOKEN: ["token", "authorization", "access_token", "refresh_token", "bearer"],
    SensitiveDataType.PHONE: ["phone", "mobile", "tel", "cellphone", "telephone"],
    SensitiveDataType.ID_CARD: ["id_card", "idcard", "id_number", "idno", "identity_card", "ssn"],
    SensitiveDataType.BANK_CARD: ["bank_card", "bankcard", "card_no", "cardno", "credit_card", "debit_card", "cvv"],
    SensitiveDataType.EMAIL: ["email", "mail", "user_email"],
    SensitiveDataType.GENERIC_SECRET: ["secret", "api_key", "apikey", "private_key", "client_secret"],
}

# 敏感取值正则特征
_REGEX_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_REGEX_ID_CARD = re.compile(
    r"(?<!\d)[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"
)
_REGEX_BANK_CARD = re.compile(r"(?<!\d)[1-9]\d{15,18}(?!\d)")
_REGEX_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_REGEX_JWT = re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}")


@dataclass
class SanitizationAuditTrail:
    total_fields_scanned: int = 0
    masked_field_count: int = 0
    detected_types: Set[SensitiveDataType] = field(default_factory=set)
    sanitized_paths: List[str] = field(default_factory=list)
    sanitized_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_fields_scanned": self.total_fields_scanned,
            "masked_field_count": self.masked_field_count,
            "detected_types": [t.value for t in self.detected_types],
            "sanitized_paths": self.sanitized_paths,
            "sanitized_at": self.sanitized_at,
        }


def mask_sensitive_value(
    val: str,
    data_type: SensitiveDataType,
    mode: SanitizationMode = SanitizationMode.MASK,
    salt: str = "atp_salt_2026",
) -> str:
    """对单个字符串进行掩码、加盐哈希或同构假数据置换"""
    if mode == SanitizationMode.HASH_SALT:
        h = hashlib.sha256(f"{val}:{salt}".encode("utf-8")).hexdigest()[:12]
        return f"hash_{h}"

    if mode == SanitizationMode.SYNTHETIC_REPLACE:
        h_int = int(hashlib.md5(f"{val}:{salt}".encode("utf-8")).hexdigest()[:8], 16)
        if data_type == SensitiveDataType.PHONE:
            return f"139{str(h_int).zfill(8)[:8]}"
        elif data_type == SensitiveDataType.ID_CARD:
            return f"11010119900101{str(h_int).zfill(4)[:4]}"
        elif data_type == SensitiveDataType.BANK_CARD:
            return f"622202{str(h_int).zfill(10)[:10]}"
        elif data_type == SensitiveDataType.EMAIL:
            return f"user_{str(h_int)[:6]}@synthetic.test"
        elif data_type == SensitiveDataType.PASSWORD:
            return "SyntheticP@ssword123!"
        elif data_type == SensitiveDataType.JWT_TOKEN:
            return f"eyJ_synthetic_header.eyJ_synthetic_payload_{str(h_int)[:6]}.signature"
        else:
            return f"synthetic_{str(h_int)[:8]}"

    # 默认模式: MASK
    if data_type == SensitiveDataType.PHONE:
        return f"{val[:3]}****{val[-4:]}" if len(val) >= 7 else "****"
    elif data_type == SensitiveDataType.ID_CARD:
        return f"{val[:6]}********{val[-4:]}" if len(val) >= 10 else "********"
    elif data_type == SensitiveDataType.BANK_CARD:
        return f"{val[:6]}******{val[-4:]}" if len(val) >= 10 else "******"
    elif data_type == SensitiveDataType.EMAIL:
        parts = val.split("@")
        if len(parts) == 2:
            name, domain = parts
            masked_name = f"{name[0]}***" if name else "***"
            return f"{masked_name}@{domain}"
        return "***@***"
    elif data_type == SensitiveDataType.PASSWORD:
        return "[MASKED_PASSWORD]"
    elif data_type == SensitiveDataType.JWT_TOKEN:
        return "Bearer [MASKED_TOKEN]" if val.lower().startswith("bearer ") else "[MASKED_JWT_TOKEN]"
    else:
        return "[MASKED_SECRET]"


def detect_value_sensitive_type(val: Any, key_name: Optional[str] = None) -> Optional[SensitiveDataType]:
    """根据键名启发式与取值正则推导敏感数据类型"""
    if not isinstance(val, str):
        return None

    # 1. 优先根据键名启发式判断
    if key_name:
        k_lower = key_name.lower().replace("-", "_")
        for s_type, keywords in _SENSITIVE_KEY_PATTERNS.items():
            if any(kw == k_lower or kw in k_lower for kw in keywords):
                return s_type

    # 2. 根据取值正则内容判断
    if _REGEX_PHONE.fullmatch(val):
        return SensitiveDataType.PHONE
    if _REGEX_ID_CARD.fullmatch(val):
        return SensitiveDataType.ID_CARD
    if _REGEX_BANK_CARD.fullmatch(val):
        return SensitiveDataType.BANK_CARD
    if _REGEX_EMAIL.fullmatch(val):
        return SensitiveDataType.EMAIL
    if _REGEX_JWT.search(val) or val.lower().startswith("bearer eyj"):
        return SensitiveDataType.JWT_TOKEN

    return None


def sanitize_traffic_payload(
    payload: Any,
    mode: SanitizationMode = SanitizationMode.MASK,
    salt: str = "atp_salt_2026",
    path_prefix: str = "$",
) -> Tuple[Any, SanitizationAuditTrail]:
    """递归遍历并深度脱敏任意嵌套的数据载荷 (Headers, Query, JSON Body)"""
    audit = SanitizationAuditTrail()

    def _walk(obj: Any, current_path: str, parent_key: Optional[str] = None) -> Any:
        audit.total_fields_scanned += 1

        if isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                p = f"{current_path}.{k}"
                # 检查键名是否属于敏感类型
                stype = detect_value_sensitive_type(v, key_name=str(k))
                if stype and isinstance(v, str):
                    audit.masked_field_count += 1
                    audit.detected_types.add(stype)
                    audit.sanitized_paths.append(p)
                    new_dict[k] = mask_sensitive_value(v, stype, mode=mode, salt=salt)
                else:
                    new_dict[k] = _walk(v, p, parent_key=str(k))
            return new_dict

        elif isinstance(obj, list):
            new_list = []
            for idx, item in enumerate(obj):
                p = f"{current_path}[{idx}]"
                stype = detect_value_sensitive_type(item, key_name=parent_key)
                if stype and isinstance(item, str):
                    audit.masked_field_count += 1
                    audit.detected_types.add(stype)
                    audit.sanitized_paths.append(p)
                    new_list.append(mask_sensitive_value(item, stype, mode=mode, salt=salt))
                else:
                    new_list.append(_walk(item, p, parent_key=parent_key))
            return new_list

        elif isinstance(obj, str):
            stype = detect_value_sensitive_type(obj, key_name=parent_key)
            if stype:
                audit.masked_field_count += 1
                audit.detected_types.add(stype)
                audit.sanitized_paths.append(current_path)
                return mask_sensitive_value(obj, stype, mode=mode, salt=salt)
            return obj

        return copy.deepcopy(obj)

    sanitized = _walk(payload, path_prefix)
    return sanitized, audit
