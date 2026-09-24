# Hermes K3s 认证接口与工具冒烟（2026-09-24）

## 环境与身份

- 目标为 `192.168.3.196` 的 `atp-single-node` 单节点联调 Release，Helm revision 47 `deployed`，Backend 镜像 `registry.local/atp/backend:71b0b0b3`。
- 使用现有每日 SLO canary 的专用账号 `atp-slo-canary`，从目标机受限凭据文件在进程内读取密码；命令输出、仓库及本记录均不含密码、Token 或回答正文。该账号只可见项目 77。
- 登录、项目 77 详情及 Hermes 评测题集均返回 HTTP 200；题集版本为 `2026-09-23.1`。

## 实际请求

- 先发起一次模型规划挑战问题。`POST /hermes/orchestrate` 返回 HTTP 200，但状态为 `no_match`；规划来源 `deterministic_fallback`，校验状态 `unavailable`，模型调用数 0、工具步骤 0，生成会话 4。代码路径与会话指标显示原因是 `project_model_not_configured`。
- 只读核对发现：项目 77 没有关联 `ai_llm_config_id`；该账号可见的项目只有 77。当前数据库有 1 份已启用模型配置，但没有任何项目关联到已启用配置。因此本次未触发真实模型请求，不能作为 K3s 实际模型规划验收。
- 随后在项目 77 发起一次确定性只读编排，询问失败任务与质量趋势。接口返回 HTTP 200、`matched`，执行 `failed_tasks` 与 `quality_trend` 两步，均为 `ok`，分别返回 20 与 1 条证据；生成会话 5，模型调用数 0。
- 项目 77 的 `hermes_read_tool` 审计计数由 0 增至 2；会话 5 指标为 `queries=1`、`tool_calls=2`。Backend 最近八分钟、最多 1000 行的日志样本中，`MissingGreenlet`、`Traceback`、工具失败及审计持久化失败标记均为 0，`/health` 为 200。

## 边界与后续条件

两次请求在现有业务库留下会话 4、5 以及两条工具审计；没有创建、修改或执行测试资产。该结果验证了 K3s 上的认证、项目访问、确定性只读工具及审计链路，但未验证 K3s 真实模型规划。独立环境的真实模型评测见[独立验收记录](hermes-isolated-acceptance-2026-09-24.md)。

若要补齐 K3s 真实模型链路，应通过受支持的 API/管理界面新建专用联调项目并关联现有已启用模型配置，使用对此项目有权限的账号运行一次有界问题后清理联调资产；当前专用 canary 账号没有创建项目的全局权限。不应为冒烟测试直接改动正在使用的项目 77 或绕过 API 修改业务库。P4/P9 等发布门禁仍未关闭。
