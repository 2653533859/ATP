# Hermes K3s 真实模型规划与临时项目权限验收（2026-09-24）

## 环境与范围

- 目标为 `192.168.3.196` 的 `atp-single-node` 单节点 K3s 联调 Release；Helm revision 47 为 `deployed`，六个 ATP Pod 均为 `1/1 Running`，Backend `/health` 返回 200。
- 管理员通过服务器受限密码文件登录；密码、Cookie、Token、供应商 Endpoint、API Key 和回答正文均未写入本记录。
- 当前 K3s 有一份已启用且保存了 API Key 的配置 `id=1`，模型名为 `claude-opus-4-6-thinking`；原有四个项目均未绑定模型。该配置的正式连接测试返回 HTTP 200、`response_received=true`，耗时 4320.43 ms。它与独立验收环境使用的 Gemini 配置不是同一份配置。

## 有界真实模型请求

通过正式项目 API 创建临时项目 84，绑定模型配置 1，未修改已有项目 77。第一次使用独立规划挑战题请求 Hermes：HTTP 200，`source=model`、`validation=accepted`，模型选中 `failed_tasks` 和 `quality_trend`；当时临时项目没有运行，两步工具均为 `empty`，不能算作有证据的工具验收。

随后只在临时项目内通过正式 API 创建模块 94、API 用例 77，审批后执行一次仅请求本机 Backend `/health` 的 GET。用例故意期待 HTTP 201，实际 `/health` 为 200，因此运行 125 按预期终态 `failed`。再次提交同一道规划挑战题得到：

| 核对项 | 实际结果 |
| --- | --- |
| Hermes 接口、规划 | HTTP 200、`matched`；`source=model`、`validation=accepted`、`model_calls=1` |
| 工具选择 | `failed_tasks`、`quality_trend`，均为 `ok`，各有 1 条证据 |
| 模型用量 | 输入 977、输出 165、总计 1142 Token；规划耗时 5463 ms |
| 成本 | `estimated_cost=null`；本次未取得计价结果，不能解释为零成本 |
| 趋势回答 | 对回答做了有限关键词检查，命中单个时间段不足以判断变化的提示；未记录或人工审阅回答正文 |

这证明 K3s 项目绑定后的真实模型候选规划、固定只读工具校验、运行证据、用量和会话记录可贯通。它不是 K3s 固定十题质量验收，也不证明模型回答的所有来源引用或供应商账单金额准确。独立环境的十题结果见[独立验收记录](hermes-isolated-acceptance-2026-09-24.md)。

## 权限、审计与清理

- 将现有 `atp-slo-canary` 测试账号临时作为项目 84 的 `viewer`。该账号可读取项目并通过确定性 Hermes 工具读取失败任务；创建模块返回 403，读取无成员关系的项目 78 也返回 403。测试后立即通过成员 API 移除，项目 84 成员只剩管理员 owner。
- 清理前，项目 84 的审计含 `hermes_read_tool` 5 条、`access_denied` 1 条、成员增删各 1 条及用例审批 1 条；项目 78 另有跨项目 `access_denied` 1 条。审计读取使用管理员 API，未输出明文详情。
- 通过 `DELETE /projects/84` 清理临时项目后，项目 84、用例 77 和运行 125 均返回 404；数据库只读复核确认项目、模块、Hermes Session 和项目成员对项目 84 的计数均为 0。原项目 77 仍为 HTTP 200 且模型绑定仍为空，模型配置 1 仍启用；项目 84 的 9 条审计记录按系统留存策略保留。
- 收尾时 Helm revision 47 保持 `deployed`、六个 Pod 均 `1/1 Running`、Backend `/health` 为 200；Backend 最近 15 分钟、最多 2000 行日志中的 `Traceback`、`MissingGreenlet`、Hermes 工具审计持久化失败及规划失败标记计数为 0。

## 未关闭项

当前 K3s 临时项目已删除，固定十题所需的编号 1 运行、需求和知识资产没有在业务库中伪造。K3s 的真实模型回答引用质量、异常/超时回退、供应商侧调用审计与账单、跨节点故障域，以及 P4/P9 的 7/14 天代表性 SLO 和独立 MinIO，仍需各自的验收证据。
