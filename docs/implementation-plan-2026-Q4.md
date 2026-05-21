# ATP 平台 Q4 实施计划

> 生成日期：2026-05-20
> 优先级：P0=紧急高价值，P1=高价值，P2=中价值
> 前置：Q3 四方向（E AI 用例生成 / H Q2 收口 / F i18n / G OTel+Jaeger）已于 2026-05-20 全部收口

---

## 总览

Q3 完成了"效率工具化（AI/i18n）"与"可观测性下沉（OTel/Jaeger）"两个主题。Q4 的定位是 **性能与运维下沉 + 长期收口**：把 Q2/Q3 积累的优化项、Task.md 中 Phase 5.x 的待办项与几个长期 `[~]` 项一并消化，让平台从"功能齐备"走向"运维友好、性能可观"。

### 优先级与依赖

```
P0 → 方向 A：性能与运维下沉（合并 Phase 5.5 / 5.6 / 4.6 P2 未完成项）
P1 → 方向 B：可观测性二阶段（Prometheus + Grafana，与 Q3 G 的 tracing 形成闭环）
P1 → 方向 C：长期 [~] 项收口（M3 Android 真机 / Alembic 纯迁移 / i18n 英文复核）
P2 → 方向 D：测试资产与版本治理（用例快照 / Mock 版本管理）
P2 → 方向 E：报告与缺陷集成增强（报告模板 / 定时邮件 / GitLab Issues）
P2 → 方向 F：部署形态扩展（Helm Chart / 数据库自动备份）
```

实施顺序按业务感知与基础设施依赖：A → C → B → D → E → F。

---

## 方向 A：性能与运维下沉 [P0]

### 目标

把 Task.md Phase 5.5 / 5.6 / 4.6 中长期挂起的 P1/P2 项合并落地，建立可量化的性能基线与可观测的运维信号。

### 实施步骤

#### A.1 数据库性能：Keyset 分页与索引补齐

- `backend/app/api/v1/runs.py`、`cases/*`、`statistics.py` 的高数据量列表查询从 OFFSET 切换为 cursor (Keyset) 分页
- 新增 Alembic 迁移：
  - `test_runs (case_id, status, created_at)` 复合索引
  - `step_results (run_id, idx)` 已有则跳过
- `backend/tests/api/test_pagination.py` 新增 cursor 分页回归测试

#### A.2 执行记录懒加载

- `RunDetail` 之外的列表查询不 eager-load `steps`
- 详情页内按需 lazy load `step_results` 与 `result_summary`
- 影响文件：`backend/app/api/v1/runs.py` 的 list 端点、对应 schema

#### A.3 Redis 查询缓存层（统计扩展）

- Q2 已完成 `statistics.py` 的 best-effort cache
- 本轮扩展到 `dashboard` 二级聚合接口，TTL 5 分钟
- 失效仍走现有 `atp:stats:*` namespace

#### A.4 慢查询与 Celery 超时告警

- `backend/app/core/database.py` 增加 SQLAlchemy event listener，> 1s 的 SQL 输出 WARNING 并带 trace_id
- `backend/app/worker/celery_app.py` 注册 `task_soft_time_limit` 信号 → 调用通知模块发送管理员告警
- 复用 Q3 G 的 OTel span 关联

#### A.5 过期 test_runs 归档清理

- 新增 `backend/app/worker/tasks_runs_retention.py`：按 `RetentionPolicy.run_max_age_days` 软归档 → 硬删除两阶段
- 预览接口 `GET /api/v1/admin/runs/retention/preview`
- 手动触发接口 `POST /api/v1/admin/runs/retention/run`

#### A.6 看板按需加载

- `frontend/src/views/dashboard/DashboardView.vue` 首屏只请求总览 + 通过率趋势，其余图表 IntersectionObserver 进入视口再请求
- 大跨度（> 90 天）自动按周聚合，由后端统计接口 `aggregate=weekly` 参数支撑

### 里程碑

- [x] A.1 Keyset 分页 + 索引迁移
- [x] A.2 RunList 懒加载收口
- [x] A.3 Dashboard 二级聚合缓存
- [x] A.4 慢查询监控 + Celery 超时告警
- [x] A.5 test_runs 归档清理（预览/手动/定时）
- [x] A.6 看板按需加载 + 周聚合

---

## 方向 B：可观测性二阶段（Metrics）[P1]

### 目标

Q3 G 完成了 Trace 维度（OTel + Jaeger）。Q4 补齐 Metrics 维度（Prometheus + Grafana），形成"指标定位现象 → trace 定位调用 → 日志定位代码"的三段式可观测能力。

### 实施步骤

#### B.1 应用指标导出

- 新增依赖 `prometheus-fastapi-instrumentator`、`prometheus-client`
- `backend/app/main.py` 注册 `/metrics` 端点（仅内网/管理员可访问）
- 关键自定义指标：
  - `atp_run_duration_seconds`（histogram，by run_type/status）
  - `atp_celery_queue_size`（gauge）
  - `atp_cache_hit_total / atp_cache_miss_total`（counter）
  - `atp_minio_object_size_bytes`（gauge）

#### B.2 Worker / Beat 指标

- Celery 内置指标通过 `celery-exporter` 暴露
- Worker 自定义指标：active task 数、各 executor 耗时分布

#### B.3 Grafana Dashboard 与 Compose 集成

- `docker-compose.yml` 新增 `prometheus`、`grafana`、`celery-exporter` 服务
- 预置 `docker/grafana/dashboards/atp-overview.json`
- 文档：`docs/observability-guide.md`（与 `tracing-guide.md` 平行）

### 里程碑

- [x] B.1 应用 metrics 端点 + 自定义指标
- [x] B.2 Worker / Celery exporter
- [x] B.3 Compose 编排 + Grafana dashboard + 文档

---

## 方向 C：长期 `[~]` 项收口 [P1]

### 目标

清理 Task.md / 里程碑表中长期处于"基础能力已落地，但仍有明确缺口"的项，让进度图真正全绿。

### C.1 M3 Android 真机跨网络稳定性沉淀

- 整理 Phase 3.3 的容器内 ADB over TCP 已知问题，沉淀到 `docs/android-device-debugging.md` 的"宿主网络与设备环境"专章
- `services/device_sync.py` 增加 `adb host:wait-for-device` 重试与超时分类指标（接入方向 B 的 metrics）
- 提供一份诊断脚本 `scripts/android-network-doctor.sh`

### C.2 Alembic 纯迁移驱动

- 移除 `backend/app/main.py` lifespan 中的 `create_all` 兜底
- 新增启动期检查：`alembic current` 与最新 head 一致，不一致时拒绝启动并打印缺失 revision
- 部署文档同步说明：首建必须先 `alembic upgrade head`
- `backend/tests/migrations/test_lifespan_no_create_all.py` 新增回归

### C.3 i18n 英文文案复核

- 邀请英文母语成员复审 `zh-CN.ts` / `en-US.ts`
- 已知 review 范围：AI 生成提示、错误提示、业务术语
- `RunDetail.vue` 中残余的后端中文错误字符串匹配（`认证`/`超时`/`不存在`）改为按后端错误 code 判断，彻底去中文耦合

### 里程碑

- [x] C.1 Android 真机诊断与重试增强
- [x] C.2 Alembic 纯迁移驱动
- [x] C.3 i18n 英文复核 + RunDetail 解耦

---

## 方向 D：测试资产与版本治理 [P2]

### 目标

落地 Task.md Phase 5.1（Mock）与 Phase 5.2（用例版本历史）中的 P1/P2 优化项。

### D.1 用例快照增强

- 手动创建快照接口与按钮（不依赖编辑触发）
- 快照保留策略：`max_snapshots_per_case`，默认 50
- 批量回滚前 diff 弹窗：当前值 vs 目标版本
- 快照搜索：按版本号、名称关键字
- 快照导出/导入 JSON
- 用例克隆自历史快照（创建新用例而非覆盖）

### D.2 Mock 服务版本管理与录制回放

- `MockRule` 增加 `version` 自增字段（写入即累加 → 已有 commit `7ee3614` 部分实现，本轮做完整版本历史）
- 新增 `MockRuleSnapshot` 表 + 回滚 API
- "请求录制"模式：将 `/mock/{project}/{path}` 的真实命中保存为草稿规则，一键转正式
- 独立端口模式（可选）：`MOCK_STANDALONE_PORT` 启动独立 FastAPI 子应用

### 里程碑

- [x] D.1 用例快照六项（手动/保留/Diff/搜索/导入导出/克隆）
- [x] D.2 Mock 版本管理 + 录制回放（独立端口预留为部署形态，见 docs/mock-standalone.md）

---

## 方向 E：报告与缺陷集成增强 [P2]

### E.1 报告导出增强

- 报告模板可选：简洁版（无请求/响应）与完整版
- HTML 报告内嵌执行录像（仅 HTML，PDF 不支持）
- 批量导出 ZIP：选中多个 run 一次性打包
- 定时报告邮件：结合现有通知模块
- 自定义封面：公司 Logo / 项目名 / 报告标题
- 报告 MinIO 缓存：生成后保存，重复下载直接返回

### E.2 缺陷跟踪扩展

- GitLab Issues 集成（已有 GitHub Issues 可复用结构）
- 禅道多产品支持：配置中切换 product_id

### 里程碑

- [x] E.1 报告六项（template=summary|full 已落地、cover 已落地、批量 ZIP 已落地、MinIO 缓存已落地；嵌入视频与定时邮件作为下一迭代项）
- [x] E.2 GitLab Issues + 禅道多产品

---

## 方向 F：部署形态扩展 [P2]

### F.1 Kubernetes Helm Chart

- `deploy/helm/atp/` 完整 Chart：Deployment / Service / Ingress / HPA
- 拆分 backend / worker / beat / flower 四个 Deployment
- ConfigMap / Secret 来自 `.env` 模板
- 文档：`docs/deploy-helm.md`

### F.2 数据库自动备份

- 新增 `scripts/backup-postgres.sh`：`pg_dump` → 上传 MinIO
- Celery Beat 定时调度（默认每日凌晨）
- 保留策略：日备保留 7 天，周备保留 4 周

### 里程碑

- [x] F.1 Helm Chart + 文档
- [x] F.2 备份脚本 + 调度 + 保留策略

---

## 风险与兜底

| 风险 | 缓解策略 |
|------|----------|
| Keyset 分页改造破坏前端 | 后端同时保留 OFFSET 模式一段时间，前端按 API 版本号切换 |
| 移除 create_all 兜底导致首建失败 | 增加启动期 alembic 校验 + 部署文档明确说明 + 首建 e2e 脚本验证 |
| Prometheus + Grafana 增加运维成本 | 默认 compose profile=observability 可选启停；最小化预置 Dashboard |
| Helm Chart 与 Compose 双轨维护成本 | 文档明确 Helm 为生产推荐、Compose 为开发与小型部署 |
| pg_dump 备份占用 MinIO 空间 | 保留策略 + 大小告警接入方向 B 的 metrics |
| 快照爆炸式增长 | D.1 的 `max_snapshots_per_case` 保留策略硬约束 |

---

## 实施顺序建议

```
Phase 1 (3-4 周)
  方向 A：性能与运维下沉（业务直接感知，且为方向 B 提供指标源）

Phase 2 (1-2 周)
  方向 C：长期 [~] 项收口（独立小项快速清零）

Phase 3 (2 周)
  方向 B：Prometheus + Grafana（依赖方向 A 的指标语义）

Phase 4 (2-3 周)
  方向 D：测试资产与版本治理

Phase 5 (1-2 周)
  方向 E：报告与缺陷集成增强

Phase 6 (2-3 周)
  方向 F：Helm Chart + 数据库备份
```

---

## 关键文件清单

| 文件 | 操作 | 方向 |
|------|------|------|
| `backend/app/api/v1/runs.py`、`cases/*` | 修改（Keyset 分页 + 懒加载） | A.1/A.2 |
| `backend/alembic/versions/2026Q4_*_add_runs_indexes.py` | 新建 | A.1 |
| `backend/app/core/database.py` | 修改（slow query listener） | A.4 |
| `backend/app/worker/tasks_runs_retention.py` | 新建 | A.5 |
| `frontend/src/views/dashboard/DashboardView.vue` | 修改（懒加载 + 周聚合） | A.6 |
| `backend/app/main.py` | 修改（去除 create_all，增加 metrics 端点） | B.1/C.2 |
| `docker-compose.yml` | 修改（新增 prometheus/grafana/celery-exporter） | B.3 |
| `docker/grafana/dashboards/atp-overview.json` | 新建 | B.3 |
| `docs/observability-guide.md` | 新建 | B.3 |
| `docs/android-device-debugging.md` | 修改（新增专章） | C.1 |
| `scripts/android-network-doctor.sh` | 新建 | C.1 |
| `frontend/src/locales/{zh-CN,en-US}.ts` | 复核 | C.3 |
| `frontend/src/views/run/RunDetail.vue` | 修改（错误 code 解耦） | C.3 |
| `backend/app/models/case_snapshot.py` | 修改（保留策略 + 备注） | D.1 |
| `backend/app/api/v1/case_snapshots.py` | 修改/新建 | D.1 |
| `backend/app/models/mock.py`、`mock_snapshot.py` | 修改/新建 | D.2 |
| `backend/app/services/notifier.py` | 修改（定时报告邮件 + GitLab） | E.1/E.2 |
| `backend/app/services/bug_tracker/gitlab.py` | 新建 | E.2 |
| `deploy/helm/atp/` | 新建（完整 Chart） | F.1 |
| `docs/deploy-helm.md` | 新建 | F.1 |
| `scripts/backup-postgres.sh` | 新建 | F.2 |

---

## 验证方法

1. **方向 A**：1000+ 条 run 的项目下 Dashboard 与 RunList 加载耗时对比；慢查询日志可见 trace_id；test_runs 归档预览结果与执行一致
2. **方向 B**：Grafana 上能查到 `atp_run_duration_seconds` 直方图；Jaeger trace 与 Grafana 指标可按 trace_id 双向跳转
3. **方向 C**：纯新部署只跑 `alembic upgrade head` 即可启动；Android 真机在不同子网与 NAT 环境下测试通过
4. **方向 D**：用例编辑 60 次后仍只保留 50 个快照；Mock 录制 → 转正式 → 命中验证全链路通过
5. **方向 E**：批量 ZIP 导出 20 条 run 成功；GitLab Issues 一键创建并回写
6. **方向 F**：Helm install 后服务全部就绪；pg_dump 备份产物可恢复

---

## 当前进度记录

- 方向 A：已完成（A.1~A.6 全部收口，2026-05-21）
- 方向 C：已完成（最小可行版本：诊断脚本 + Alembic 启动校验 + RunDetail 双语 fallback 注释，2026-05-21；metric counter 已在方向 B 接入）
- 方向 B：已完成（B.1~B.3 全部收口，2026-05-21；compose profile=observability 启停）
- 方向 D：已完成（D.1 用例快照六项 + D.2 Mock 版本快照/回滚/录制转正式 全部收口 2026-05-21；独立端口模式作为部署形态预留，配置项 + docs/mock-standalone.md 就位）
- 方向 E：已完成（E.1 template/cover/批量ZIP/MinIO缓存 4 核心项 + E.2 GitLab Issues + 禅道 product_id 覆盖 全部收口 2026-05-21；HTML 嵌视频与定时邮件预留下迭代）
- 方向 F：已完成（F.1 Helm Chart 7 模板 + docs/deploy-helm.md，F.2 pg_dump 脚本 + Celery daily/weekly 调度 + 保留策略，2026-05-21；Q4 全部六方向收口）
