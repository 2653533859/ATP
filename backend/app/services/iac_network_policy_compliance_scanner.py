"""基础设施即代码 (IaC) 与网络策略安全合规巡检引擎 (T2.3)。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ComplianceSeverity(str, Enum):
    """合规风险严重度等级。"""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ComplianceVerdict(str, Enum):
    """合规准入裁决。"""

    PASS = "PASS"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"


@dataclass
class ComplianceViolation:
    """单条合规违规明细。"""

    rule_id: str
    rule_name: str
    severity: ComplianceSeverity
    resource_kind: str
    resource_name: str
    violation_message: str
    remediation_guidance: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "resource_kind": self.resource_kind,
            "resource_name": self.resource_name,
            "violation_message": self.violation_message,
            "remediation_guidance": self.remediation_guidance,
        }


@dataclass
class IaCComplianceReport:
    """IaC 与网络策略合规审计报告。"""

    report_id: str
    target_name: str
    total_resources_scanned: int
    total_violations_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    compliance_score_pct: float  # 0~100%
    verdict: ComplianceVerdict
    violations: list[ComplianceViolation]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "target_name": self.target_name,
            "total_resources_scanned": self.total_resources_scanned,
            "total_violations_count": self.total_violations_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "compliance_score_pct": round(self.compliance_score_pct, 1),
            "verdict": self.verdict.value,
            "violations": [v.to_dict() for v in self.violations],
            "created_at": self.created_at.isoformat(),
        }


# 全局扫描报告仓库
_COMPLIANCE_REPORTS: dict[str, IaCComplianceReport] = {}

# 内置合规检查规则字典
COMPLIANCE_RULES_METADATA = [
    {
        "rule_id": "IAC-001",
        "name": "禁止特权容器运行 (Privileged Container Prohibited)",
        "severity": ComplianceSeverity.CRITICAL.value,
        "description": "容器以 privileged: true 运行将拥有宿主机内核完全控制权，存在严重容器逃逸风险。",
    },
    {
        "rule_id": "IAC-002",
        "name": "禁止挂载敏感宿主机路径 (Sensitive Host Path Mount Prohibited)",
        "severity": ComplianceSeverity.CRITICAL.value,
        "description": "禁止容器挂载 /var/run/docker.sock, /etc, /proc 等敏感宿主机核心路径。",
    },
    {
        "rule_id": "IAC-003",
        "name": "禁止共享宿主机网络或命名空间 (Host Network/PID Prohibited)",
        "severity": ComplianceSeverity.CRITICAL.value,
        "description": "容器开启 hostNetwork: true 或 hostPID: true 会破坏网络与进程隔离边界。",
    },
    {
        "rule_id": "IAC-004",
        "name": "网络策略全通未受限检测 (Unrestricted Ingress Prohibited)",
        "severity": ComplianceSeverity.HIGH.value,
        "description": "NetworkPolicy 规则入向未限制来源 Pod/Namespace，允许全网段 0.0.0.0/0 任意访问。",
    },
    {
        "rule_id": "IAC-005",
        "name": "容器必须声明资源限额 (Resource Requests & Limits Required)",
        "severity": ComplianceSeverity.MEDIUM.value,
        "description": "未声明 CPU/内存 limit 和 request 会导致节点资源争抢与失控 OOM。",
    },
    {
        "rule_id": "IAC-006",
        "name": "禁止以 Root 用户执行 (RunAsNonRoot Required)",
        "severity": ComplianceSeverity.MEDIUM.value,
        "description": "容器必须显式声明 runAsNonRoot: true 或指定非 0 的 UID 运行。",
    },
]


def clear_compliance_store() -> None:
    """清空合规报告仓库（单测专用）。"""
    _COMPLIANCE_REPORTS.clear()


def scan_iac_manifests(
    target_name: str,
    manifests: list[dict[str, Any]],
) -> IaCComplianceReport:
    """扫描 Kubernetes / Docker 清单配置，识别安全合规隐患并评定准入分级。"""
    violations: list[ComplianceViolation] = []
    scanned_count = len(manifests)

    for doc in manifests:
        kind = doc.get("kind", "Deployment")
        metadata = doc.get("metadata", {})
        res_name = metadata.get("name", doc.get("name", "unnamed-resource"))

        # 1. 检查 NetworkPolicy 资源
        if kind == "NetworkPolicy":
            spec = doc.get("spec", {})
            ingress_rules = spec.get("ingress", [])
            for rule in ingress_rules:
                from_list = rule.get("from", [])
                # 若 ingress 规则无 from 字段，或者包含 cidr: 0.0.0.0/0
                is_unrestricted = False
                if not from_list:
                    is_unrestricted = True
                else:
                    for f in from_list:
                        ip_block = f.get("ipBlock", {})
                        if ip_block.get("cidr") in ("0.0.0.0/0", "::/0"):
                            is_unrestricted = True

                if is_unrestricted:
                    violations.append(
                        ComplianceViolation(
                            rule_id="IAC-004",
                            rule_name="网络策略全通未受限检测",
                            severity=ComplianceSeverity.HIGH,
                            resource_kind=kind,
                            resource_name=res_name,
                            violation_message=f"NetworkPolicy [{res_name}] 入向 ingress 允许来自任意网段的未受限访问。",
                            remediation_guidance="在 ingress.from 中明确指定 podSelector 或 namespaceSelector 白名单。",
                        )
                    )
            continue

        # 2. 检查工作负载 Pod / Deployment / DaemonSet / StatefulSet
        spec = doc.get("spec", {})
        # 兼容 Deployment template.spec 与裸 Pod spec
        pod_spec = spec.get("template", {}).get("spec", spec)

        # 规则 IAC-003: hostNetwork / hostPID
        if pod_spec.get("hostNetwork") is True or pod_spec.get("hostPID") is True:
            violations.append(
                ComplianceViolation(
                    rule_id="IAC-003",
                    rule_name="禁止共享宿主机网络或命名空间",
                    severity=ComplianceSeverity.CRITICAL,
                    resource_kind=kind,
                    resource_name=res_name,
                    violation_message=f"资源 [{res_name}] 声明了 hostNetwork: true 或 hostPID: true，突破节点隔离界限。",
                    remediation_guidance="移除 hostNetwork 与 hostPID 配置，使用容器虚拟网络与隔离命名空间。",
                )
            )

        # 规则 IAC-002: 宿主机卷挂载
        volumes = pod_spec.get("volumes", [])
        sensitive_mounts = ["/var/run/docker.sock", "/var/run", "/etc", "/proc", "/sys", "/"]
        for vol in volumes:
            host_path = vol.get("hostPath", {}).get("path", "")
            if any(host_path.startswith(s) for s in sensitive_mounts):
                violations.append(
                    ComplianceViolation(
                        rule_id="IAC-002",
                        rule_name="禁止挂载敏感宿主机路径",
                        severity=ComplianceSeverity.CRITICAL,
                        resource_kind=kind,
                        resource_name=res_name,
                        violation_message=f"卷 [{vol.get('name')}] 挂载了敏感宿主机目录 ({host_path})，存在逃逸劫持风险。",
                        remediation_guidance="禁止直接挂载宿主机核心路径，改用 ConfigMap、Secret 或 EmptyDir 卷。",
                    )
                )

        # 规则 容器级别安全配置审查
        containers = pod_spec.get("containers", [])
        pod_sec = pod_spec.get("securityContext", {})
        run_as_non_root = pod_sec.get("runAsNonRoot", False)

        for c in containers:
            c_name = c.get("name", "app")
            c_sec = c.get("securityContext", {})

            # 规则 IAC-001: 特权模式
            if c_sec.get("privileged") is True:
                violations.append(
                    ComplianceViolation(
                        rule_id="IAC-001",
                        rule_name="禁止特权容器运行",
                        severity=ComplianceSeverity.CRITICAL,
                        resource_kind=kind,
                        resource_name=f"{res_name}/{c_name}",
                        violation_message=f"容器 [{c_name}] 配置了 privileged: true，开启完全宿主机特权。",
                        remediation_guidance="移除 privileged: true，按需使用 capabilities.add 授予最小必要权限。",
                    )
                )

            # 规则 IAC-005: 资源限额
            resources = c.get("resources", {})
            has_limits = "limits" in resources
            has_requests = "requests" in resources
            if not (has_limits and has_requests):
                violations.append(
                    ComplianceViolation(
                        rule_id="IAC-005",
                        rule_name="容器必须声明资源限额",
                        severity=ComplianceSeverity.MEDIUM,
                        resource_kind=kind,
                        resource_name=f"{res_name}/{c_name}",
                        violation_message=f"容器 [{c_name}] 未完整声明 resources.limits 与 resources.requests。",
                        remediation_guidance="在清单中指定合理的 cpu/memory requests 与 limits，防止资源争抢。",
                    )
                )

            # 规则 IAC-006: 非 root 运行
            c_non_root = c_sec.get("runAsNonRoot", run_as_non_root)
            if not c_non_root:
                violations.append(
                    ComplianceViolation(
                        rule_id="IAC-006",
                        rule_name="禁止以 Root 用户执行",
                        severity=ComplianceSeverity.MEDIUM,
                        resource_kind=kind,
                        resource_name=f"{res_name}/{c_name}",
                        violation_message=f"容器 [{c_name}] 未配置 securityContext.runAsNonRoot: true。",
                        remediation_guidance="配置 runAsNonRoot: true 并指定 runAsUser 为非零值。",
                    )
                )

    # 计算严重度统计与扣分模型
    critical_c = sum(1 for v in violations if v.severity == ComplianceSeverity.CRITICAL)
    high_c = sum(1 for v in violations if v.severity == ComplianceSeverity.HIGH)
    medium_c = sum(1 for v in violations if v.severity == ComplianceSeverity.MEDIUM)
    low_c = sum(1 for v in violations if v.severity == ComplianceSeverity.LOW)

    penalty = (critical_c * 25.0) + (high_c * 15.0) + (medium_c * 8.0) + (low_c * 3.0)
    score = max(0.0, min(100.0, 100.0 - penalty))

    if critical_c > 0 or score < 60.0:
        verdict = ComplianceVerdict.BLOCKED
    elif high_c > 0 or score < 85.0:
        verdict = ComplianceVerdict.WARNING
    else:
        verdict = ComplianceVerdict.PASS

    now = datetime.now(timezone.utc)
    report_id = f"iac_{target_name}_{int(now.timestamp())}_{len(violations)}"
    report = IaCComplianceReport(
        report_id=report_id,
        target_name=target_name,
        total_resources_scanned=scanned_count,
        total_violations_count=len(violations),
        critical_count=critical_c,
        high_count=high_c,
        medium_count=medium_c,
        low_count=low_c,
        compliance_score_pct=score,
        verdict=verdict,
        violations=violations,
        created_at=now,
    )
    _COMPLIANCE_REPORTS[report_id] = report
    return report


def get_compliance_report(report_id: str) -> IaCComplianceReport | None:
    """按 ID 查询合规扫描报告。"""
    return _COMPLIANCE_REPORTS.get(report_id)


def list_compliance_reports(limit: int = 50) -> list[dict[str, Any]]:
    """获取历史合规报告列表。"""
    reports = list(reversed(list(_COMPLIANCE_REPORTS.values())))
    return [r.to_dict() for r in reports[:limit]]
