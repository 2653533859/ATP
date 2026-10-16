"""基础设施即代码 (IaC) 与网络策略合规巡检单元测试 (T2.3)。"""

from __future__ import annotations

import pytest
from app.services.iac_network_policy_compliance_scanner import (
    ComplianceSeverity,
    ComplianceVerdict,
    clear_compliance_store,
    get_compliance_report,
    list_compliance_reports,
    scan_iac_manifests,
)


@pytest.fixture(autouse=True)
def _reset_compliance_state():
    clear_compliance_store()
    yield
    clear_compliance_store()


def test_scan_iac_clean_pass():
    """测试完全合规清单扫描输出 PASS。"""
    manifests = [
        {
            "kind": "Deployment",
            "metadata": {"name": "secure-app"},
            "spec": {
                "template": {
                    "spec": {
                        "securityContext": {"runAsNonRoot": True},
                        "containers": [
                            {
                                "name": "web",
                                "securityContext": {"privileged": False, "runAsNonRoot": True},
                                "resources": {
                                    "requests": {"cpu": "100m", "memory": "128Mi"},
                                    "limits": {"cpu": "500m", "memory": "512Mi"},
                                },
                            }
                        ],
                    }
                }
            },
        }
    ]

    report = scan_iac_manifests(target_name="secure-release", manifests=manifests)
    assert report.total_resources_scanned == 1
    assert report.total_violations_count == 0
    assert report.compliance_score_pct == 100.0
    assert report.verdict == ComplianceVerdict.PASS


def test_scan_iac_detect_privileged_and_host_mount():
    """测试探测特权容器与高危敏感卷挂载并阻断准入 (BLOCKED)。"""
    manifests = [
        {
            "kind": "Deployment",
            "metadata": {"name": "insecure-worker"},
            "spec": {
                "template": {
                    "spec": {
                        "hostNetwork": True,
                        "volumes": [
                            {"name": "docker-sock", "hostPath": {"path": "/var/run/docker.sock"}},
                        ],
                        "containers": [
                            {
                                "name": "runner",
                                "securityContext": {"privileged": True},
                                # 缺少 resources limits
                            }
                        ],
                    }
                }
            },
        }
    ]

    report = scan_iac_manifests(target_name="insecure-release", manifests=manifests)
    assert report.total_resources_scanned == 1
    assert report.critical_count >= 3  # privileged, hostNetwork, hostPath mount
    assert report.verdict == ComplianceVerdict.BLOCKED
    assert report.compliance_score_pct < 60.0

    rules_triggered = {v.rule_id for v in report.violations}
    assert "IAC-001" in rules_triggered
    assert "IAC-002" in rules_triggered
    assert "IAC-003" in rules_triggered


def test_scan_network_policy_unrestricted_ingress():
    """测试探测 NetworkPolicy 全网段放通风险 (HIGH)。"""
    manifests = [
        {
            "kind": "NetworkPolicy",
            "metadata": {"name": "open-netpol"},
            "spec": {
                "podSelector": {},
                "ingress": [
                    {
                        "from": [{"ipBlock": {"cidr": "0.0.0.0/0"}}],
                    }
                ],
            },
        }
    ]

    report = scan_iac_manifests(target_name="netpol-check", manifests=manifests)
    assert report.high_count == 1
    assert report.verdict in (ComplianceVerdict.WARNING, ComplianceVerdict.BLOCKED)
    assert report.violations[0].rule_id == "IAC-004"
    assert report.violations[0].severity == ComplianceSeverity.HIGH


def test_list_and_get_compliance_reports():
    """测试合规报告持久化与查询。"""
    manifests = [{"kind": "Pod", "name": "test-pod", "spec": {"containers": [{"name": "app"}]}}]
    report = scan_iac_manifests(target_name="test-run", manifests=manifests)

    saved = get_compliance_report(report.report_id)
    assert saved is not None
    assert saved.report_id == report.report_id

    reports = list_compliance_reports()
    assert len(reports) == 1
