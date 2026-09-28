# C3.4 完整 UTC 日 SLO 与 Flower 检查点（2026-09-28）

## 采集来源

2026-09-28 00:36 UTC 后，在发布机使用与仓库 SHA-256 `bcc450ebc5fd33238d6c83a7c98b8218b0112b743cb17acfc49f4bb08445b084` 一致的 `collect-q12-evidence.py`，只读查询 `127.0.0.1:39090`，采集 **2026-09-27 00:00～24:00 UTC** 完整日。生成的[日报](../slo-history-2026-09-27-2026-09-27.md)与[可用性](../fixtures/q12/slo-availability-2026-09-27-2026-09-27.csv)、[延迟](../fixtures/q12/slo-latency-2026-09-27-2026-09-27.csv)、[运行成功率](../fixtures/q12/slo-success-2026-09-27-2026-09-27.csv)、[端点分布](../fixtures/q12/slo-endpoint-mix-2026-09-27-2026-09-27.json)均从发布机复制到仓库，并逐文件核对 SHA-256。日报 SHA-256 为 `aa203aa1a7a6b3c80db31fee652cc78207be0a2aa766b25ed502cc5dc5a50ead`。采集器将其标记为 `pre-calibration preflight`，告警和发布门禁仍为 `deferred`。

## 完整日结果

| 项目 | 2026-09-27 UTC 结果 |
| --- | --- |
| Backend / Worker 五分钟检查点 | 各 `288/288`，全部 `up=1` |
| Backend / Worker 原始 `up` 样本 | 各 `5760`，最低值均为 `1`，失败样本为 `0` |
| API 请求量、可用性 | Prometheus 外推约 `40` 次；日最差与平均一小时可用性均为 `100%` |
| API P95 | 五分钟与一小时最差均为 `95 ms` |
| 运行成功率 | 日最差与平均一小时均为 `100%`；报告运行量约 `4` 次 |

同一 UTC 日的 systemd canary 有两份成功日志，分别生成于 `00:33:10` 与 `10:43:45` UTC；每份包含 12 次认证读取和 2 次 `passed` 的 case run，共 **4 次已确认通过的运行**。第二轮是 revision 57 Worker 指标热修复发布后的受控复核。日报的请求端点主要是项目列表、工作台概览、用例运行和运行轮询；这些低量受控流量不能作为代表性业务负载。日报中的请求数和运行量来自 Prometheus 区间查询及取整，canary 日志只用于独立核对，不回填历史样本。发布前后 Worker 计数器有正常重置；[发布证据](c3-worker-only-release-2026-09-27.md)记录新 Worker 的零值样本先于两次运行出现。

## Flower 与当前发布状态

Flower 在该完整 UTC 日有 `5760` 个原始 RSS 样本，最小与最大值均为 `161755136` 字节（约 `154 MiB`）；`up` 最低为 `1`，进程启动时间变化 `0`，Flower 事件计数器重置 `0`。同日 Flower 事件总增量约 `432982`，包含定时心跳等事件，不能换算为业务运行数。2026-09-28 北京时间早间只读复核时，Flower Pod 仍为 9 月 25 日创建的实例，`kubectl top` 容器内存为 `123Mi`。Prometheus RSS 与 `kubectl top` 是不同口径。

Helm revision `57` 仍为 `deployed`，六个业务 Pod 均 Ready、重启计数 `0`；五个 Prometheus target 均 `up` 且无抓取错误，六条规则均 `health=ok`、`state=inactive`。9 月 28 日 08:33 北京时间的定时 canary 自动触发，08:34 以 `Result=success`、退出码 `0` 结束；日志包含 12 次认证读取和 2 次 `passed` 运行。该次属于尚未结束的 9 月 28 日 UTC 日，未计入本报告。

## 门槛与下一步

本次确认了覆盖热修复发布时间的 9 月 27 日完整 UTC 日采集连续性和低流量指标链；该 UTC 日的前半段仍运行旧 Worker。代表性流量下连续 7/14 个完整 UTC 日 SLO 校准尚未建立；9 月 24 日还存在一次 Backend `up=0`，不能把这些天拼成已通过窗口。Flower 的一天稳定样本不足以关闭长期内存和重启观察。继续逐日采集，并在真实业务流量达到可审查规模后核对端点结构、失败形态与告警阈值；C3.4、C3.5 及发布阻断门禁保持开放。本次只读检查未修改业务 Helm、数据库、Secret 或监控规则。
