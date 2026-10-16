"""跨环境配置漂移自动探测与环境变量差分比对器 (T2.1)。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class DriftSeverity(str, Enum):
    """配置漂移风险等级。"""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    IDENTICAL = "IDENTICAL"


class DriftType(str, Enum):
    """配置差异类型。"""

    MISSING_IN_TARGET = "MISSING_IN_TARGET"
    EXTRA_IN_TARGET = "EXTRA_IN_TARGET"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    SECURITY_SENSITIVE_LEAK = "SECURITY_SENSITIVE_LEAK"


@dataclass
class ConfigDriftItem:
    """单个配置项漂移差分明细。"""

    key: str
    base_value: Any
    target_value: Any
    drift_type: DriftType
    severity: DriftSeverity
    risk_explanation: str
    remediation_suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "base_value": self.base_value,
            "target_value": self.target_value,
            "drift_type": self.drift_type.value,
            "severity": self.severity.value,
            "risk_explanation": self.risk_explanation,
            "remediation_suggestion": self.remediation_suggestion,
        }


@dataclass
class ConfigDriftReport:
    """跨环境配置漂移全景审计报告。"""

    report_id: str
    service_name: str
    base_env: str
    target_env: str
    total_keys_checked: int
    identical_count: int
    drift_count: int
    highest_severity: DriftSeverity
    consistency_score_pct: float  # 一致性得分 0~100%
    drifts: list[ConfigDriftItem]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "service_name": self.service_name,
            "base_env": self.base_env,
            "target_env": self.target_env,
            "total_keys_checked": self.total_keys_checked,
            "identical_count": self.identical_count,
            "drift_count": self.drift_count,
            "highest_severity": self.highest_severity.value,
            "consistency_score_pct": round(self.consistency_score_pct, 1),
            "drifts": [d.to_dict() for d in self.drifts],
            "created_at": self.created_at.isoformat(),
        }


# 全局配置快照与报告仓库
_ENV_CONFIG_SNAPSHOTS: dict[str, dict[str, Any]] = {}  # key: f"{env}:{service}"
_CONFIG_DRIFT_REPORTS: dict[str, ConfigDriftReport] = {}

# 敏感与高危键名模式正则
_CRITICAL_KEY_PATTERNS = [
    re.compile(r"(secret|password|private_key|token|credential|auth_key)", re.IGNORECASE),
    re.compile(r"(payment_gateway|order_sign_key|alipay|wechat_pay)", re.IGNORECASE),
]
_HIGH_KEY_PATTERNS = [
    re.compile(r"(timeout|max_connections|thread_pool|pool_size|concurrency)", re.IGNORECASE),
    re.compile(r"(db_host|database_url|redis_host|kafka_broker)", re.IGNORECASE),
]


def clear_config_drift_store() -> None:
    """清空配置与报告仓库（单测专用）。"""
    _ENV_CONFIG_SNAPSHOTS.clear()
    _CONFIG_DRIFT_REPORTS.clear()


def register_environment_config_snapshot(
    env_name: str,
    service_name: str,
    configs: dict[str, Any],
) -> dict[str, Any]:
    """登记或更新某个环境微服务的最新配置快照。"""
    store_key = f"{env_name.lower()}:{service_name.lower()}"
    _ENV_CONFIG_SNAPSHOTS[store_key] = {
        "env_name": env_name,
        "service_name": service_name,
        "configs": configs,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "message": f"环境 [{env_name}] 微服务 [{service_name}] 配置快照登记成功",
        "store_key": store_key,
        "keys_count": len(configs),
    }


def _classify_severity(
    key: str, drift_type: DriftType, base_val: Any, target_val: Any
) -> tuple[DriftSeverity, str, str]:
    """根据键名特征与差异模式判定严重度、风险说明与修复建议。"""
    # 1. 密钥敏感项探测
    for pat in _CRITICAL_KEY_PATTERNS:
        if pat.search(key):
            if drift_type == DriftType.VALUE_MISMATCH and base_val != target_val:
                # 若生产密钥在低环境出现相同或不安全明文
                return (
                    DriftSeverity.CRITICAL,
                    f"安全敏感鉴权/密钥项 [{key}] 在两环境间存在漂移或明文泄露风险。",
                    "核对安全凭据隔离规范，确保开发/测试环境使用独立且经过脱敏的测试凭证。",
                )
            elif drift_type == DriftType.MISSING_IN_TARGET:
                return (
                    DriftSeverity.CRITICAL,
                    f"生产环境关键安全凭证 [{key}] 在目标测试环境缺失，可能导致服务启动校验失败。",
                    "在测试环境补齐对应模拟凭证或启用 Mock 授权模式。",
                )

    # 2. 超时、并发连接池与核心中间件项
    for pat in _HIGH_KEY_PATTERNS:
        if pat.search(key):
            if drift_type == DriftType.VALUE_MISMATCH:
                return (
                    DriftSeverity.HIGH,
                    f"核心性能与中间件参数 [{key}] 差异较大 (基准: {base_val}, 目标: {target_val})，可能引发超时不一致或连接池饥饿。",
                    f"建议将测试环境参数对齐或保持在合理比例，防止性能测试失真。",
                )
            elif drift_type == DriftType.MISSING_IN_TARGET:
                return (
                    DriftSeverity.HIGH,
                    f"中间件连接配置 [{key}] 在目标环境未配置，服务可能回退至不可预期默认值。",
                    f"补齐 [{key}] 配置项，明确指定目标测试中间件地址。",
                )

    # 3. 常规缺失或额外字段
    if drift_type == DriftType.MISSING_IN_TARGET:
        return (
            DriftSeverity.MEDIUM,
            f"目标环境缺少基准环境已有的配置项 [{key}]。",
            f"评估该配置项是否为新增特性开关，并在测试环境中补齐对应设置。",
        )
    elif drift_type == DriftType.EXTRA_IN_TARGET:
        return (
            DriftSeverity.LOW,
            f"目标环境存在额外的冗余临时配置项 [{key}]。",
            f"确认是否为本地联调遗留的临时调试变量，若非必要建议清理保持环境纯净。",
        )
    else:
        return (
            DriftSeverity.MEDIUM,
            f"配置项 [{key}] 两环境取值不一致 (基准: {base_val}, 目标: {target_val})。",
            f"审查取值差异是否符合当前环境预期。",
        )


def compare_environment_configs(
    base_env: str,
    target_env: str,
    service_name: str,
    base_configs: dict[str, Any] | None = None,
    target_configs: dict[str, Any] | None = None,
) -> ConfigDriftReport:
    """深度比对两环境微服务配置，输出差异明细与一致性审计报告。"""
    # 若未显式传入配置，尝试从仓库查找
    b_conf = base_configs
    if b_conf is None:
        b_entry = _ENV_CONFIG_SNAPSHOTS.get(f"{base_env.lower()}:{service_name.lower()}")
        b_conf = b_entry.get("configs", {}) if b_entry else {}

    t_conf = target_configs
    if t_conf is None:
        t_entry = _ENV_CONFIG_SNAPSHOTS.get(f"{target_env.lower()}:{service_name.lower()}")
        t_conf = t_entry.get("configs", {}) if t_entry else {}

    all_keys = sorted(set(b_conf.keys()) | set(t_conf.keys()))
    drifts: list[ConfigDriftItem] = []
    identical_count = 0

    severity_order = {
        DriftSeverity.CRITICAL: 4,
        DriftSeverity.HIGH: 3,
        DriftSeverity.MEDIUM: 2,
        DriftSeverity.LOW: 1,
        DriftSeverity.IDENTICAL: 0,
    }
    highest_sev = DriftSeverity.IDENTICAL

    for key in all_keys:
        in_base = key in b_conf
        in_target = key in t_conf

        if in_base and in_target:
            val_b = b_conf[key]
            val_t = t_conf[key]
            if val_b == val_t:
                identical_count += 1
            else:
                sev, expl, sug = _classify_severity(key, DriftType.VALUE_MISMATCH, val_b, val_t)
                drifts.append(
                    ConfigDriftItem(
                        key=key,
                        base_value=val_b,
                        target_value=val_t,
                        drift_type=DriftType.VALUE_MISMATCH,
                        severity=sev,
                        risk_explanation=expl,
                        remediation_suggestion=sug,
                    )
                )
                if severity_order[sev] > severity_order[highest_sev]:
                    highest_sev = sev
        elif in_base and not in_target:
            val_b = b_conf[key]
            sev, expl, sug = _classify_severity(key, DriftType.MISSING_IN_TARGET, val_b, None)
            drifts.append(
                ConfigDriftItem(
                    key=key,
                    base_value=val_b,
                    target_value=None,
                    drift_type=DriftType.MISSING_IN_TARGET,
                    severity=sev,
                    risk_explanation=expl,
                    remediation_suggestion=sug,
                )
            )
            if severity_order[sev] > severity_order[highest_sev]:
                highest_sev = sev
        else:
            val_t = t_conf[key]
            sev, expl, sug = _classify_severity(key, DriftType.EXTRA_IN_TARGET, None, val_t)
            drifts.append(
                ConfigDriftItem(
                    key=key,
                    base_value=None,
                    target_value=val_t,
                    drift_type=DriftType.EXTRA_IN_TARGET,
                    severity=sev,
                    risk_explanation=expl,
                    remediation_suggestion=sug,
                )
            )
            if severity_order[sev] > severity_order[highest_sev]:
                highest_sev = sev

    total_keys = len(all_keys)
    score = (identical_count / total_keys * 100.0) if total_keys > 0 else 100.0

    now = datetime.now(timezone.utc)
    report_id = f"drift_{service_name}_{base_env}_{target_env}_{int(now.timestamp())}"
    report = ConfigDriftReport(
        report_id=report_id,
        service_name=service_name,
        base_env=base_env,
        target_env=target_env,
        total_keys_checked=total_keys,
        identical_count=identical_count,
        drift_count=len(drifts),
        highest_severity=highest_sev,
        consistency_score_pct=score,
        drifts=drifts,
        created_at=now,
    )
    _CONFIG_DRIFT_REPORTS[report_id] = report
    return report


def get_config_drift_report(report_id: str) -> ConfigDriftReport | None:
    """按 ID 查询配置漂移报告。"""
    return _CONFIG_DRIFT_REPORTS.get(report_id)


def list_config_drift_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史配置漂移报告列表。"""
    reports = list(reversed(list(_CONFIG_DRIFT_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
