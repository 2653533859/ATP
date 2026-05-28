# ATP 平台 Q7 实施计划

> 生成日期：2026-05-28
> 前置：Q6 全部收口（2026-05-28）—— Phase 1 长尾清账 7 项 / Phase 2 AI 自愈 iter4 四子项 / M3 Android 真机执行链路抖动自愈
> 推进策略：**A 类清账主导**——把 Task.md 中残留的 `[~]` 与 `[ ]` 真正清零，沉淀 Q6 新能力的可观测性与运维基线，并为后续业务方向（B 类）腾出干净的地基

---

## 总览

Q6 完成了"看板长尾 + AI 自愈 iter4 + Android 真机自愈"三波收口。Q7 定位为
**工程清账与可观测性沉淀**，不开新业务方向：

- **Phase 1（1 周）** A.3 ADB 自愈运营观察 — 把 Q6 落地的自愈能力转为可量化指标
- **Phase 2（1 周）** A.1 Alembic 迁移统一 — 移除 `create_all` 兜底，首建走纯迁移
- **Phase 3（1-1.5 周）** A.2 部署/运维持续打磨（4 子项）
- **Phase 4（0.5 周）** A.4 Q8 方向编制 — 基于 Q6/Q7 真实数据决定下一季主线

预计 3-4 周完成。完成后 Task.md 应只剩**已主动跳过**的条目，所有 `[~]`/`[ ]` 清零。

---

## Phase 1：ADB 自愈运营观察 [P0]

### A.3.1 worker 进程独立 `/metrics` 端点

**现状**：`backend/app/core/metrics.py` 已有 no-op 兜底的 Counter 抽象；backend 进程通过
`prometheus_fastapi_instrumentator` 暴露 `/metrics`。但 **Celery worker 是独立进程**，
当前不暴露 `/metrics`，导致 ADB 自愈（99% 调用在 worker 内）的指标无法被 Prometheus 抓取。

**实施**：
- `backend/app/worker/celery_app.py` — 注册 `worker_process_init` 信号：
  - 调用 `prometheus_client.start_http_server(WORKER_METRICS_PORT)`
  - 缺依赖时 no-op，与 backend 行为一致
- `backend/app/core/config.py` — 新增 `WORKER_METRICS_PORT: int = 9091`（0 = 关闭）
- `docker-compose.yml` — worker service expose 9091
- `docker/prometheus.yml` — 新增 `atp-worker` job
- Helm Chart `templates/worker-deployment.yaml` — 加 `containerPort: 9091`
- 单测：`backend/tests/worker/test_worker_metrics.py` —
  - prometheus_client 缺失时 no-op
  - signal 注册行为验证

### A.3.2 ADB 自愈指标埋点

**实施**：
- `backend/app/core/metrics.py` 新增 3 个：
  ```
  ADB_RECONNECT_TOTAL = Counter("atp_adb_reconnect_total", ..., labels=("result",))
    # result: success | failure | not_tcp_serial | adb_not_found
  ADB_HEARTBEAT_LOST_TOTAL = Counter("atp_adb_heartbeat_lost_total", ..., labels=("executor",))
    # executor: android | perf | stability | fluency
  ADB_ENSURE_REACHABLE_DURATION = Histogram("atp_adb_ensure_reachable_duration_seconds", ...)
  ```
- `backend/app/services/adb_resilience.py`：
  - `ensure_reachable` 顶部记录开始时间，return 前 `observe(duration)` + 按结果 inc reconnect counter
  - `HeartbeatMonitor` 触发 on_lost 时 inc heartbeat_lost counter（需要 executor label）
- 4 个执行器调用 `HeartbeatMonitor(..., executor_label="android")` 传入身份
- 单测：`test_adb_resilience_metrics.py` — counter inc / histogram observe 注入验证

### A.3.3 Grafana 仪表盘扩展

**实施**：
- `docker/grafana/dashboards/atp-overview.json` 新增 3 个 panel：
  - **Panel A**：ADB Reconnect Outcome（按 result label 堆叠面积图，5min rate）
  - **Panel B**：Heartbeat Lost Rate（按 executor 分组柱状图，1h 增量）
  - **Panel C**：ensure_reachable 延迟 P50/P95/P99（histogram_quantile）
- `deploy/grafana/alerts/atp-alerts.yaml` 新增 2 条告警：
  - `ADBReconnectFailureHigh`：5min 内 failure 比例 > 30% 且总尝试数 > 5
  - `ADBHeartbeatLostBurst`：1h 内任一 executor 心跳触发 > 3 次

### A.3.4 文档与运维 runbook

- `docs/observability-guide.md` 新增"ADB 自愈指标"章节
- `docs/android-device-debugging.md` 第八节加"如何观察自愈指标"段落

### 里程碑

- [ ] A.3.1 worker `/metrics` 端点
- [ ] A.3.2 ADB 指标埋点（含单测）
- [ ] A.3.3 Grafana panel + 告警规则
- [ ] A.3.4 文档与 runbook

---

## Phase 2：Alembic 迁移统一 [P0]

### A.1.1 现状梳理

`backend/app/main.py` 的 lifespan 在启动时调用 `Base.metadata.create_all(bind=engine.sync_engine)`
作为首建兜底。这导致：
- 新部署如果跳过 alembic upgrade，应用照样能跑（但 alembic_version 表为空）
- alembic 与 ORM 双轨制，长期容易出现 schema drift

### A.1.2 实施

- 评估 `APP_AUTO_CREATE_TABLES` 配置项（默认 false）的真实使用场景：
  - 开发模式：保留为 dev 便利开关
  - 生产模式：必须 alembic 驱动
- `backend/app/main.py` lifespan 改造：
  - `APP_AUTO_CREATE_TABLES=false`（默认）时跳过 `create_all`，仅校验 `alembic_version` 表存在
  - `verify_alembic_head_or_warn` 已有，确认其在零状态下的行为
- Docker compose 启动顺序：worker / backend service 加 `depends_on` + 启动前 `alembic upgrade head`
  - 通过 `entrypoint.sh` 或 init container 实现
- Helm Chart：新增 `templates/migrate-job.yaml`（pre-install / pre-upgrade hook）
- 测试：
  - `backend/tests/migrations/test_zero_state_upgrade.py` — 空库 → upgrade head → 所有 ORM 表存在
  - `backend/tests/migrations/test_drift_detection.py` — ORM 与 alembic 差异检测
- 文档：`docs/migrations.md` 编写"零状态首建"流程、回滚指南、drift 排查方法

### A.1.3 风险与兜底

| 风险 | 缓解 |
|------|------|
| 已部署环境升级后 lifespan 不再 create_all 导致缺表 | 升级前在 `docs/migrations.md` 给出"如何确认 alembic 已应用到 head"操作步骤 |
| Helm pre-install hook 失败阻塞首次部署 | hook 设置 `helm.sh/hook-delete-policy: hook-failed` 失败时保留 pod 便于排查 |
| 开发本地起服务忘记跑 alembic | `APP_AUTO_CREATE_TABLES=true` dev 默认开启可保留兜底 |

### 里程碑

- [ ] A.1.2 lifespan 改造 + 测试
- [ ] Docker compose / Helm 启动顺序调整
- [ ] `docs/migrations.md` 文档

---

## Phase 3：部署/运维持续打磨 [P1]

Task.md 5.9 节剩余 `[ ]` 项，拆 4 个独立子任务。

### A.2.1 Worker 镜像瘦身

**现状**：worker 镜像 ~3GB（含 Playwright + Chromium + Android SDK）。

**实施**：
- `Dockerfile.worker` 改造为 multi-stage build：
  - stage 1：build 依赖（apt-get install）
  - stage 2：runtime 仅复制必要二进制 + Python 依赖
- 评估 distroless / alpine 兼容性（Playwright 对 glibc 有要求，alpine 可能不行）
- 目标：镜像缩到 1.5GB 内
- 验证：完整跑通一个 Web + Android 用例

### A.2.2 慢查询 Grafana 面板

**现状**：`backend/app/core/slow_query.py` 已写入 `atp.slow_query` OTel span attribute + `SLOW_QUERY` counter。

**实施**：
- `docker/grafana/dashboards/atp-overview.json` 新增"慢查询"分区：
  - 24h 内慢查询总数（counter rate）
  - 按 SQL prefix 分组 Top 10（依赖 OTel + trace 后端）
- 文档：`docs/observability-guide.md` 加"如何定位慢查询"

### A.2.3 Celery 队列文档化

**现状**：所有 Celery 任务都跑默认 `celery` 队列，没有显式 routing。

**实施**：
- 梳理任务清单：
  - 普通用例执行（高频，短）→ default
  - mobile_special（长任务，独占设备）→ mobile_special queue
  - AI healing / vision（外部 LLM 调用）→ ai queue
  - 清理 / 备份 / 告警 → maintenance queue
- `backend/app/worker/celery_app.py` 配置 `task_routes`
- docker-compose / Helm 提供按 queue 分 worker 副本的 values 示例
- `docs/celery-queues.md` 编写

### A.2.4 K8s 资源 limit 模板

**现状**：`deploy/helm/atp/values.yaml` 的 `resources` 字段为空。

**实施**：
- 按 Deployment 类型给出参考值：
  - backend: requests 200m/512Mi, limits 1000m/2Gi
  - worker: requests 500m/1Gi, limits 2000m/4Gi（含浏览器）
  - beat: requests 100m/128Mi, limits 200m/256Mi
  - flower: requests 100m/128Mi, limits 200m/256Mi
- `values.schema.json` 增加 resources 字段描述
- `docs/deploy-helm.md` 加"资源容量规划"章节

### 里程碑

- [ ] A.2.1 worker 镜像瘦身
- [ ] A.2.2 慢查询面板
- [ ] A.2.3 Celery 队列 routing + 文档
- [ ] A.2.4 K8s 资源 limit 模板

---

## Phase 4：Q8 方向编制 [P1]

### A.4.1 数据复盘

基于 Q6 + Q7 收集的真实数据，给出以下结论：

- 看板告警触发频次与误报率
- AI 自愈采纳率（按 case_type 与 error_fingerprint）
- few-shot 注入对采纳率的提升幅度
- vision flag 在 灰度试点中的效果（如有启用）
- ADB 自愈重连成功率、心跳触发率
- 慢查询 Top 10 与优化潜力

### A.4.2 候选业务方向调研

从 Q6 评审里列出的 B 类候选中筛选：

- B.1 AI 自愈 iter5：vision 生产化 + 自愈后回归测试自动化
- B.2 AI 用例生成：从需求 / 截图 / API 文档生成用例草稿
- B.3 性能压测中心：HTTP/gRPC 压测集成 locust/k6
- B.4 跨设备同步用户偏好：localStorage → user_settings 表
- B.5 测试数据集 v2：版本管理 / 审计 / schema 校验

### A.4.3 输出

- `docs/implementation-plan-2026-Q8.md`
- 与团队对齐 Q8 主线方向（1-2 个 P0 + 2-3 个 P1）

### 里程碑

- [ ] A.4.1 Q6/Q7 数据复盘报告
- [ ] A.4.2 候选方向调研笔记
- [ ] A.4.3 Q8 计划编制

---

## 实施顺序建议

```
Week 1（Phase 1）
  A.3.1 worker /metrics 端点 ────────── 2 天
  A.3.2 ADB 自愈指标埋点 ─────────────── 2 天
  A.3.3 Grafana panel + alerts ─────── 1 天
  A.3.4 文档 ──────────────────────── 0.5 天

Week 2（Phase 2）
  A.1.2 lifespan 改造 + 迁移测试 ────── 2 天
  A.1 Docker/Helm 启动顺序 ──────────── 1 天
  A.1 docs/migrations.md ────────────── 1 天

Week 3（Phase 3）
  A.2.1 worker 镜像瘦身 ──────────── 1-2 天
  A.2.2 慢查询面板 ──────────────── 1 天
  A.2.3 Celery 队列 routing ─────── 1 天
  A.2.4 K8s 资源 limit 模板 ───────── 0.5 天

Week 4（Phase 4）
  A.4.1 数据复盘 ──────────────────── 1-2 天
  A.4.2 候选方向调研 ──────────────── 1 天
  A.4.3 Q8 计划编制 ──────────────── 1 天
```

---

## 验收标准

Q7 完成时应满足：

- ✅ Task.md 中所有 `[~]` 与 `[ ]` 条目清零（除主动跳过的 `[-]`）
- ✅ Grafana 仪表盘可观察 ADB 自愈、慢查询两类业务指标
- ✅ 新部署可纯 alembic 驱动首建，不依赖 `create_all` 兜底
- ✅ worker 镜像减重 ≥ 30%（目标 < 2GB）
- ✅ `docs/implementation-plan-2026-Q8.md` 编制完成
- ✅ 各阶段子任务都有对应 commit + 测试覆盖

---

## 与 Q6 的衔接

- **延续**：Q6 P2.x（反馈聚合 / few-shot / vision）需要 Q7 A.3 + A.4 数据观察来验证效果
- **延续**：Q6 M3（ADB 自愈）落地后，Q7 A.3 是必备的运营观察基线
- **新增依赖**：A.3.1 worker `/metrics` 端点是首个 worker 进程级 Prometheus 集成，后续所有 worker 指标（AI healing 调用统计、Celery 内部状态）都会复用此端点

---

## 当前进度记录

- Phase 1：未启动
- Phase 2：未启动
- Phase 3：未启动
- Phase 4：未启动
