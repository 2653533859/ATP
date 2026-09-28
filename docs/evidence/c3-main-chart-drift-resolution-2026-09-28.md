# C3.4 主 Helm Chart 漂移收口（2026-09-28）

## 结果

Helm release `atp-single-node` 已在 `atp` namespace 升级至 revision **62**，以仓库主 Chart 对齐此前由精确旧 Chart 快照发布的六个 Deployment。revision 62 为 `deployed`，六个 Deployment 均 Ready，容器重启数为 0。升级期间首次尝试因历史 Server-Side Apply 字段管理冲突自动回滚到 revision 61；复核冲突仅涉及已审查的 Deployment 更新策略后，第二次升级显式使用 `--force-conflicts` 成功。不能据此声称升级过程零中断：Backend、Beat、Web Recorder Pod 在第一次失败/回滚过程中曾重建。

## Chart 变更范围

以 revision 59 为现场基线，仓库主 Chart 的六个 Deployment 差异均为此前已验证的运行配置，不涉及迁移 Hook：

| Deployment | 主 Chart 中的变更 | 依据 |
| --- | --- | --- |
| Backend | hostNetwork 下限制滚动替换并增加配置校验和 | `74a15fa4`, `abcd375c` |
| Beat | 增加配置校验和 | `abcd375c` |
| Flower | 改为零 surge 的替换策略并增加配置校验和 | `287755f3`, `abcd375c` |
| Performance Worker | 零 surge 更新、配置校验和、Tini、Pod 唯一身份和心跳来源 | `74a15fa4`, `ff1e82c7`, `7599f0da` |
| Web Recorder | 零 surge 更新、配置校验和、Tini、Xvfb 有界显示重试 | `abcd375c` |
| Worker | 零 surge 更新、配置校验和、Pod 唯一 Celery 节点名和 Tini | `8ecd77e5`, `ff1e82c7`, `74a15fa4` |

升级前仓库 Chart 逐文件检查、六个 Deployment 的显式变更许可和服务端 dry-run 均通过；迁移 Hook 与现场一致，正式升级使用 `--no-hooks`。首次尝试在 Flower、Performance Worker、Worker 的 `.spec.strategy.type` 遇到历史 `kubectl-patch` SSA manager 冲突，Helm 自动回滚。确认变更对象及字段后，以相同 Chart 重试并允许解决这些冲突；revision 62 发布成功。升级前 Redis 各队列长度为 0、Celery active/reserved 为 0、Web Recorder 活跃会话为 0；Performance Worker 有一个预期的周期心跳任务。

## revision 62 部署后核验

- 六个 Deployment 全部 Ready；所有容器 `restartCount=0`。
- Backend、Flower 健康端点均返回 HTTP 200。
- Backend、Flower、Performance Worker、Web Recorder、Worker 的生效策略为 `RollingUpdate(maxSurge=0,maxUnavailable=100%)`；Beat 为 `Recreate`。
- Worker 和 Web Recorder 的 PID 1 为 Tini；Web Recorder 有一个 Xvfb 进程。
- Redis 六个业务队列长度均为 0；Worker active 为 0；Performance Worker 保留一个预期心跳；Web Recorder `active_sessions=0`。
- 已部署 Backend 容器内的嵌套知识摘要敏感字段脱敏断言通过。
- 发布 Prometheus 5/5 targets 为 up，6/6 规则健康。Flower RSS 单次样本约 135 MiB，仅表示该次观察，不作为长期内存稳定性证据。
- revision 62 部署后以 `--require-baseline-match` 复跑仓库 Chart 预检，22 个 Chart 文件与仓库一致，10 个普通资源和 1 个 Hook 均无未解释差异。

## 后续门禁

Chart 漂移已收口，但 C3.4 尚未关闭。首个完整的 revision 62 部署后 UTC 日从 2026-09-29 开始；需要继续取得 Backend/Worker 各 288/288 个五分钟点和有代表性的业务负载，再完成 7/14 日 SLO 校准。继续观察 Flower 的 RSS、重启和进程启动趋势。当前 Backend 仍运行单文件知识脱敏热修复镜像，不是 `4d451431` 的完整源码镜像发布；本次未运行迁移 Hook，也未声称完成完整 SHA 发布、P4/P9 或最终验收。
