# C3.4 SLO 与 Flower 检查点（2026-09-27 北京时间）

## 完整 UTC 日采集

使用与仓库 SHA-256 一致的 `collect-q12-evidence.py` 从发布 Prometheus `127.0.0.1:39090` 只读采集 2026-09-24～25，生成 [`../slo-history-2026-09-24-2026-09-25.md`](../slo-history-2026-09-24-2026-09-25.md) 和其引用的四份 CSV/JSON 原始摘要。采集器将整个窗口标记为 `pre-calibration preflight`，告警与发布门禁均为 `deferred`。

- 9 月 24 日 Backend/Worker 都返回 288 个五分钟检查点，但 Backend 有一个 `up=0`，所以 Backend 连续性失败；9 月 25 日两者均为 `288/288` 且所有点为 `up=1`。窗口的 Prometheus 日增量约为 339/85 次 HTTP 请求和 2/1 次运行；这些是外推估计，不能当作精确业务笔数。
- 9 月 24 日流量含 Hermes 受控验收，9 月 25 日主要是定时 canary；端点分布和这两天的运行量不足以证明代表性业务流量。9 月 26 日 UTC 日在本次采集时尚未结束，未纳入完整日报告。
- 9 月 25 日 00:33 UTC 的 systemd canary 日志显示两次 `passed` 运行，而 Prometheus `atp_run_outcomes_total{status="passed"}` 在 00:34:20 UTC 首次出现时已为 1，00:34:40 UTC 才为 2。该日 `increase(...[1d])` 约为 1：首次标记序列没有先前的零样本，Prometheus 无法倒推第一次增量。历史报告的运行量及成功率据此保留证据限制，不把 canary 日志补写成 Prometheus 样本。

仓库现已在 Worker 指标端点启动前预初始化 `case/suite/plan` × `passed/failed/error/skipped/cancelled` 的零值序列，并加入回归用例。**目标机 revision 56 尚未包含此代码**；在经过发布预检、部署并看到零值序列先于首个真实事件出现前，不能宣称目标环境已修复首次计数漏算。当前发布 Worker 使用 `--pool=solo`；多进程指标汇聚不在本次验证范围内。

## Flower 与发布状态

2026-09-26 16:36 UTC 只读复核：Helm revision 56 为 `deployed`，六个业务 Pod 均 Ready 且重启计数为 0；五个 Prometheus target 均 `up`，六条规则 `health=ok`、`state=inactive`。Flower 在最近四小时查询中有 718 个原始 RSS 样本，最小/最大均为 `161755136` 字节（约 154MiB），`up` 最低值为 1，进程启动时间变化为 0；`kubectl top` 容器内存为 123Mi。Flower 事件计数四小时增量约 5.4 万，包含多类事件，不能换算为完成运行数。连续序列只从 9 月 26 日启用抓取后开始，尚不足以证明长期稳定。

## 后续门槛

先完成零值指标的受控发布和首轮目标指标验证，再积累代表性流量下连续 7/14 个完整 UTC 日的采样、端点结构与告警校准。9 月 24 日的 Backend 下线点会使包含该日的连续窗口失败。C3.4 与 C3.5 均继续开放；本次没有升级业务 Helm、迁移数据库或更改 Secret。
