# C3 发布收口准备（2026-09-29）

本页是当前单节点 K3s 发布范围的 C3.5 准备清单，不是发布通过结论。历史 `release-evidence-index-2026-08-25.json` 保留当时的多节点和跨主机 MinIO 门禁；当前范围以 [`release-scope-2026-09-01.md`](release-scope-2026-09-01.md) 的 2026-09-08 补充为准。最终候选 SHA 尚未绑定，P4/C3.4 与 P9 均保持开放。

| 项目 | 已有证据 | 收口前还需取得 |
| --- | --- | --- |
| 产品能力 | A3、B2、B3 以及 C1～C3.3 已按开发计划和任务记录完成；B2/B3 目标环境证据在 `docs/evidence/b2-*`、`b3-*` | 用最终候选 SHA 复核能力矩阵与实际支持范围；生产 Provider/站点兼容性按接入目标单独验收 |
| 代码质量 | 2026-09-28 后端 2725 passed、2 skipped、覆盖率 82.04%，337 个测试文件独立通过；见 [`evidence/c3-coverage-closure-2026-09-28.md`](evidence/c3-coverage-closure-2026-09-28.md) | 最终 SHA 的 CI、构建、安全及必要的目标环境复验 |
| 单节点运行 | Helm revision 62 的六个 Deployment Ready、零重启，Chart 22/22 文件匹配，5/5 监控目标和 6/6 规则健康；见 [`evidence/c3-main-chart-drift-resolution-2026-09-28.md`](evidence/c3-main-chart-drift-resolution-2026-09-28.md) | 完整源码镜像替换当前 Backend 单文件热修复镜像，按 Chart 差异预检、迁移判断、发布及稳定性观察留证 |
| 定时业务检查 | revision 62 后首轮 canary 于 2026-09-29 00:34 UTC 成功，12 次认证读取和两个 passed Run；见 [`evidence/c3-postchart-slo-canary-2026-09-29.md`](evidence/c3-postchart-slo-canary-2026-09-29.md) | 2026-09-30 00:00 UTC 后核验 9 月 29 日完整 UTC 日的 Backend/Worker 各 288/288 个五分钟点 |
| 发布 SLO | 历史完整日和 Flower 样本为低量受控流量，HTTP route counter 初次采样前请求不能由 `increase()` 还原 | 代表性业务流量、连续 7/14 日校准、Flower 长期 RSS/重启/进程趋势和告警门禁结论 |
| 范围外增强 | 多节点高可用、跨节点调度、跨主机 MinIO source/target 已从本次单节点发布门禁移出 | 后续版本重新纳入时独立立项并补目标环境证据 |

## 最终发布时的顺序

1. 恢复正式主机管理通道，确认基线 Helm revision、运行镜像、队列、迁移 head 与 Chart 差异；当前本机 Linux-mcp 返回 `Transport closed`，SSH 批处理因本机配置的私钥缺失而无法认证，因此本页不记新的主机状态。
2. 将最终代码 SHA 构建为完整源码不可变镜像，记录源码、依赖与镜像摘要；检查镜像与目标环境的构建来源。当前 Windows shell 有 Helm，但无 `docker`、`nerdctl`、`podman` 或 `buildah` 命令，尚未构建候选镜像。
3. 在不破坏观测窗口的前提下执行 Chart 基线/仅预期资源差异预检，确认是否需要迁移 Hook，再发布并核验健康、队列、监控与回滚路径。
4. 用完整 UTC 日和代表性流量完成 C3.4，按 [`q9-release-checklist.md`](q9-release-checklist.md) 核对最终 SHA 的质量、安全、集成、E2E、SLO 与数据治理证据；更新能力矩阵、运行手册和当前候选证据索引后，才给出 P9 发布结论。

`C3.5` 只有在同一最终 SHA 的镜像、目标环境和门禁证据齐备时才能勾选。本页不能代替实时主机复核、镜像构建或完整日采样。
