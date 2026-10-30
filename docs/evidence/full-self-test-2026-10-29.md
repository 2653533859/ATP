# ATP 全量自测（2026-10-29）

测试当前工作区及未提交修改；使用本机 Python 3.12.11、Node 24.14.0。日志和隔离数据位于 `.local-run/full-selftest-20261029/`。实际接口测试使用临时 SQLite、临时管理员和回环 HTTP 目标。

## 结果

- 后端非集成全套：420 秒超时，日志记录 821 passed、83 failed，尚有未执行项；不构成全套通过。`backend.log`。
- 非 API 后端套件：1951 passed、19 failed、2 skipped。失败包括缺失设备代理表迁移、生命周期测试替身、Android 稳定性测试返回值契约、发布范围文档断言及性能 worker 测试隔离。`nonapi.log`、`nonapi.xml`。
- 后端定向复核：33 passed、6 failed；六项分别为零状态迁移 1、Android 稳定性 3、启动生命周期 2。`targeted.log`。
- API 按文件独立扫描：首轮 127 文件中 117 通过、10 失败。测试脚本最初未创建临时目录父目录，造成部分 FileNotFoundError；对其中 8 个文件使用新目录单独重跑全部通过。剩余 2 个文件仍失败：`test_case_execution_guards.py` 的 tracing 替身缺少导入，`test_remote_device_connect.py` 的 FakeDB 缺少 `get`。结合重跑结果为 125/127 文件通过；不是整套单进程测试通过。`api-standalone-results.log`、`api-recheck.log`。
- 前端单测首轮 60 文件/248 项通过、25 个 worker 启动超时；4 worker 重跑为 84 文件/426 项通过、1 个 worker 意外退出；单 worker 重跑为 84 文件/424 项通过、1 个 worker 意外退出。三轮均未完整通过，不合并数字计算通过率。`frontend-test.log`、`frontend-test-retry.log`、`frontend-test-serial.log`。
- 两个近期 UI 修复的定向单测：15 passed。`ui-targeted.log`。
- 模拟接口的 Chromium E2E 使用 1 worker，12 项结果中 10 passed、2 failed。用例列表在登录页加载超时；配置中心页面已显示但测试未找到期望的 heading。全部结果记录后测试进程收尾持续无进展，停止了测试进程，未取得正常退出摘要。该轮使用本地 404 代理与测试 mock，不代表真实云端服务验收。`e2e-isolated.log` 与 `frontend/test-results/`。
- 前端 `npm run type-check` 和 `npm run build` 通过；Ruff 通过，mypy 检查 214 个文件通过。`frontend-build.log`、`ruff.log`、`mypy.log`。
- 隔离本地实际接口链路重试通过 14 项，包括健康、登录、项目与用例创建、实际本地 HTTP 执行、运行查询、Outbox 入队及导出。首次并发高负载启动未通过健康检查；重试成功，不隐去首轮结果。`live.log`、`live-retry.log`、`live-result.json`。

## 边界

未运行需要 PostgreSQL、Redis、MinIO 的真实集成测试；未进行真实云端同步、真机 Android/iOS 或真实 LLM 验收。模拟 E2E 和本地待同步队列不能替代上述验收。测试服务和模拟代理已停止，原有 8000 服务没有改写业务数据。此次没有修改业务源码或测试断言。

结论：当前工作区不能判定全量测试通过或发布就绪；需处理后端测试隔离、缺失迁移、Android 测试契约和前端 worker/E2E 异常，再重新运行完整门禁。
