# ATP 项目当前状态（2026-10-25）

本文汇总截至 2026-10-25 仓库中的实现和已有验收记录。产品目标见 [`../PRD.md`](../PRD.md)，逐项任务见 [`../Task.md`](../Task.md)；带日期的证据只证明记录时的状态，不代表实时生产状态。

## 源码与版本

- `main` 的核对基线为 `d87f3277`（2026-10-24），在 v2.7.0 发布提交之后修复了 Hermes 操作面板及本地模式运行保护。
- v2.7.0 的 T1～T4 共 12 项研发任务在任务台账中均为完成；功能清单、专项测试与证据入口见 [`v2.7.0-release-notes.md`](v2.7.0-release-notes.md)。
- 2026-10-16 的最近一次生产割接记录对应 v2.7.0 发布基线 `b54a8533`。后续提交 `d87f3277` 的生产部署与现场验收尚无本仓库证据，不应视为已上线。

## 已交付能力

| 领域 | 当前仓库能力 | 主要依据 |
| --- | --- | --- |
| 核心平台 | 认证与角色权限、项目/模块/用例、套件/计划、执行、报告、统计、通知与缺陷管理 | [`../Task.md`](../Task.md)、[`current-capability-baseline-2026-10-15.md`](current-capability-baseline-2026-10-15.md) |
| 测试执行 | HTTP/REST、GraphQL、WebSocket、gRPC、Web UI、Android；脚本和低代码执行 | [`current-capability-baseline-2026-10-15.md`](current-capability-baseline-2026-10-15.md) |
| Windows 单机 | SQLite、本地任务和文件存储、API/Web 核心流程、Android 工作台及双模式隔离 | [`windows-standalone.md`](windows-standalone.md)、[`evidence-index-2026-10-15.md`](evidence-index-2026-10-15.md) |
| v2.6.0 | Hermes MCP、视觉断言与定位自愈、Android 设备池与矩阵、弹性性能任务、企业通知和外部缺陷同步 | [`v2.6.0-release-notes.md`](v2.6.0-release-notes.md) |
| v2.7.0 | iOS 设备池与 WDA 会话自愈、Trace 检索与异常归因、多协议 DAG 编排与调试、脱敏、API Key 和灾备演练 | [`v2.7.0-release-notes.md`](v2.7.0-release-notes.md) |

## 部署与验证边界

- 2026-10-16 的 [v2.7.0 现场报告](evidence/linux-site-production-cutover-v2-7-0-2026-10-16.md)记录：PostgreSQL 升至 `20261015_0081`、Helm revision 65、六个核心 Pod 就绪，健康检查及两次真实 API 用例 Canary 通过。实时运行状态需重新查询目标环境。
- v2.7.0 [发布说明](v2.7.0-release-notes.md)记录 Ruff、格式检查、mypy、Bandit、61 项专项测试、12 个专项测试文件独立运行及单一 Alembic 迁移头通过。这些是发布时的结果；后续代码变更需重新执行门禁。
- 当前主 CI 由每周定时或手动触发；integration、E2E 和 release readiness 由手动触发。`main` 没有 required status checks，CI 失败不会阻断推送。命令和触发条件以 [`ci-workflows.md`](ci-workflows.md)为准。
- iOS 代码能力不等于 macOS/Xcode/WebDriverAgent/真机端到端验收；真实设备环境的边界见 [`ios-device-automation-plan.md`](ios-device-automation-plan.md)。

## 文档使用顺序

1. 看本页了解当前概况，随后查看 [`../Task.md`](../Task.md)和对应版本发布说明确认任务完成情况。
2. 按操作目标进入 [`user-operation-manual.md`](user-operation-manual.md)、[`windows-standalone.md`](windows-standalone.md)或 [`deploy-helm.md`](deploy-helm.md)。
3. `PRD.md`、早期路线图、旧版能力基线及带日期的验收记录保留原始规划或历史现场结果；不要将其中的“当前”“待办”直接当作 2026-10-25 的状态。
