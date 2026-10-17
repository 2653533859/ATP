# T1.1 Git Diff 与 AST 变更高危符号提取器服务验收 (2026-10-17)

## 概述与交付物

T1.1（Git Diff 与 AST 变更高危符号提取器服务）已全量研发交付并通过各项工程门禁，**正式开启 ATP v5.7.0 Phase 1（代码变更 AST 影响面追踪与符号依赖映射器）**：
1. **代码补丁与 AST 符号交叉碰撞引擎 (`backend/app/services/code_diff_symbol_extractor.py`)**：
   - **Unified Diff 块解析器 (`parse_unified_diff_hunks`)**：精准解析 `@@ -x,y +x,y @@` 分块，提取变更目标行号集合；
   - **Python AST 源码符号范围定位器 (`extract_symbols_from_ast`)**：递归遍历提取类（`CLASS`）、同步函数（`FUNCTION`）、异步函数（`ASYNC_FUNCTION`）及类方法（`METHOD`）的行号范围（`[start_line, end_line]`）、全限定名称（`OrderService.checkout`）与参数签名；
   - **符号变更加权碰撞分析 (`extract_diff_changed_symbols`)**：
     - 若修改行落在函数声明签名行（`start_line`），标记为 `SIGNATURE_CHANGED`（评级 `CRITICAL` 高危）；
     - 若修改行落在函数体内部，标记为 `MODIFIED`（评级 `MAJOR`）；
   - **输出结构化变更符号报告 (`DiffSymbolExtractionReport`)**：记录受影响符号列表、被触碰行号集合与参数签名。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_code_diff_symbol_extractor.py`：3 passed（Unified Diff 分块修改行精准解析、AST 多层级符号树提取与签名格式化、函数体内部修改与签名变更高危评级交叉分析）；
   - **通过率**：**3 passed in 0.30s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：1/1 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 1 source file.**。
