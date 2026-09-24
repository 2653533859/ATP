# Hermes 独立环境验收记录（2026-09-24）

## 环境与版本

- 目标机：`192.168.3.196`。验收目录：`/opt/atp-hermes-eval-20260924`；Compose 项目：`atp-hermes-eval-20260924`。
- PostgreSQL、Redis、MinIO 使用该 Compose 项目的独立命名卷与私有网络。Backend 与 Worker 不连接现有 `atp-single-node` K3s 服务；Backend 仅映射宿主机 `127.0.0.1:39184`。
- 验收镜像：`registry.local/atp/hermes-evaluation-backend:20260924`，镜像 ID `sha256:c547c842f8fed2f6fd5fd6d017b3e7c266ffb55dd4a876f88ad417c241821722`，代码标签 `71b0b0b394b6bc86c4627aaca96605a95ed025c5`。基础镜像为 `registry.local/atp/backend:bdb84286`，叠加七个已核对 SHA256 的运行文件；没有改变现有 K3s Backend 镜像。
- `/health` 返回 200；管理员登录后题集为 `hermes-core-v2 / 2026-09-23.1`、10 题；模型配置 ID 1 的连接测试成功。模型密钥经目标机内存管道从现有已启用配置导入隔离 API，并由隔离 APP_SECRET_KEY 重新加密；没有写入仓库或报告。

## 夹具与评测

- [夹具报告](hermes-isolated-seed-2026-09-24.json)：经 API 创建隔离项目、需求 1、知识 1、用例及运行 1。运行实际取得隔离 `/health` 的 HTTP 200，然后因预设 999 状态码断言进入 `failed`。五个只读工具均返回 `ok` 与证据。项目 ID 为 1，另建无授权项目 ID 2 供越权检查。
- [首轮失败报告](hermes-isolated-evaluation-initial-2026-09-24.json)：修复前 4 题通过、6 题请求失败，模型规划挑战题请求失败。Backend 堆栈定位 `MissingGreenlet`：只读工具回滚后，后续访问已过期的 User 属性。修复后保留回滚隔离与审计提交，在返回前刷新 User。
- [最终评测报告](hermes-isolated-evaluation-final-2026-09-24.json)：在上述镜像上，以隔离项目 viewer 账号执行固定十题，`10 passed / 0 blocked / 0 failed`；单独的模型规划挑战题 `passed`，模型规划器选出 `failed_tasks` 和 `quality_trend`，两步工具状态均为 `ok`。固定十题中的六道工具路由题由确定性规则处理，不应计为六次模型规划成功。
- 人工读取了两条有来源的模型回答及规划挑战题回答：两条模型回答均引用需求 1 并标明证据不足；质量趋势只有一个时间段时，原回答没有说明无法比较。修复后 [质量回答核对](hermes-isolated-quality-answer-2026-09-24.json) 显示模型规划 `accepted`，两个工具为 `ok`，回答明确说无法判断是否有变化。该记录只保存结构标记，不保存回答正文。

## 权限、反馈与审计

- viewer 对无授权项目的项目详情、Hermes query、orchestrate 和 tools/execute 均返回 403；创建项目、修改成员、创建 Hermes 草稿均返回 403。匿名项目读取返回 401，非法跨项目工具参数返回 422，越过会话所有者提交反馈返回 404。
- viewer 对自己会话的反馈：首次 `helpful` 使计数从 `(0,0,0)` 变为 `(1,0,1)`；重复同值不增加；改为 `not_helpful` 后变为 `(0,1,1)`；过期 message_id 返回 409，跨项目提交返回 403。
- 修复前工具结果虽为 `ok`，`hermes_read_tool` 审计未提交，跨项目 403 也没有持久审计。修复后数据库观察到项目 1 的 `hermes_read_tool` 21 条、`access_denied` 1 条，项目 2 的 `access_denied` 2 条。计数包含多轮复核请求，不应解释为单轮十题的调用量。拒绝日志由独立 Session 提交，不会提交被拒请求的业务事务。
- 模型规划治理在反馈核对时报告 `attempts=1`、`model_calls=1`、用量 1144 tokens；计价状态为 `pricing_not_configured`，因此不能据此计算费用。最终多轮执行后的用量须以供应商账单和最新治理快照复核。

## 结论边界

本记录证明该独立单机环境、当前七文件叠加镜像、隔离夹具及上述 API/模型交互。自动评分只覆盖路由、状态、证据、引用等结构条件；人工抽查仅覆盖列出的回答，不能推断所有答案事实正确或长期趋势变化。尚未做 7/14 天质量趋势、多节点并发和现有 K3s Release 发布验收。现有业务库、K3s Helm Release、Windows 前端目录均未迁移或修改。

后续 2026-09-24 已将同一镜像发布到现有 K3s 单节点联调 Release；发布及有界健康证据见[单节点 K3s 发布记录](hermes-k3s-rollout-2026-09-24.md)。本段记录的是独立验收当时的环境状态。

同日隔离项目另以 Gemini 3.8 Flash 完成一轮真实模型验收，结果见[Gemini 独立环境验收记录](hermes-gemini38-isolated-acceptance-2026-09-24.md)。
