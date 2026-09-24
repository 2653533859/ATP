# Hermes K3s 固定十题、回答修复与受控异常验收（2026-09-24）

## 环境与隔离

在 `192.168.3.196` 的 K3s 临时命名空间中运行 Backend，使用已有独立 Compose 数据库的固定夹具：项目、需求、知识、失败 Case 运行编号均为 1，五个只读工具在夹具准备阶段均返回 `ok`。临时 Pod 只在宿主回环 `127.0.0.1:39185` 提供 API，通过专用 Secret 连接隔离 PostgreSQL、Redis、MinIO；没有连接 `atp-single-node` 的业务数据库或修改项目 77。隔离 Viewer 运行题集，当前版本为 `hermes-core-v2 / 2026-09-23.1`。凭据、供应商地址、原始模型请求和回答正文未写入结构化报告或仓库。

## 固定题与人工内容复核

- 初始镜像 `registry.local/atp/backend:9f161362` 的[结构化报告](hermes-k3s-fixed-evaluation-2026-09-24.json)：固定十题 `10 passed / 0 blocked / 0 failed`，独立模型规划挑战 `passed`。十题包括六道确定性工具题、两道无结果拒答、两道真实模型生成题；10/10 不等于十次模型规划。
- 人工阅读两条生成回答时发现质量缺口：回答把“本次检索片段未显示关联用例”写成项目缺少关联用例，并建议补充用例；隔离夹具实际已有需求—用例关联。结构评分没有发现这项事实范围错误，因此不能只凭 10/10 宣称内容质量通过。
- 提交 `fcf2c507` 将回答要求限制在本次检索片段，禁止由未显示资产推断整个项目不存在该资产，并把回答提示版本升至 `hermes-v3`。修复后的[结构化报告](hermes-k3s-fixed-evaluation-v3-2026-09-24.json)仍为固定十题 `10 passed / 0 blocked / 0 failed`、模型规划挑战 `passed`。再次阅读两条生成回答：均引用 `[S1]`，把需求定义与运行验收状态分开；明确说明本次片段未显示关联和运行信息，建议先查询现有记录，确认缺失后再补充。人工复核仅覆盖这两条回答及一条规划摘要。
- 后端定向 `63 passed`，受影响文件单独 `27 passed`，非集成全量 `2665 passed / 2 skipped`；Ruff、格式、mypy（167 个源文件）和提交/推送钩子通过。

## 受控异常与治理

在首个临时 K3s Backend 上，另建隔离项目与本机回环模型桩。桩正常响应时返回有效 `[S1]`；第二次响应延迟 70 秒以触发 Hermes 的 60 秒查询超时，配置每日查询上限 2、规划上限 1。详见[结构化报告](hermes-k3s-timeout-quota-2026-09-24.json)：

| 场景 | 观察结果 |
| --- | --- |
| 正常桩响应 | HTTP 200，`llm_grounded`，一条来源与有效 `[S1]` |
| 查询超时 | 约 60.04 秒后 HTTP 200，`project_retrieval`，来源 1 |
| 查询限额 | HTTP 200，`project_retrieval`，桩请求数保持 2 |
| 规划限额 | 第二次规划为 `deterministic_fallback` / `unavailable`，原因 `daily_limit_reached`，模型调用 0 |

第一次自动清理请求漏带授权头，返回 403/401；随即重新登录并正确清理，项目与模型配置删除均为 204、回查 404。隔离库中相关项目、需求、Hermes 会话、成员和模型配置计数均为 0，两条临时 Redis 限额键已删除。首次固定题运行新增的 9 条只读工具审计未出现密码、Cookie、API Key 等字段标记。此处超时/限额是本机受控故障，不能代替真实供应商故障、供应商账单或其侧审计。

## 正式单节点发布复核

基于 `9f161362` 镜像只叠加修复后的 `hermes.py` 与 Hermes schema，构建 `registry.local/atp/backend:fcf2c507`，镜像 ID 为 `sha256:a7ddddf58970427bfc876fb444747bfa958e15b485d73cdd0bdeda65089afbea`。两份源码在本地、上传文件、临时 Pod 与正式 Pod 内的 SHA-256 分别一致：`5d6f5f9616296a65bbbdd55cdfd78ffb9cfd2ac622dc967ca73cd0b54fd86bcd` 和 `62127a406fb638d09cd1c43ebe7ad70387c56731ca0a7bca0812fd6baf960762`。

Helm 服务端预演通过，仅更新 Backend 镜像标签后 revision 49 为 `deployed`。[正式 Release 冒烟](hermes-k3s-prompt-v3-release-smoke-2026-09-24.json)在临时合成项目上返回 HTTP 200、`llm_grounded`、`hermes-v3`、一条需求来源和有效 `[S1]`，回答覆盖五次失败、十五分钟锁定和通知方式缺口。项目已删除且回查 404；现有模型配置 1 仍启用、项目 77 的模型绑定仍为空。30 秒四次采样均为 6/6 Pod 就绪、Backend `/health` 200，新 Backend 无重启；最近十五分钟 Backend 日志中无 Traceback、MissingGreenlet、审计持久化失败或常见敏感字段明文标记。

两次临时 K3s 命名空间及其 Secret 均已删除。固定十题是在临时 K3s Backend 联接独立夹具库上完成；正式 `atp-single-node` 业务库只做一条合成需求冒烟，不能称其原有项目已通过十题。代表性回答质量阈值、供应商侧调用与账单审计、长期 SLO、独立 MinIO 和 P4/P9 仍需各自验收。
