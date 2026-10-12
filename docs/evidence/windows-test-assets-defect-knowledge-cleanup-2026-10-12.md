# N2.4 测试资产、需求/缺陷/知识及产物精确清理证据（2026-10-12）

## 概述与结论

N2.4（测试资产、需求/缺陷/知识及报告附件链路）已完成代码优化与定向自动化回归验证。
覆盖：
1. **测试资产变量占位符替换**：
   - 验证环境变量与上下文占位符 `{{VAR}}` 在请求 URL、Header 及复杂嵌套 JSON 请求体中能够正确替换；
   - 保证整型、布尔型等非字符串类型在请求体中得到严格保留。
2. **需求关联用例与验收准则覆盖率**：
   - 验证 `link_requirement_case` 将用例与需求准则双向绑定；
   - 校验跨项目关联拦截，正确计算需求关联用例数与准则覆盖率。
3. **失败执行记录快速转内部缺陷**：
   - 验证失败用例运行一键生成缺陷记录，绑定 `run_id` 与 `case_id`，提取失败原因与错误堆栈；
   - 生成唯一指纹防止重复提交，并在 `Defect` 初始化时保证 `occurrence_count=1` 规范。
4. **缺陷故障经验沉淀为知识条目**：
   - 验证通过 `create_knowledge` 将排查结论沉淀入知识库，支持项目隔离、分类与标签检索。
5. **本地对象存储产物精确清理**：
   - 验证 `delete_run_artifacts` 精确清理指定 `run_id` 的截图（`screenshots/runs/{id}/`）、Trace（`traces/runs/{id}/`）、录屏（`videos/runs/{id}/`）与报告（`reports/run-{id}/`）；
   - 保证未删除运行的产物完好无损，做到**零孤儿文件残留**。

## 测试与代码清单

- `backend/app/api/v1/defects.py`：修复新缺陷初始化时 `occurrence_count=1` 显式赋值，保证与 Schema 严格一致。
- `backend/tests/services/test_n2_4_assets_defect_knowledge_cleanup.py`：新建 N2.4 专用 5 项自动化回归，涵盖变量替换、需求关联、失败转缺陷、经验入知识及本地产物精确清理，5 passed in 1.91s。

## 质量门禁与验证

1. **定向测试**：5 passed in 1.91s，独立运行无副作用。
2. **静态质量**：`ruff check`、`ruff format`、`mypy` 188 个源文件全部通过。
