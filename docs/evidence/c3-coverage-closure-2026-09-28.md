# C3.4 后端覆盖率门禁收口（2026-09-28）

## 背景与改动

Performance Worker 心跳热修复的完整后端回归为 `2693 passed / 2 skipped`，但按仓库正式口径计算的覆盖率为 80.54%，未达到 82% 门禁。本轮保留原门槛，针对真实未覆盖行为增加需求管理、知识检索、缺陷运行证据和工作台五类任务的路由回归。新增测试覆盖项目隔离、过滤和计数、需求版本及用例关联、运行上下文和重试来源、编辑权限及跨项目拒绝。

知识来源的结构化摘要测试发现嵌套字典中的 `token` 等字段会在 JSON 序列化后绕过原有文本脱敏正则。`redact_knowledge_value` 现先递归遮盖敏感键对应的值，再执行已有自由文本与 URL 脱敏；回归覆盖嵌套字典、列表和来源搜索聚合。此修复只作用于本次代码，不代表已经部署到正式单节点。

## 本地验证

- `backend/.venv/Scripts/python.exe -m pytest backend/tests -q --ignore=backend/tests/integration --cov=backend/app --cov-report=term-missing:skip-covered --cov-fail-under=82 --basetemp .local-run/pytest-coverage-closure`：**2725 passed / 2 skipped**，TOTAL **82.04%**，退出码 0。相对前次增加 32 个通过项，覆盖率提高 1.50 个百分点；82.04% 仅略高于门槛，后续新增代码须重新核算。
- 新增或修改的 5 个测试文件分别独立运行：**5 passed / 0 failed standalone**。
- 全仓非集成测试文件以 `scripts/pytest-standalone-sweep.py --jobs 4` 逐个运行：**337 passed / 0 failed standalone**。
- Ruff 检查、mypy（167 个源文件无问题）和 `git diff --check` 通过。

## 现场边界与下一步

覆盖率收口时的只读复核为 6/6 Ready、零重启；知识脱敏代码当时尚未部署。随后依据 revision 58 精确 Chart 快照把 Backend 单文件补丁发布到 Helm revision 59，并在运行容器中验证嵌套字段脱敏，具体发布证据见 [`c3-knowledge-redaction-hotfix-2026-09-28.md`](c3-knowledge-redaction-hotfix-2026-09-28.md)。主 Chart 后于 revision 62 对齐并复检通过；C3.4 完整发布后 UTC 日、代表性 7/14 日 SLO 和 Flower 长期稳定性仍开放，见 [`c3-main-chart-drift-resolution-2026-09-28.md`](c3-main-chart-drift-resolution-2026-09-28.md)。
