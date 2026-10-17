"""IPA 签名合规与 Provisioning 描述文件验真服务单测 (T4.2)"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from app.services.ios_ipa_signing_validator import (
    IosSignatureType,
    IpaValidationVerdict,
    clear_validation_history,
    list_validation_reports,
    validate_ipa_signing,
)


@pytest.fixture(autouse=True)
def clean_state():
    clear_validation_history()
    yield
    clear_validation_history()


def test_validate_development_and_adhoc_ipa():
    udid_allowed = "00008101-UDID-ALLOWED"
    udid_unauthorized = "00008101-UNAUTHORIZED"

    now = datetime.now(timezone.utc)
    valid_exp = (now + timedelta(days=90)).isoformat()

    provisioning_data = {
        "team_id": "9ABC123456",
        "team_name": "Antigravity Engineering Team",
        "bundle_id": "com.company.testapp",
        "get_task_allow": True,
        "ExpirationDate": valid_exp,
        "ProvisionedDevices": [udid_allowed, "00008101-ANOTHER-UDID"],
    }

    # 1. 目标真机在白名单内，校验通过
    report_valid = validate_ipa_signing(
        provisioning_data=provisioning_data,
        target_device_udid=udid_allowed,
        expected_bundle_id="com.company.testapp",
        now=now,
    )
    assert report_valid.is_deployable is True
    assert report_valid.verdict == IpaValidationVerdict.VALID
    assert report_valid.signature_type == IosSignatureType.DEVELOPMENT
    assert report_valid.is_device_provisioned is True
    assert report_valid.days_until_expiration >= 89

    # 2. 目标真机不在白名单内，提前阻断
    report_unauth = validate_ipa_signing(
        provisioning_data=provisioning_data,
        target_device_udid=udid_unauthorized,
        now=now,
    )
    assert report_unauth.is_deployable is False
    assert report_unauth.verdict == IpaValidationVerdict.DEVICE_NOT_PROVISIONED
    assert "不在 Provisioning Profile 授权设备清单内" in report_unauth.message

    # 3. 证书过期校验
    expired_exp = (now - timedelta(days=10)).isoformat()
    expired_data = dict(provisioning_data, ExpirationDate=expired_exp)
    report_expired = validate_ipa_signing(
        provisioning_data=expired_data,
        target_device_udid=udid_allowed,
        now=now,
    )
    assert report_expired.is_deployable is False
    assert report_expired.verdict == IpaValidationVerdict.CERTIFICATE_EXPIRED

    # 4. 企业级签名 (In-House) 免除设备白名单
    enterprise_data = {
        "team_id": "ENT1234567",
        "team_name": "Enterprise InHouse Distribution",
        "bundle_id": "com.company.enterprise",
        "ProvisionsAllDevices": True,
        "ExpirationDate": valid_exp,
    }
    report_ent = validate_ipa_signing(
        provisioning_data=enterprise_data,
        target_device_udid="00008101-ANY-RANDOM-UDID",
        now=now,
    )
    assert report_ent.is_deployable is True
    assert report_ent.signature_type == IosSignatureType.ENTERPRISE
    assert report_ent.verdict == IpaValidationVerdict.VALID

    reports = list_validation_reports()
    assert len(reports) == 4
