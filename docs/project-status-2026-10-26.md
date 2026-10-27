# ATP 项目当前状态（2026-10-27）

本文按 2026-10-26 本地 `main` 与 `origin/main` 的同步结果、仓库代码和已归档证据整理。产品范围见 [`../PRD.md`](../PRD.md)，任务台账见 [`../Task.md`](../Task.md)。带日期的测试和现场记录仅证明记录时的状态。

## 代码与版本

- `git fetch origin` 后，本地 `main` 与 `origin/main` 均为 `deaf884f`（2026-10-26，接口场景来源请求指纹）；同步前工作区干净，无待合并提交。
- v2.7.0 的 T1～T4 共 12 项研发任务已按 [`v2.7.0-release-notes.md`](v2.7.0-release-notes.md) 和 `Task.md` 记录为代码完成。发布后的新增代码包括 Hermes 和本地模式修复，以及 AutoDroid 对照计划的 A1/A2/M1/M2。
- 2026-10-27 在 Linux 生产主机（`CHINAMI-762P0P5:2222`，`192.168.3.196`）完成 **v2.7.1** 生产割接上线：数据库升级至 `20261026_0082`、后端上线 `v2.7.1-cloudsync`、K3s 六个核心 Pod 1/1 Running 0 重启，Systemd `atp-slo-canary.service` 真实业务探针通过（12 次认证读、Run 200/201 passed）。实测证据见 [2026-10-27 v2.7.1 现场报告](evidence/linux-site-production-cutover-v2-7-1-2026-10-27.md)。

## 当前能力与验证口径

| 领域 | 当前代码状态 | 证据边界 |
| --- | --- | --- |
| 平台与执行 | 认证、项目/用例、套件/计划、HTTP/GraphQL/WebSocket/gRPC、Web/Android、报告、通知、缺陷管理；Windows SQLite 单机与 Linux 服务器双模式 | 详见 [`current-capability-baseline-2026-10-15.md`](current-capability-baseline-2026-10-15.md) 和 [`../Task.md`](../Task.md)；本次未重新跑全量门禁 |
| v2.7.0 | iOS 设备与 WDA 自愈、Trace、混合 DAG、脱敏、API Key、灾备演练 | 发布时的专项测试与质量门禁见发布说明；iOS 真机端到端仍需 macOS/WDA 环境 |
| D0～D7 本地与云端汇总全方案 | 非 C 盘物理落盘（D0）、多项目隔离（D1）、脱敏摘要与 Outbox（D2）、云端接收中心 0082（D3）、跨网络同步与看板（D4）、在线受控访问（D5）、历史数据迁入本地（D6）、桌面宿主（D7） | D0～D6 有分阶段实测记录，见 [D0/D1 证据](evidence/windows-desktop-d0-physical-path-verification-2026-10-26.md)、[D3/D4 证据](evidence/windows-desktop-cloud-sync-d3-d4-2026-10-26.md)、[D5/D6 证据](evidence/windows-desktop-cloud-d5-d6-closure-2026-10-27.md)；D5 的大文件和多用户验收未完成。D7 已产出自带 Python 后端的 Windows 便携 ZIP 并通过解压运行验收，见 [打包说明](windows-pyinstaller-backend.md)；原生窗口、MSI、升级和新电脑验收尚未完成。 |
| A1/A2 规格影响与建议可靠性 | 两版 OpenAPI 规格比对、场景来源请求指纹追溯、建议成立性校验、去重与失效防护 | 真实业务规格实测识别 1 新增、1 变更、1 废弃端点与 3 项场景步骤，通过请求指纹区分来源变更与局部覆盖；用真实 GET/POST 响应验证建议生成、去重应用、失效拦截与零二次写，见 [A1/A2 证据](evidence/autodroid-atp-api-real-spec-and-suggestions-a1-a2-2026-10-26.md) |
| M1/M2/M3 Android | 镜像操作形成草稿、结构化预检诊断（M2）与真机执行闭环（M3）已全量贯通 | 华为平板真机（`5CQBB26605200808`）实测完成 8 步设置交互（Run 1 passed 16265ms）、异常故障阻断与租约安全释放（Run 2 failed），截图落盘并经 D2/D4 同步至云端服务器；见实测报告 [M3 证据](evidence/autodroid-atp-android-m3-closed-loop-2026-10-26.md) |

## 未完成的当前计划

1. **M4 iOS 可视化录制试点（P1）**：先在 macOS/Xcode/WDA 和真机上验收既有 iOS 执行链；环境就绪后再做少量标准步骤录制与回放。
2. **M5 探索路径资产试点（P2）**：依赖 M3 和明确的业务应用，评估路径审阅、冻结与当前安装版本回放的覆盖及误判数据。

上述 A0～M5 的任务定义、依赖和退出标准见 [`autodroid-learning-development-plan-2026-10-25.md`](autodroid-learning-development-plan-2026-10-25.md)。`Task.md` 中较早的 `[~]`、`[ ]` 保留其历史阶段语境，不应直接视为本次最新开发队列。

## 文档与门禁

- 当前使用本页作为状态入口；版本交付看 [`v2.7.0-release-notes.md`](v2.7.0-release-notes.md)，操作看 [`user-operation-manual.md`](user-operation-manual.md)，双模式运行看 [`windows-standalone.md`](windows-standalone.md)。
- CI 由每周定时或手动触发，integration、E2E、release readiness 需手动触发；`main` 无 required status checks。当前触发条件以 [`ci-workflows.md`](ci-workflows.md) 为准。
