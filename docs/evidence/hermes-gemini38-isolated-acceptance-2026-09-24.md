# Hermes Gemini 3.8 Flash 独立环境验收（2026-09-24）

## 配置与范围

- Google 官方稳定模型 ID 为 [`gemini-3.8-flash`](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)。用户提供的 OpenAI 兼容服务在模型列表中提供 `gemini-3.8-flash-high`；使用该 ID 的最小对话请求返回 HTTP 200，响应标识为 `gemini-3.8-flash`，本地 ATP `call_llm` 适配器亦返回有效文本与用量。
- 隔离栈仍位于 Linux `192.168.3.196` 的 `/opt/atp-hermes-eval-20260924`，Backend 仅绑定 `127.0.0.1:39184`。通过隔离环境管理员 API 新建启用的 `openai_compatible` 配置 2，连接测试成功，并将隔离项目 1 从原配置 1 切至配置 2。原配置 1 保留；项目 1 当前绑定配置 2。模型密钥只通过交互输入传给 API，并由隔离数据库加密保存，未写入仓库、报告或记忆。
- 本次没有修改现有 `atp-single-node` K3s Release 或业务库。隔离栈 Backend、Worker 和三项数据服务持续运行，`/health` 为 200；一次性配置脚本已删除。

## 评测结果

- [结构化报告](hermes-gemini38-isolated-evaluation-2026-09-24.json)：以隔离项目 viewer 账号执行 `hermes-core-v2 / 2026-09-23.1` 固定十题，`10 passed / 0 blocked / 0 failed`；另行的模型规划挑战题 `passed`，实际模型规划来源为 `model`、校验为 `accepted`，`failed_tasks` 与 `quality_trend` 两步均为 `ok`。
- 十题中六道工具路由题由确定性规则处理，两道无来源问题验证拒答；只有两道有来源回答进入模型生成，不能把 10/10 理解成十次模型规划成功。
- 抽查两条模型生成回答：都引用了夹具需求 1 的 `[S1]` 来源，并把缺少测试执行证据与最终验收结论明确标为未知，没有把需求文本推断成已通过运行。抽查规划挑战题回答：失败任务为 1 条、质量趋势只有 1 个有效时间段和最近通过率 0.0%，明确说无法判断变化。
- 规划挑战题记录单次模型调用、用量 1135 tokens；治理状态仍为 `pricing_not_configured`，不能据此得出费用。Backend 最近五分钟日志样本中没有 `MissingGreenlet`、`Traceback`、模型调用失败或工具审计失败标记。

## 结论边界

该结果只证明当前七文件镜像、隔离夹具和所述模型接口的有界运行；自动评分主要覆盖路由、状态、证据和引用结构，人工内容核对只覆盖上列三条回答。现有 K3s 业务库尚无项目关联已启用模型配置，故本次不构成 K3s 真实模型端到端验收，也不关闭多节点、长期 SLO、独立 MinIO 或 P4/P9 门禁。
