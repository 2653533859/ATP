"""IPA 签名合规与 Provisioning 描述文件验真器服务 (T4.2)

解决 iOS 自动化执行前由于签名过期、TeamID 不匹配或 UDID 未加白导致的部署失败问题:
1. embedded.mobileprovision 描述文件智能解析 (TeamID, Expiration, ProvisionedDevices);
2. 签名类型智能判定 (DEVELOPMENT, AD_HOC, ENTERPRISE, APP_STORE);
3. 目标真机 UDID 白名单提前阻断校验 (避免部署耗时后报 0xe8008015 错误);
4. 证书过期风险预警与签名合规审计报告。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class IosSignatureType(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    AD_HOC = "AD_HOC"
    ENTERPRISE = "ENTERPRISE"
    APP_STORE = "APP_STORE"
    UNKNOWN = "UNKNOWN"


class IpaValidationVerdict(str, Enum):
    VALID = "VALID"
    CERTIFICATE_EXPIRED = "CERTIFICATE_EXPIRED"
    DEVICE_NOT_PROVISIONED = "DEVICE_NOT_PROVISIONED"
    BUNDLE_ID_MISMATCH = "BUNDLE_ID_MISMATCH"
    INVALID_METADATA = "INVALID_METADATA"


@dataclass
class IpaSigningValidationReport:
    validation_id: str
    bundle_id: str
    team_id: str
    team_name: str
    signature_type: IosSignatureType
    verdict: IpaValidationVerdict
    is_deployable: bool
    target_device_udid: Optional[str]
    is_device_provisioned: bool
    expiration_date: str
    days_until_expiration: int
    message: str
    validated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "bundle_id": self.bundle_id,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "signature_type": self.signature_type.value,
            "verdict": self.verdict.value,
            "is_deployable": self.is_deployable,
            "target_device_udid": self.target_device_udid,
            "is_device_provisioned": self.is_device_provisioned,
            "expiration_date": self.expiration_date,
            "days_until_expiration": self.days_until_expiration,
            "message": self.message,
            "validated_at": self.validated_at,
        }


# 全局轻量级签名校验历史
_VALIDATION_HISTORY: List[IpaSigningValidationReport] = []


def clear_validation_history() -> None:
    _VALIDATION_HISTORY.clear()


def list_validation_reports(limit: int = 50) -> List[Dict[str, Any]]:
    return [r.to_dict() for r in reversed(_VALIDATION_HISTORY[-limit:])]


def validate_ipa_signing(
    provisioning_data: Dict[str, Any],
    target_device_udid: Optional[str] = None,
    expected_bundle_id: Optional[str] = None,
    now: datetime | None = None,
) -> IpaSigningValidationReport:
    """对 IPA 包的 embedded.mobileprovision 属性与目标真机 UDID 进行合规验真"""
    current_time = now or datetime.now(timezone.utc)
    validation_id = f"val_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')[:17]}"

    raw_team = provisioning_data.get("team_id")
    if not raw_team:
        team_ident = provisioning_data.get("TeamIdentifier")
        if isinstance(team_ident, list) and team_ident:
            raw_team = team_ident[0]
        elif isinstance(team_ident, str):
            raw_team = team_ident
    team_id = str(raw_team or "UNKNOWN")
    team_name = str(provisioning_data.get("team_name") or provisioning_data.get("TeamName") or "Apple Developer Team")
    bundle_id = str(
        provisioning_data.get("bundle_id") or provisioning_data.get("application_identifier") or "com.unknown.app"
    )

    # 去除 TeamID 前缀 (如 9ABC123456.com.example.app -> com.example.app)
    if "." in bundle_id and team_id != "UNKNOWN" and bundle_id.startswith(team_id + "."):
        bundle_id = bundle_id[len(team_id) + 1 :]

    # 1. 签名类型推断
    provisions_all = bool(provisioning_data.get("ProvisionsAllDevices", False))
    provisioned_devices = (
        provisioning_data.get("ProvisionedDevices") or provisioning_data.get("provisioned_devices") or []
    )
    if isinstance(provisioned_devices, str):
        provisioned_devices = [provisioned_devices]

    if provisions_all:
        sig_type = IosSignatureType.ENTERPRISE
    elif (
        provisioning_data.get("get_task_allow") is True
        or provisioning_data.get("Entitlements", {}).get("get-task-allow") is True
    ):
        sig_type = IosSignatureType.DEVELOPMENT
    elif provisioned_devices:
        sig_type = IosSignatureType.AD_HOC
    else:
        sig_type = IosSignatureType.APP_STORE

    # 2. 证书过期时间计算
    exp_str = str(provisioning_data.get("ExpirationDate") or provisioning_data.get("expiration_date") or "")
    if exp_str:
        try:
            exp_date = datetime.fromisoformat(exp_str)
        except Exception:
            exp_date = current_time.replace(year=current_time.year + 1)
    else:
        exp_date = current_time.replace(year=current_time.year + 1)

    days_left = (exp_date - current_time).days
    is_expired = current_time > exp_date

    # 3. 目标真机 UDID 校验
    is_device_provisioned = True
    if target_device_udid and sig_type in (IosSignatureType.DEVELOPMENT, IosSignatureType.AD_HOC):
        # 统一大小写比对
        allowed_udids = {str(u).lower() for u in provisioned_devices}
        if target_device_udid.lower() not in allowed_udids:
            is_device_provisioned = False

    # 4. Bundle ID 一致性比对
    bundle_id_match = True
    if expected_bundle_id and expected_bundle_id.lower() != bundle_id.lower():
        bundle_id_match = False

    # 5. 判定最终裁决
    if is_expired:
        verdict = IpaValidationVerdict.CERTIFICATE_EXPIRED
        is_deployable = False
        msg = f"IPA 签名证书已于 [{exp_date.isoformat()}] 过期，无法在目标真机上安装运行"
    elif not is_device_provisioned:
        verdict = IpaValidationVerdict.DEVICE_NOT_PROVISIONED
        is_deployable = False
        msg = f"目标真机 UDID [{target_device_udid}] 不在 Provisioning Profile 授权设备清单内 (共 {len(provisioned_devices)} 台)"
    elif not bundle_id_match:
        verdict = IpaValidationVerdict.BUNDLE_ID_MISMATCH
        is_deployable = False
        msg = f"包体内 Bundle ID [{bundle_id}] 与预期测试应用标识 [{expected_bundle_id}] 不匹配"
    else:
        verdict = IpaValidationVerdict.VALID
        is_deployable = True
        msg = f"IPA 签名合法 ({sig_type.value})，证书有效期剩余 {days_left} 天，设备授权已匹配"

    report = IpaSigningValidationReport(
        validation_id=validation_id,
        bundle_id=bundle_id,
        team_id=team_id,
        team_name=team_name,
        signature_type=sig_type,
        verdict=verdict,
        is_deployable=is_deployable,
        target_device_udid=target_device_udid,
        is_device_provisioned=is_device_provisioned,
        expiration_date=exp_date.isoformat(),
        days_until_expiration=days_left,
        message=msg,
    )
    _VALIDATION_HISTORY.append(report)
    return report
