# C3.4 revision 62 后每日 canary 检查（2026-09-29）

## Canary 结果

2026-09-29 00:34:26 UTC，正式节点 systemd timer 自动启动 `atp-slo-canary.service`。服务于 00:35:12 UTC 结束，`Result=success`、退出码 0。脱敏日志记录了 12 次认证读取；项目 77 的两个自目标 case run（Run 136、137）均为 `passed`，未输出凭据。

本次 canary 在 Helm revision 62（2026-09-28 09:10:26 UTC）之后运行，是本次 Chart 对齐后的首轮定时业务检查。`atp-slo-canary.timer` 仍为 enabled/active，下次计划在 2026-09-30 08:33:07 Asia/Shanghai（00:33:07 UTC）。

## 当前服务与采集状态

2026-09-29 00:46 UTC 只读核验：Helm revision 62 为 `deployed`；六个应用 Pod 均 Running/Ready，容器重启数为 0；发布 Prometheus 5/5 targets 为 up。自 00:00 UTC 起，Backend 和 Worker 各有 184 个 15 秒 `up` 样本，最低值均为 1。

当天 UTC 尚未结束，184 个原始抓取样本只是截至检查时的中间状态，不能据此声称 Backend/Worker 已完成 `288/288` 个五分钟检查点，也不能生成完整日报告。完整的 revision 62 部署后 UTC 日须等到 2026-09-30 00:00 UTC 后采集；代表性 7/14 日 SLO 校准和 Flower 长期稳定性仍开放。

2026-09-29 00:51 UTC 预检日报采集器：发布机 `/opt/atp-slo-collect-20260924/collect-q12-evidence.py` 的 SHA-256 为 `bcc450ebc5fd33238d6c83a7c98b8218b0112b743cb17acfc49f4bb08445b084`，与仓库版本一致；CLI 已确认可用 `--slo-only`，仅需完整起止日期及本机 Prometheus URL，无需业务账号凭据。此处只核验版本和用法，未提前生成未完成 UTC 日的日报。
