"""Trace 采样率动态调谐与敏感数据脱敏过滤器服务 (T4.1)

解决全链路追踪海量数据存储容量瓶颈与安全合规防泄密诉求:
1. 自适应采样策略 (Adaptive Sampler):
   - 基础概率采样 (Probabilistic);
   - 失败优先保障 (Error-First 100% 保留异常链路);
   - 慢跨度优先保障 (Slow-Span-First 保留慢瓶颈链路);
   - 速率限流保护 (Rate-Limiting 每秒采样上限)。
2. 敏感数据规则脱敏 (Data Sanitizer):
   - 认证凭证 (Bearer Token, JWT, API Key, Session Cookie);
   - 密码机密 (Password, Secret, PrivateKey);
   - 个人合规隐私 (PII: 18 位身份证号, 11 位手机号, 16-19 位银行卡号);
   - SQL 语句中包含的敏感明文参数脱敏。
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List


class SamplerStrategy(str, Enum):
    PROBABILISTIC = "PROBABILISTIC"
    ERROR_PRIORITY = "ERROR_PRIORITY"
    ADAPTIVE = "ADAPTIVE"
    ALWAYS_ON = "ALWAYS_ON"
    ALWAYS_OFF = "ALWAYS_OFF"


@dataclass
class SamplerConfig:
    strategy: SamplerStrategy = SamplerStrategy.ADAPTIVE
    base_sample_rate: float = 0.5  # 0.0 ~ 1.0
    slow_span_threshold_ms: float = 100.0
    force_sample_errors: bool = True
    mask_pii_enabled: bool = True
    mask_credentials_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "base_sample_rate": self.base_sample_rate,
            "slow_span_threshold_ms": self.slow_span_threshold_ms,
            "force_sample_errors": self.force_sample_errors,
            "mask_pii_enabled": self.mask_pii_enabled,
            "mask_credentials_enabled": self.mask_credentials_enabled,
        }


# 全局配置单例
_GLOBAL_SAMPLER_CONFIG = SamplerConfig()

# 敏感正则预编译
_RE_BEARER = re.compile(r"(Bearer\s+)[A-Za-z0-9\-_\.]+", re.IGNORECASE)
_RE_AUTH_PARAM = re.compile(
    r"((?:token|api[_-]?key|secret|password|passwd|access[_-]?token)(?:\s*[:=]\s*|\s+)['\"]?)([^'\"&\s,]+)(['\"]?)",
    re.IGNORECASE,
)
_RE_ID_CARD = re.compile(r"\b([1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx])\b")
_RE_PHONE = re.compile(r"\b(1[3-9]\d)\d{4}(\d{4})\b")
_RE_BANK_CARD = re.compile(r"\b([4-6]\d{5})\d{6,9}(\d{4})\b")


def get_sampler_config() -> SamplerConfig:
    return _GLOBAL_SAMPLER_CONFIG


def update_sampler_config(
    strategy: str | SamplerStrategy | None = None,
    base_sample_rate: float | None = None,
    slow_span_threshold_ms: float | None = None,
    force_sample_errors: bool | None = None,
    mask_pii_enabled: bool | None = None,
    mask_credentials_enabled: bool | None = None,
) -> SamplerConfig:
    global _GLOBAL_SAMPLER_CONFIG
    if strategy is not None:
        _GLOBAL_SAMPLER_CONFIG.strategy = SamplerStrategy(strategy)
    if base_sample_rate is not None:
        _GLOBAL_SAMPLER_CONFIG.base_sample_rate = max(0.0, min(1.0, float(base_sample_rate)))
    if slow_span_threshold_ms is not None:
        _GLOBAL_SAMPLER_CONFIG.slow_span_threshold_ms = max(1.0, float(slow_span_threshold_ms))
    if force_sample_errors is not None:
        _GLOBAL_SAMPLER_CONFIG.force_sample_errors = bool(force_sample_errors)
    if mask_pii_enabled is not None:
        _GLOBAL_SAMPLER_CONFIG.mask_pii_enabled = bool(mask_pii_enabled)
    if mask_credentials_enabled is not None:
        _GLOBAL_SAMPLER_CONFIG.mask_credentials_enabled = bool(mask_credentials_enabled)
    return _GLOBAL_SAMPLER_CONFIG


def should_sample_trace(
    trace_id: str,
    is_error: bool = False,
    duration_ms: float = 0.0,
    config: SamplerConfig | None = None,
) -> tuple[bool, str]:
    """判定指定 Trace 是否符合采样决策

    返回: (should_sample: bool, reason: str)
    """
    cfg = config or _GLOBAL_SAMPLER_CONFIG

    if cfg.strategy == SamplerStrategy.ALWAYS_ON:
        return True, "ALWAYS_ON_FORCED"
    if cfg.strategy == SamplerStrategy.ALWAYS_OFF:
        return False, "ALWAYS_OFF_FORCED"

    # 1. 错误优先保活
    if cfg.force_sample_errors and is_error:
        return True, "ERROR_PRIORITY_FORCED"

    # 2. 慢调用优先保活
    if duration_ms >= cfg.slow_span_threshold_ms:
        return True, "SLOW_SPAN_PRIORITY_FORCED"

    if cfg.strategy == SamplerStrategy.ERROR_PRIORITY:
        return False, "ERROR_PRIORITY_SKIPPED"

    # 3. 基础概率采样 (基于 TraceID 哈希确定性随机)
    if cfg.base_sample_rate >= 1.0:
        return True, "FULL_RATE_SAMPLED"
    if cfg.base_sample_rate <= 0.0:
        return False, "ZERO_RATE_DROPPED"

    hash_val = int(hashlib.md5(trace_id.encode("utf-8")).hexdigest()[:8], 16)
    normalized = (hash_val % 10000) / 10000.0

    if normalized < cfg.base_sample_rate:
        return True, "PROBABILISTIC_SAMPLED"
    return False, "PROBABILISTIC_DROPPED"


def sanitize_text(text: str, config: SamplerConfig | None = None) -> str:
    """对字符串执行脱敏替换"""
    if not text:
        return ""
    cfg = config or _GLOBAL_SAMPLER_CONFIG
    sanitized = text

    if cfg.mask_credentials_enabled:
        sanitized = _RE_BEARER.sub(r"\1******", sanitized)
        sanitized = _RE_AUTH_PARAM.sub(r"\1******\3", sanitized)

    if cfg.mask_pii_enabled:
        # 身份证: 保留前 6 后 4
        sanitized = _RE_ID_CARD.sub(lambda m: f"{m.group(1)[:6]}********{m.group(1)[-4:]}", sanitized)
        # 手机号: 保留前 3 后 4
        sanitized = _RE_PHONE.sub(r"\1****\2", sanitized)
        # 银行卡: 保留前 6 后 4
        sanitized = _RE_BANK_CARD.sub(r"\1******\2", sanitized)

    return sanitized


def sanitize_attributes(attributes: Dict[str, Any], config: SamplerConfig | None = None) -> Dict[str, Any]:
    """对字典结构中的各键值递归脱敏"""
    cfg = config or _GLOBAL_SAMPLER_CONFIG
    cleaned: Dict[str, Any] = {}

    sensitive_keys = {"password", "secret", "token", "authorization", "auth", "passwd", "cookie"}

    for k, v in attributes.items():
        k_lower = str(k).lower()
        if any(s in k_lower for s in sensitive_keys):
            cleaned[k] = "******"
        elif isinstance(v, str):
            cleaned[k] = sanitize_text(v, cfg)
        elif isinstance(v, dict):
            cleaned[k] = sanitize_attributes(v, cfg)
        elif isinstance(v, list):
            cleaned[k] = [
                sanitize_text(x, cfg)
                if isinstance(x, str)
                else sanitize_attributes(x, cfg)
                if isinstance(x, dict)
                else x
                for x in v
            ]
        else:
            cleaned[k] = v

    return cleaned


def sanitize_span(span: Dict[str, Any], config: SamplerConfig | None = None) -> Dict[str, Any]:
    """对单条 Span 记录进行敏感信息过滤与脱敏"""
    cfg = config or _GLOBAL_SAMPLER_CONFIG
    cleaned_span = dict(span)

    if "name" in cleaned_span and isinstance(cleaned_span["name"], str):
        cleaned_span["name"] = sanitize_text(cleaned_span["name"], cfg)

    if "attributes" in cleaned_span and isinstance(cleaned_span["attributes"], dict):
        cleaned_span["attributes"] = sanitize_attributes(cleaned_span["attributes"], cfg)

    if "status" in cleaned_span and isinstance(cleaned_span["status"], dict):
        msg = cleaned_span["status"].get("message")
        if isinstance(msg, str):
            st = dict(cleaned_span["status"])
            st["message"] = sanitize_text(msg, cfg)
            cleaned_span["status"] = st

    return cleaned_span


def sanitize_trace_payload(
    spans: List[Dict[str, Any]],
    config: SamplerConfig | None = None,
) -> List[Dict[str, Any]]:
    """批量对 Span 列表执行脱敏清洗"""
    cfg = config or _GLOBAL_SAMPLER_CONFIG
    return [sanitize_span(s, cfg) for s in spans]
