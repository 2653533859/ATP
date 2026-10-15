"""Sensitive Test Data and Credentials Dynamic Redaction Gateway (T4.1).

Detects and redacts Personally Identifiable Information (PII) including:
1. Chinese 11-digit mobile phone numbers (e.g. 138****5678)
2. Chinese 18-digit resident ID cards (e.g. 110101********1234)
3. 16-19 digit bank cards / credit cards (e.g. 6222********1234)
4. Email addresses (e.g. te***@example.com)
5. Sensitive credential keys (passwords, tokens, secrets, API keys)
6. Custom sensitive keywords / enterprise blacklist terms
"""

from __future__ import annotations

from copy import deepcopy
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Pattern: 11-digit Chinese mobile phone numbers
PHONE_REGEX = re.compile(r"(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)")

# Pattern: 18-digit Chinese Resident Identity Card numbers
ID_CARD_REGEX = re.compile(
    r"(?<!\d)([1-9]\d{5})(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(\d{3}[\dXx])(?!\d)"
)

# Pattern: 16-19 digit Bank / UnionPay / Credit Card numbers
BANK_CARD_REGEX = re.compile(r"(?<!\d)([3-6]\d{3})(\d{8,11})(\d{4})(?!\d)")

# Pattern: Email addresses
EMAIL_REGEX = re.compile(r"([a-zA-Z0-9_.+-]{1,2})[a-zA-Z0-9_.+-]*(@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
SENSITIVE_KEY_REGEX = re.compile(
    r"(?i)^(password|passwd|secret|api[_-]?(?:key|token)|access[_-]?token|auth|token|private[_-]?key|jwt|authorization)$"
)


def mask_pii_text(text: str, custom_keywords: list[str] | None = None) -> str:
    """Mask PII patterns (phone, ID card, bank card, email) and custom keywords within a text string."""
    if not isinstance(text, str) or not text:
        return text

    # 1. Mask Phone Numbers: 13800138000 -> 138****8000
    res = PHONE_REGEX.sub(r"\g<1>****\g<3>", text)

    # 2. Mask 18-digit ID Cards: 110101199003071234 -> 110101********1234
    res = ID_CARD_REGEX.sub(r"\g<1>********\g<2>", res)

    # 3. Mask Bank Cards: 6222021234567890123 -> 6222********0123
    res = BANK_CARD_REGEX.sub(r"\g<1>********\g<3>", res)

    # 4. Mask Emails: alice@example.com -> al***@example.com
    res = EMAIL_REGEX.sub(r"\g<1>***\g<2>", res)

    # 5. Mask Custom Keywords / Blacklist
    if custom_keywords:
        for kw in custom_keywords:
            kw_clean = str(kw).strip()
            if kw_clean:
                res = re.sub(re.escape(kw_clean), "[REDACTED]", res, flags=re.IGNORECASE)

    return res


def redact_pii_data(data: Any, custom_keywords: list[str] | None = None) -> Any:
    """Recursively traverse and redact PII patterns and credential keys in arbitrary data structures."""
    if isinstance(data, str):
        return mask_pii_text(data, custom_keywords)

    if isinstance(data, dict):
        redacted_dict: dict[str, Any] = {}
        for k, v in data.items():
            key_str = str(k)
            # If the key itself names a sensitive credential, mask the value
            if SENSITIVE_KEY_REGEX.match(key_str):
                redacted_dict[k] = "******"
            else:
                redacted_dict[k] = redact_pii_data(v, custom_keywords)
        return redacted_dict

    if isinstance(data, list):
        return [redact_pii_data(item, custom_keywords) for item in data]

    if isinstance(data, tuple):
        return tuple(redact_pii_data(item, custom_keywords) for item in data)

    if isinstance(data, set):
        return {redact_pii_data(item, custom_keywords) for item in data}

    return data


def apply_pii_redaction_gateway(
    payload: Any,
    *,
    custom_keywords: list[str] | None = None,
    extra_sensitive_keys: list[str] | None = None,
) -> Any:
    """Entry point for the gateway to deep-copy and redact test response bodies, assertions, and logs."""
    cloned = deepcopy(payload)
    keywords = list(custom_keywords or [])
    if extra_sensitive_keys:
        keywords.extend(extra_sensitive_keys)
    return redact_pii_data(cloned, keywords)
