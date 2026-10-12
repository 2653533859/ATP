# N2.1 API 与 Web 用例生命周期及异常证据（2026-10-12）

## 概述与结论

N2.1 第一阶段（API 与 Web 用例核心流程闭环、录制异常保护与断言证据）已完成代码修复与定向回归。
覆盖：
1. **Web 录制浏览器关闭与异常收敛**：补齐 `page.on("close")`、`context.on("close")`、`browser.on("disconnected")` 监听器，页面或浏览器窗口被意外关闭时自动收敛至 `stopped` 状态并持久化已有产物，防止录制会话挂起；对已关闭页面的 `screenshot()` 与 `current_url()` 提供安全保护。
2. **API 用例全流程与失败断言证据**：支持创建包含请求参数、JSONPath 提取及多重断言的用例；审核流转（draft → submit_review → approved）状态机完整；成功执行记录变量提取与断言明细，断言失败时标记用例为 `failed` 并保留具体断言错误信息。
3. **Web 用例低代码回放与截图证据**：支持低代码步骤回放；成功执行步骤记录；`assert_text` 等断言失败时判定步骤为 `failed`，捕获失败现场截图并上传至本地对象存储（`.local-data/`），终止后续步骤执行。

## 代码与测试清单

- `backend/app/api/v1/web_recordings.py`：新增录制生命周期关闭与断开事件监听、安全截图与安全 URL 回退。
- `backend/tests/api/test_web_recordings.py`：新增页面关闭、上下文关闭、浏览器断开及关闭页面安全截图回归，30 项测试通过。
- `backend/tests/api/test_n2_1_case_lifecycle.py`：新建 N2.1 专用生命周期闭环回归，涵盖 API 审核流转、API 成功与断言失败、Web 异常关闭收敛、Web 成功与断言失败现场截图，4 项测试通过。
- `backend/tests/conftest.py`：升级 stub 隔离机制（`pytest_collectstart`），彻底解决多文件连续收集阶段的 `types.SimpleNamespace` 模块身份污染问题。

## 质量门禁与验证

1. **定向与全量 API 测试**：
   - `test_n2_1_case_lifecycle.py`：4 passed；
   - `test_web_recordings.py`：30 passed；
   - `backend/tests/api/` 全量：1096 passed in 5.86s；
   - `backend/tests/frontend/` 全量：93 passed in 0.69s。
2. **静态质量与编译**：
   - `ruff check` 与 `ruff format` 711 个文件检查通过；
   - `mypy` 188 个源文件 0 错误；
   - 前端 `vue-tsc --noEmit` 与 `vite build` 0 错误（4111 modules transformed）。
3. **独立服务运行**：
   - Windows 本地单机服务已热重启，`http://127.0.0.1:8001/health` 返回 `{"status":"ok"}`。
