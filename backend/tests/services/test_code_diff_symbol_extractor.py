"""Git Diff 与 AST 变更高危符号提取器单测 (T1.1)"""

from __future__ import annotations

from app.services.code_diff_symbol_extractor import (
    SymbolChangeSeverity,
    SymbolChangeType,
    SymbolType,
    extract_diff_changed_symbols,
    extract_symbols_from_ast,
    parse_unified_diff_hunks,
)


def test_parse_unified_diff_hunks():
    diff = """--- a/backend/app/services/order.py
+++ b/backend/app/services/order.py
@@ -10,3 +10,5 @@
 def old_func():
-    pass
+    val = 100
+    return val
"""
    res = parse_unified_diff_hunks(diff)
    assert "backend/app/services/order.py" in res
    lines = res["backend/app/services/order.py"]
    # 修改行 11, 12
    assert 11 in lines or 12 in lines


def test_extract_symbols_from_ast():
    source = """class OrderService:
    def __init__(self, db):
        self.db = db

    async def checkout(self, user_id, amount):
        return amount

def calculate_tax(amount):
    return amount * 0.1
"""
    symbols = extract_symbols_from_ast(source)
    assert len(symbols) == 4

    names = [s.qualified_name for s in symbols]
    assert "OrderService" in names
    assert "OrderService.__init__" in names
    assert "OrderService.checkout" in names
    assert "calculate_tax" in names

    checkout_sym = next(s for s in symbols if s.qualified_name == "OrderService.checkout")
    assert checkout_sym.symbol_type == SymbolType.ASYNC_FUNCTION
    assert "checkout(self, user_id, amount)" in checkout_sym.signature


def test_extract_diff_changed_symbols_body_and_signature():
    source = """def calculate_discount(price, rate):
    if price > 100:
        return price * rate
    return price
"""
    # 场景 1: 函数体内部修改 (第 3 行)
    diff_body = """--- a/services/discount.py
+++ b/services/discount.py
@@ -1,4 +1,4 @@
 def calculate_discount(price, rate):
     if price > 100:
-        return price * rate
+        return price * (rate - 0.05)
     return price
"""
    rep_body = extract_diff_changed_symbols(diff_body, {"services/discount.py": source})
    assert rep_body.changed_symbols_count == 1
    sym_body = rep_body.symbols[0]
    assert sym_body.symbol_name == "calculate_discount"
    assert sym_body.change_type == SymbolChangeType.MODIFIED
    assert sym_body.severity == SymbolChangeSeverity.MAJOR

    # 场景 2: 签名行发生变动 (第 1 行)
    diff_sig = """--- a/services/discount.py
+++ b/services/discount.py
@@ -1,4 +1,4 @@
-def calculate_discount(price, rate):
+def calculate_discount(price, rate, vip_level=1):
     if price > 100:
         return price * rate
"""
    rep_sig = extract_diff_changed_symbols(diff_sig, {"services/discount.py": source})
    assert rep_sig.changed_symbols_count == 1
    sym_sig = rep_sig.symbols[0]
    assert sym_sig.change_type == SymbolChangeType.SIGNATURE_CHANGED
    assert sym_sig.severity == SymbolChangeSeverity.CRITICAL

    d = rep_sig.to_dict()
    assert d["total_files_analyzed"] == 1
    assert d["changed_symbols_count"] == 1
    assert d["symbols"][0]["change_type"] == "SIGNATURE_CHANGED"
