"""Unit tests for Change Risk Scorer Service (S2.2)."""

from __future__ import annotations

import pytest

from app.services.change_risk_scorer import (
    RiskLevel,
    evaluate_change_risk,
    get_change_risk_report,
    list_change_risk_reports,
    reset_change_risk_registry,
)
from app.services.git_diff_ast_analyzer import reset_diff_ast_registry


@pytest.fixture(autouse=True)
def clean_registries():
    reset_diff_ast_registry()
    reset_change_risk_registry()
    yield
    reset_diff_ast_registry()
    reset_change_risk_registry()


LOW_RISK_DIFF = """diff --git a/app/utils/format.py b/app/utils/format.py
--- a/app/utils/format.py
+++ b/app/utils/format.py
@@ -5,2 +5,2 @@ def format_name(first: str, last: str) -> str:
-    return first + " " + last
+    return f"{first} {last}".strip()
"""

LOW_RISK_CODE = """# Format utils
def dummy():
    pass

def format_name(first: str, last: str) -> str:
    return f"{first} {last}".strip()
"""

CRITICAL_RISK_DIFF = """diff --git a/backend/app/core/auth_security.py b/backend/app/core/auth_security.py
--- a/backend/app/core/auth_security.py
+++ b/backend/app/core/auth_security.py
@@ -5,4 +5,12 @@ def verify_payment_token(token: str, secret: str) -> bool:
+    if not token or not secret:
+        raise ValueError("Missing credentials")
+    for attempt in range(3):
+        try:
+            if len(token) > 10 and secret.startswith("sec_"):
+                return True
+        except Exception:
+            pass
     return False
"""

CRITICAL_RISK_CODE = """# Auth security module
def dummy():
    pass

def verify_payment_token(token: str, secret: str) -> bool:
    if not token or not secret:
        raise ValueError("Missing credentials")
    for attempt in range(3):
        try:
            if len(token) > 10 and secret.startswith("sec_"):
                return True
        except Exception:
            pass
    return False
"""


def test_evaluate_low_risk_change():
    report = evaluate_change_risk(
        diff_text=LOW_RISK_DIFF,
        file_sources={"app/utils/format.py": LOW_RISK_CODE},
    )

    assert report.risk_level == RiskLevel.LOW
    assert report.overall_risk_score < 25.0
    assert len(report.high_risk_files) == 0
    assert "快速通道" in report.recommended_action


def test_evaluate_critical_risk_change():
    report = evaluate_change_risk(
        diff_text=CRITICAL_RISK_DIFF,
        file_sources={"backend/app/core/auth_security.py": CRITICAL_RISK_CODE},
    )

    # 触及 backend/app/core 核心认证 + 引入 if/for/try 圈复杂度
    assert report.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert report.overall_risk_score >= 50.0
    assert len(report.high_risk_files) == 1
    assert "backend/app/core/auth_security.py" in report.high_risk_files

    # 验证维度解析
    dims = report.dimensions
    assert "volume" in dims
    assert "complexity" in dims
    assert "criticality" in dims
    assert dims["criticality"].score >= 75.0
    assert dims["complexity"].score > 10.0


def test_get_and_list_change_risk_reports():
    report = evaluate_change_risk(
        diff_text=LOW_RISK_DIFF,
        file_sources={"app/utils/format.py": LOW_RISK_CODE},
    )

    fetched = get_change_risk_report(report.risk_id)
    assert fetched is not None
    assert fetched.risk_id == report.risk_id

    reports = list_change_risk_reports()
    assert len(reports) == 1
    assert reports[0].risk_id == report.risk_id
