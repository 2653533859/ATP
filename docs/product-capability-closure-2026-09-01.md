# 产品能力缺口闭环说明（2026-09-01）

本文记录 PRD 中此前缺少明确产品入口或执行契约的能力。这里的“完成”仅指代码、迁移和本地契约闭环；真实 Kubernetes、macOS/iPhone、第三方供应商和外部平台仍按发布范围与环境门禁单独验收。

## 1. GraphQL 与 WebSocket

- GraphQL 用例支持 `query`、`mutation`、`subscription`。Subscription 使用 `graphql-transport-ws`，可配置 `subscription_url`、`connection_payload`、`max_messages`、`reconnect_attempts` 和 `reconnect_delay_ms`。
- 用例编辑器的“读取 Schema”会调用项目隔离的 introspection API，列出 Query/Mutation/Subscription 根字段并生成操作骨架。服务端主动访问会应用公共 HTTP URL/SSRF 校验；内网 Schema 应通过受控网关暴露，不能绕过该校验。
- 普通 WebSocket 用例增加有界建连重试。重试只发生在握手阶段，消息发送后不会隐式重放。

## 2. 脚本依赖

Web/Android 脚本编辑区增加 `requirements.txt`。每行必须是 `package==version` 精确锁定，可带 extras 和环境 marker；URL、本地路径、Git 源和 pip 索引参数会被拒绝。

执行时 Worker 将依赖安装到本次运行临时目录并通过独立 `PYTHONPATH` 注入，运行结束随临时目录清理，不安装到 Worker 主环境。依赖下载仍需要 Worker 能访问已批准的 Python 包索引；离线环境应在 Worker 层配置受控镜像。依赖安装失败或超时会令运行明确失败，不得降级为“已通过”。

## 3. Android 设备组

迁移 `20260901_0067` 新增 `device_groups` 和 `device_group_members`。`/device-groups` 提供查询、创建、更新和删除；Android 用例的设备矩阵可选择设备组并展开为现有 serial 列表，因此继续复用逐设备租约、矩阵子运行和结果汇总逻辑。

## 4. Suite 共享变量与 Fixtures

套件配置新增：

```json
{
  "shared_variables": {"tenant": "staging"},
  "fixtures": {
    "setup": [{"action": "set_variable", "variable": "token", "value": "{{tenant}}-token"}],
    "teardown": [{"action": "delete_variable", "variable": "token"}]
  }
}
```

setup 在所有子用例前执行，其结果作为只读初始上下文传入串行或并行子用例；teardown 在套件结束后执行。只允许 `set_variable`、`delete_variable`、`assert`，不执行 Python/JavaScript，也不提供任意网络请求。setup/teardown 摘要与失败原因写入 `SuiteRun.result_summary.fixtures`。

## 5. iOS 产品入口

APP 工作台新增“iOS 资产预览”，可注册 Appium 设备并按项目上传/查看 IPA。该入口复用已有 iOS 资产、租约和专用 Worker 后端，但页面固定展示技术预览提示。

iOS 仍不在本次正式支持范围；没有 macOS、Xcode、WebDriverAgent、签名 IPA 和真实 iPhone/Simulator 证据时，不得宣称 iOS 通过。

## 6. Hermes H2～H6 最小链路

迁移 `20260901_0068` 新增项目/用户隔离的 `hermes_sessions`：

- H2：最多保留最近 40 条脱敏会话消息，刷新后恢复最近会话；查询可按来源类型过滤，最近历史进入下一轮 grounded prompt。
- H3：提供 `failed_runs` 与 `quality_summary` 只读工具；调用参数和有界结果写入会话审计，不提供写工具。
- H4：计划草稿先写入 Session，只有用户显式 `CONFIRM` 后才创建禁用的手工 `draft` 计划；不会自动调度或执行。
- H5：提供版本化 `hermes-core-v1` 五题只读评测集与元数据接口；`/hermes/governance/summary` 返回项目级 prompt 版本、有效引用覆盖率、拒答/无结果率、平均/P95 延迟、helpful/not-helpful 反馈、活动量和成本不可用状态，Hermes 页面同步展示治理状态卡片。
- H6：提供 `/hermes/orchestrate` 受控自然语言入口，从五个固定 H3 只读工具中最多选择两步；运行/需求/用例/知识目标缺失时先返回 `needs_input`，未命中时回退 H1 项目证据检索，成功执行写入脱敏会话证据并在页面展示自动读取链路。

这些是最小治理链路，不等同于真实模型工具选择效果、完整角色矩阵或目标部署验收。真实模型效果阈值、成本与更大评测集仍需环境证据。

## 验证入口

```bash
backend/.venv/bin/python -m pytest \
  backend/tests/api/test_api_schema_assets.py \
  backend/tests/api/test_scripts_routes.py \
  backend/tests/api/test_device_groups_api.py \
  backend/tests/services/test_script_dependencies.py \
  backend/tests/worker/test_http_family_executors.py \
  backend/tests/worker/test_suite_execution_config.py \
  backend/tests/api/test_hermes_routes.py \
  backend/tests/migrations/test_zero_state_upgrade.py -q

cd frontend
npm run type-check
npm run test -- --run
```

部署前必须执行 `alembic upgrade head`；当前代码 head 为 `20260901_0068`。历史 q19 证据仍对应当时的 `20260825_0066`，不能把本地迁移测试改写成 q19 已升级。
