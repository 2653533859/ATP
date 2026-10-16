"""生产敏感数据自适应规则脱敏与模式识别脱敏器 (T1.2)。

为微服务网关旁路捕获的生产镜像流量提供高保真安全脱敏能力：
1. 自动识别中国 11 位手机号、18 位居民身份证、16-19 位银行卡、邮箱、Bearer/JWT 凭证及密码高敏字段；
2. 提供 MASK (掩码)、HASH (SHA-256 伪名化一致性脱敏)、REDACT (完全抹除) 三大脱敏策略；
3. 支持嵌套 JSON 请求/响应体递归解析与就地脱敏，确保生产流量合规下发至测试环境。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class MaskingStrategy(str, Enum):
    MASK = "MASK"  # 掩码脱敏 (保留首尾部分字符，中间补 *)
    HASH = "HASH"  # 不可逆 SHA-256 伪名化 (保留业务关联一致性)
    REDACT = "REDACT"  # 完全置换为 [REDACTED]


class SensitiveCategory(str, Enum):
    PHONE = "PHONE"
    ID_CARD = "ID_CARD"
    BANK_CARD = "BANK_CARD"
    EMAIL = "EMAIL"
    JWT_TOKEN = "JWT_TOKEN"
    PASSWORD = "PASSWORD"
    CUSTOM = "CUSTOM"


# 标准 PII 文本识别正则
PHONE_REGEX = re.compile(r"(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)")
ID_CARD_REGEX = re.compile(
    r"(?<!\d)([1-9]\d{5})(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(\d{3}[\dXx])(?!\d)"
)
BANK_CARD_REGEX = re.compile(r"(?<!\d)([3-6]\d{3})(\d{8,11})(\d{4})(?!\d)")
EMAIL_REGEX = re.compile(r"([a-zA-Z0-9_.+-]{1,2})[a-zA-Z0-9_.+-]*(@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
JWT_TOKEN_REGEX = re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}")
BEARER_AUTH_REGEX = re.compile(r"(?i)(bearer\s+)([a-zA-Z0-9_\-\.=]{15,})")

# 敏感字段 Key 关键字匹配
SENSITIVE_KEY_REGEX = re.compile(
    r"(?i)^(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|private[_-]?key|cvv|card[_-]?cvv|id[_-]?card|idcard|id_number|bank[_-]?card|mobile|phone)$"
)


@dataclass
class SensitiveRule:
    rule_id: str
    name: str
    category: SensitiveCategory
    strategy: MaskingStrategy
    field_key_patterns: list[str] = field(default_factory=list)
    custom_keywords: list[str] = field(default_factory=list)
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "category": self.category.value,
            "strategy": self.strategy.value,
            "field_key_patterns": self.field_key_patterns,
            "custom_keywords": self.custom_keywords,
            "enabled": self.enabled,
        }


def _create_default_rules() -> list[SensitiveRule]:
    return [
        SensitiveRule(
            "rule_phone", "大陆手机号脱敏", SensitiveCategory.PHONE, MaskingStrategy.MASK, ["phone", "mobile"]
        ),
        SensitiveRule(
            "rule_id_card", "居民身份证号脱敏", SensitiveCategory.ID_CARD, MaskingStrategy.MASK, ["id_card", "idcard"]
        ),
        SensitiveRule(
            "rule_bank_card",
            "银行卡号脱敏",
            SensitiveCategory.BANK_CARD,
            MaskingStrategy.MASK,
            ["bank_card", "card_no"],
        ),
        SensitiveRule(
            "rule_email", "电子邮箱地址脱敏", SensitiveCategory.EMAIL, MaskingStrategy.MASK, ["email", "mail"]
        ),
        SensitiveRule(
            "rule_jwt",
            "JWT/Bearer 授权凭证脱敏",
            SensitiveCategory.JWT_TOKEN,
            MaskingStrategy.REDACT,
            ["authorization", "token"],
        ),
        SensitiveRule(
            "rule_password",
            "登录密码与密钥擦除",
            SensitiveCategory.PASSWORD,
            MaskingStrategy.REDACT,
            ["password", "secret", "pwd"],
        ),
    ]


_ACTIVE_RULES: list[SensitiveRule] = _create_default_rules()


def get_active_masking_rules() -> list[SensitiveRule]:
    """获取当前生效的敏感数据脱敏规则列表。"""
    return _ACTIVE_RULES


def reset_masking_rules() -> list[SensitiveRule]:
    """重置脱敏规则为系统出厂默认值。"""
    global _ACTIVE_RULES
    _ACTIVE_RULES = _create_default_rules()
    return _ACTIVE_RULES


def update_masking_rules(rules_data: list[dict[str, Any]]) -> list[SensitiveRule]:
    """更新或扩展脱敏规则配置。"""
    global _ACTIVE_RULES
    new_rules: list[SensitiveRule] = []
    for d in rules_data:
        try:
            cat = SensitiveCategory(d.get("category", "CUSTOM").upper())
        except ValueError:
            cat = SensitiveCategory.CUSTOM
        try:
            strat = MaskingStrategy(d.get("strategy", "MASK").upper())
        except ValueError:
            strat = MaskingStrategy.MASK

        new_rules.append(
            SensitiveRule(
                rule_id=d.get("rule_id", f"rule_{len(new_rules) + 1}"),
                name=d.get("name", "自定义脱敏规则"),
                category=cat,
                strategy=strat,
                field_key_patterns=d.get("field_key_patterns", []),
                custom_keywords=d.get("custom_keywords", []),
                enabled=bool(d.get("enabled", True)),
            )
        )
    _ACTIVE_RULES = new_rules
    return _ACTIVE_RULES


def hash_pseudonym(val: str, prefix: str = "hash:") -> str:
    """对高敏标识做不可逆 SHA-256 伪名化，保留业务关联一致性。"""
    sha = hashlib.sha256(val.encode("utf-8")).hexdigest()
    return f"{prefix}{sha[:12]}"


def mask_text_content(
    text: str,
    rules: list[SensitiveRule] | None = None,
    custom_keywords: list[str] | None = None,
) -> str:
    """对单段字符串执行多维正则扫描与模式脱敏。"""
    if not isinstance(text, str) or not text:
        return text

    rule_list = rules if rules is not None else _ACTIVE_RULES
    enabled_cats = {r.category for r in rule_list if r.enabled}

    res = text

    # 1. 手机号脱敏: 13800138000 -> 138****8000
    if SensitiveCategory.PHONE in enabled_cats:
        rule = next((r for r in rule_list if r.category == SensitiveCategory.PHONE and r.enabled), None)
        if rule and rule.strategy == MaskingStrategy.HASH:
            res = PHONE_REGEX.sub(lambda m: hash_pseudonym(m.group(0), "tel_hash:"), res)
        elif rule and rule.strategy == MaskingStrategy.REDACT:
            res = PHONE_REGEX.sub("[PHONE_REDACTED]", res)
        else:
            res = PHONE_REGEX.sub(r"\g<1>****\g<3>", res)

    # 2. 18 位身份证: 110101199003071234 -> 110101********1234
    if SensitiveCategory.ID_CARD in enabled_cats:
        rule = next((r for r in rule_list if r.category == SensitiveCategory.ID_CARD and r.enabled), None)
        if rule and rule.strategy == MaskingStrategy.HASH:
            res = ID_CARD_REGEX.sub(lambda m: hash_pseudonym(m.group(0), "id_hash:"), res)
        elif rule and rule.strategy == MaskingStrategy.REDACT:
            res = ID_CARD_REGEX.sub("[ID_CARD_REDACTED]", res)
        else:
            res = ID_CARD_REGEX.sub(r"\g<1>********\g<2>", res)

    # 3. 银行卡号: 6222021234567890123 -> 6222********0123
    if SensitiveCategory.BANK_CARD in enabled_cats:
        rule = next((r for r in rule_list if r.category == SensitiveCategory.BANK_CARD and r.enabled), None)
        if rule and rule.strategy == MaskingStrategy.HASH:
            res = BANK_CARD_REGEX.sub(lambda m: hash_pseudonym(m.group(0), "card_hash:"), res)
        elif rule and rule.strategy == MaskingStrategy.REDACT:
            res = BANK_CARD_REGEX.sub("[BANK_CARD_REDACTED]", res)
        else:
            res = BANK_CARD_REGEX.sub(r"\g<1>********\g<3>", res)

    # 4. 电子邮箱: alice@example.com -> al***@example.com
    if SensitiveCategory.EMAIL in enabled_cats:
        rule = next((r for r in rule_list if r.category == SensitiveCategory.EMAIL and r.enabled), None)
        if rule and rule.strategy == MaskingStrategy.HASH:
            res = EMAIL_REGEX.sub(lambda m: hash_pseudonym(m.group(0), "mail_hash:"), res)
        elif rule and rule.strategy == MaskingStrategy.REDACT:
            res = EMAIL_REGEX.sub("[EMAIL_REDACTED]", res)
        else:
            res = EMAIL_REGEX.sub(r"\g<1>***\g<2>", res)

    # 5. Bearer / JWT 凭证脱敏: Bearer eyJ... -> Bearer [REDACTED_JWT]
    if SensitiveCategory.JWT_TOKEN in enabled_cats:
        res = BEARER_AUTH_REGEX.sub(r"\g<1>[REDACTED_AUTH_TOKEN]", res)
        res = JWT_TOKEN_REGEX.sub("[REDACTED_JWT_TOKEN]", res)

    # 6. 自定义黑名单关键词
    all_kws: list[str] = list(custom_keywords or [])
    for r in rule_list:
        if r.enabled and r.custom_keywords:
            all_kws.extend(r.custom_keywords)

    for kw in set(all_kws):
        kw_clean = str(kw).strip()
        if kw_clean:
            res = re.sub(re.escape(kw_clean), "[REDACTED]", res, flags=re.IGNORECASE)

    return res


def mask_payload_recursively(
    data: Any,
    parent_key: str | None = None,
    rules: list[SensitiveRule] | None = None,
    custom_keywords: list[str] | None = None,
) -> Any:
    """递归遍历 dict / list / JSON 字符串，根据字段名规则与值内容正则深度脱敏。"""
    if data is None:
        return None

    rule_list = rules if rules is not None else _ACTIVE_RULES

    # 1. 字典递归清洗
    if isinstance(data, dict):
        masked_dict: dict[str, Any] = {}
        for k, v in data.items():
            k_str = str(k)
            # 检查字段名是否命中敏感字段（如 password, token, secret）
            is_sensitive_key = bool(SENSITIVE_KEY_REGEX.match(k_str))
            matching_rule = None
            for r in rule_list:
                if r.enabled and any(pat.lower() in k_str.lower() for pat in r.field_key_patterns):
                    matching_rule = r
                    break

            if is_sensitive_key or matching_rule:
                rule_strat = matching_rule.strategy if matching_rule else MaskingStrategy.REDACT
                if rule_strat == MaskingStrategy.REDACT:
                    masked_dict[k] = "[REDACTED]"
                elif rule_strat == MaskingStrategy.HASH and isinstance(v, (str, int, float)):
                    masked_dict[k] = hash_pseudonym(str(v))
                elif isinstance(v, str):
                    masked_dict[k] = mask_text_content(v, rule_list, custom_keywords)
                else:
                    masked_dict[k] = "[REDACTED]"
            else:
                masked_dict[k] = mask_payload_recursively(v, k_str, rule_list, custom_keywords)
        return masked_dict

    # 2. 列表递归清洗
    if isinstance(data, list):
        return [mask_payload_recursively(item, parent_key, rule_list, custom_keywords) for item in data]

    # 3. 字符串检查是否是内置 JSON
    if isinstance(data, str):
        trimmed = data.strip()
        if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
            try:
                parsed = json.loads(trimmed)
                cleaned = mask_payload_recursively(parsed, parent_key, rule_list, custom_keywords)
                return json.dumps(cleaned, ensure_ascii=False)
            except Exception:
                pass
        return mask_text_content(data, rule_list, custom_keywords)

    return data


def mask_captured_traffic_item(
    traffic_item: dict[str, Any],
    rules: list[SensitiveRule] | None = None,
    custom_keywords: list[str] | None = None,
) -> dict[str, Any]:
    """对单条网关旁路截获的流量条目进行全局脱敏清洗。

    处理范围包含: Headers (Authorization/Cookie 等)、Query 参数、Request Body、Response Body。
    """
    item = deepcopy(traffic_item)

    # 1. Headers 脱敏 (特别是 Authorization, Cookie, Token)
    if "headers" in item and isinstance(item["headers"], dict):
        masked_headers: dict[str, str] = {}
        for hk, hv in item["headers"].items():
            if str(hk).lower() in ("authorization", "token", "x-auth-token", "cookie", "proxy-authorization"):
                masked_headers[hk] = mask_text_content(str(hv), rules, custom_keywords)
            else:
                masked_headers[hk] = mask_text_content(str(hv), rules, custom_keywords)
        item["headers"] = masked_headers

    # 2. Query 参数脱敏
    if "query_params" in item and isinstance(item["query_params"], dict):
        item["query_params"] = mask_payload_recursively(item["query_params"], None, rules, custom_keywords)

    # 3. Request Body 脱敏
    if "request_body" in item and isinstance(item["request_body"], str) and item["request_body"]:
        item["request_body"] = mask_payload_recursively(item["request_body"], None, rules, custom_keywords)

    # 4. Response Body 脱敏
    if "response_body" in item and isinstance(item["response_body"], str) and item["response_body"]:
        item["response_body"] = mask_payload_recursively(item["response_body"], None, rules, custom_keywords)

    # 5. 打上脱敏标志
    tags = item.get("tags", {})
    tags["data_masked"] = "true"
    item["tags"] = tags

    return item


def batch_mask_traffic_items(
    items: list[dict[str, Any]],
    rules: list[SensitiveRule] | None = None,
    custom_keywords: list[str] | None = None,
) -> list[dict[str, Any]]:
    """批量清洗并脱敏流量条目列表。"""
    return [mask_captured_traffic_item(it, rules, custom_keywords) for it in items]
