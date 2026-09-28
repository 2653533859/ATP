# C3.4 revision 62 后 SLO 检查点（2026-09-28）

## 采集边界

2026-09-28 10:27 UTC 通过 Linux-mcp 只读连接正式节点 `192.168.3.196`。Kubernetes context 为 `atp-single-node`，Helm release `atp-single-node` 位于同名 namespace。revision 62 于 09:10:26 UTC 部署；以下连续性查询覆盖 09:27～10:27 UTC 的一小时窗口，不构成完整 UTC 日。

## revision 62 后观测

- Helm revision 62 为 `deployed`；六个应用 Deployment 各 `1/1` Ready，六个 Pod 均 Running 且容器重启数为 0。
- 发布 Prometheus 当前 5/5 targets 为 up；6/6 规则健康，均为 inactive。
- Backend 与 Worker 各有 240 个原始 `up` 样本，窗口内最低值均为 1。按当前 15 秒抓取间隔，这与一小时的连续观测一致。
- Flower RSS 一小时最小值 `142852096` 字节、最大值 `145735680` 字节（约 136～139 MiB）；进程启动时间变化为 0。该窗口过短，不能作为长期稳定性结论。

## Canary 定时器

`atp-slo-canary.timer` 为 enabled/active。最近一次服务于 2026-09-28 00:33:33 UTC 触发、00:34:19 UTC 结束，`Result=success`、退出码 0；日报志为 12 次认证读取和两次 `passed` 运行（Run 134、135）。该次发生在 revision 62 部署前，不能当作新版本部署后 canary。下一次计划于 2026-09-29 08:34:26 Asia/Shanghai（00:34:26 UTC）触发。

## 下一步

等待下一次定时 canary 后核对新运行结果与 revision 62 状态。完整 revision 62 部署后 UTC 日从 2026-09-29 00:00 UTC 开始，需在该日结束后生成同 SHA 的完整日报，并核验 Backend/Worker 各 288/288 五分钟点。受控 canary 仍不等于代表性业务负载；连续 7/14 日校准、Flower 长期趋势、完整源码镜像发布以及 C3.4/C3.5 门禁继续开放。
