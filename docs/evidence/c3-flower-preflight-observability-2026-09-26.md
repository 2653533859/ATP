# C3.4 Flower 监控与发布 Chart 预检（2026-09-26）

## 变更范围

为防止 revision 55 旧 Chart 再次覆盖 Flower 有界保留配置，在现有部署校验器新增只读 release 预检：比较候选 Chart 与当前仓库文件哈希；使用当前 release 用户 values 渲染候选，并与 `helm get manifest/hooks` 比对；验证 Flower `max_tasks<=1000`、`max_workers<=100`、`purge_offline_workers<=300`、内存 limit 至少 512Mi 和 `hostNetwork` 下先释放端口的策略。输出仅含资源名、变化字段路径及镜像 tag；未列入 `--allow-change` 或 `--allow-hook-change` 的变化使退出码非零。Helm values 和 Secret 只在进程内处理，失败输出不回显原文。

目标机演练：旧发布 Chart 与仓库当前 Chart 有 10 个文件不同，预检直接拒绝。使用当前仓库 Chart 后逐文件校验通过，Flower 约束通过，渲染 10 个非 Hook 资源和 1 个 Hook；相对现有 revision 56，Backend、Beat、Flower、Performance Worker、Web Recorder、Worker 共 6 个 Deployment 会变化，镜像 tag 与迁移 Hook 未变化。Worker/Recorder 的命令、环境变量及多个模板注解/策略在变化范围内，未将它们作为本次监控更新发布；业务 Helm 继续保持 revision 56。

预检还验证了逐项 `--allow-change` 能在显式列出上述 6 个资源后通过；这只证明脚本的确认机制有效，**不是**批准执行完整 Chart 升级。后续变更镜像时应以 `--image-tag` 提供相同目标 tag，并与实际 Helm 升级参数一致。

发布 Prometheus 增加 `atp-flower` 对现有 `:5555/metrics` 的抓取；`AtpReleaseTargetDown` 纳入 Flower，并新增 Flower 进程 RSS 超过 400MiB 持续 10 分钟及进程启动时间变化告警。修复旧 `AtpRunSuccessRateLow` 规则选择 `job="atp-backend"` 的错误：目标 Prometheus 实际只有 `atp-worker` 暴露 `atp_run_outcomes_total`。Grafana 原看板增加 Flower RSS、五分钟事件量和 24 小时进程启动变化三个面板。

## 目标验证

- 更新前发布机三份配置文件 SHA-256 均与仓库旧版本一致，已分别保存 `.bak-20260926`。新文件 SHA-256 与当前工作区逐一相同，`promtool check config/rules` 通过；向 Prometheus 发送 HUP 后未重建容器，容器启动时间仍为 2026-09-20 04:07:03 UTC、重启计数 0，五个 target（Backend、普通 Worker、Performance Worker、Flower、Prometheus）均 `up`。
- Flower RSS、进程启动时间和事件计数均有真实样本；一次快照中 RSS 为 `161755136` 字节（约 154MiB），五分钟查询已有 14 个 RSS 样本，启动时间变化为 0，`flower_events_total` 聚合累计 `435396`（包含多类事件，不能当作完成运行数）。稍后十分钟查询已有 31 个 RSS 样本。6 条 Prometheus 规则均 `health=ok`、`state=inactive`，运行成功率规则已回读为 `atp-worker`。Grafana API 回读 `atp-overview` 共 20 面板，新面板 ID 18～20 均存在。没有输出或提交 Grafana 凭据。
- 业务 Helm revision 56 保持 `deployed`，6/6 Pod Ready、重启 0；本轮没有业务 Pod 重建、数据库迁移或 Secret 更新。
- 定向发布预检 `4 passed`、单节点可观测性契约 `7 passed`、既有部署与质量门禁契约 `41 passed`；两个改动测试文件均独立运行。后端项目虚拟环境的非集成全量回归为 `2678 passed, 2 skipped`，Ruff 检查与格式检查通过。首次误用系统 Python 导致 158 个测试在收集期因缺少 FastAPI/不兼容 SQLAlchemy 而报错；切换到 `backend/.venv` 后完整通过，该环境错误不计为产品测试失败。
- 2026-09-24 完整 UTC 日的 Backend 5 分钟 `up` 为 `287/288`（10:10 UTC 为 0），Worker `288/288`；约 339 次 HTTP 请求、2 次 Worker 运行结果。该 down 点紧邻 Helm revision 54 在 10:09:40 UTC 的升级，时间相关不等于已证明根因，且连续性门禁仍按失败处理。9 月 25 日 Backend/Worker 均 `288/288`，约 85 次请求、1 次运行结果。请求/运行量来自 Prometheus `increase(...[24h])`，因外推是近似值，包含受控验收及 canary，不能视为代表性业务流量。

## 边界与回退

`process_resident_memory_bytes` 是 Flower 进程 RSS，容器内存还需结合 `kubectl top`；启动时间变化告警不能独自区分计划内滚动更新和故障重启。Prometheus 只在回环地址提供查询，当前规则没有证明外部通知投递。新序列从本次抓取启用时开始，不能追溯历史 OOM。预检用 `helm template` 和现有用户 values，正式升级仍须执行相同覆盖参数的 Helm 服务端 dry-run、复核差异并确认镜像在目标节点可用。

如监控配置需回退，恢复目标 `/opt/atp-single-node-observability` 中三个 `.bak-20260926` 文件至原路径，执行 `promtool check config` 后向 `atp-single-node-prometheus` 发送 HUP，并复核 targets/rules、Grafana 原面板及业务 Pod；不需回滚业务 Helm。C3.4 的长期 Flower 内存、代表性 7/14 日 SLO 和发布告警校准仍未完成，C3.5 最终 SHA 收口尚未开始。
