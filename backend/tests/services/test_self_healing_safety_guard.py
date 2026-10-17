"""自愈补丁防篡改与安全围栏看门狗单测 (T4.1)"""

from __future__ import annotations

from app.services.self_healing_safety_guard import (
    RuleCode,
    SafetyVerdict,
    ViolationSeverity,
    audit_assertion_safety,
    audit_locator_safety,
    audit_self_healing_patch_safety,
)


def test_audit_assertion_tautology_blocks():
    # 1. 直接 assert True
    rep1 = audit_assertion_safety("assert True")
    assert rep1.verdict == SafetyVerdict.BLOCK
    assert any(v.rule_code == RuleCode.TAUTOLOGY_ASSERTION_DETECTED for v in rep1.violations)

    # 2. 常量恒等比较 assert 1 == 1
    rep2 = audit_assertion_safety("assert 1 == 1")
    assert rep2.verdict == SafetyVerdict.BLOCK
    assert any(v.rule_code == RuleCode.TAUTOLOGY_ASSERTION_DETECTED for v in rep2.violations)


def test_audit_assertion_code_injection_blocks():
    # 尝试调用 eval
    rep = audit_assertion_safety("assert eval('1 + 1') == 2")
    assert rep.verdict == SafetyVerdict.BLOCK
    assert any(v.rule_code == RuleCode.CODE_INJECTION_DETECTED for v in rep.violations)
    assert any(v.severity == ViolationSeverity.CRITICAL for v in rep.violations)


def test_audit_assertion_valid_passes():
    rep = audit_assertion_safety('assert res["data"]["userId"] == 1001 and res["data"]["amount"] > 0')
    assert rep.verdict == SafetyVerdict.ALLOW
    assert len(rep.violations) == 0


def test_audit_locator_overly_broad_blocks():
    for broad in ["*", "body", "html", "//*", "//body"]:
        rep = audit_locator_safety("css", broad)
        assert rep.verdict == SafetyVerdict.BLOCK
        assert any(v.rule_code == RuleCode.OVERLY_BROAD_LOCATOR for v in rep.violations)


def test_audit_locator_malicious_injection_blocks():
    # 脚本注入
    rep1 = audit_locator_safety("css", "button[title='<script>alert(1)</script>']")
    assert rep1.verdict == SafetyVerdict.BLOCK
    assert any(v.rule_code == RuleCode.MALICIOUS_INJECTION_LOCATOR for v in rep1.violations)

    # 系统指令拼接
    rep2 = audit_locator_safety("css", "#btn ; rm -rf /")
    assert rep2.verdict == SafetyVerdict.BLOCK
    assert any(v.rule_code == RuleCode.MALICIOUS_INJECTION_LOCATOR for v in rep2.violations)


def test_audit_locator_valid_passes():
    rep = audit_locator_safety("css", "button[data-action='checkout_order']")
    assert rep.verdict == SafetyVerdict.ALLOW
    assert len(rep.violations) == 0


def test_audit_patch_safety():
    # 安全合规补丁
    safe_patch = {
        "patch_id": "p_safe",
        "best_candidate": {
            "recommended_locator_type": "css",
            "recommended_locator_value": "button.btn-checkout",
        },
    }
    rep_safe = audit_self_healing_patch_safety(safe_patch)
    assert rep_safe.verdict == SafetyVerdict.ALLOW

    # 包含破坏性全屏定位器的危险补丁
    dangerous_patch = {
        "patch_id": "p_danger",
        "best_candidate": {
            "recommended_locator_type": "css",
            "recommended_locator_value": "*",
        },
    }
    rep_danger = audit_self_healing_patch_safety(dangerous_patch)
    assert rep_danger.verdict == SafetyVerdict.BLOCK
