# ATP 可观测性指引（Prometheus + Grafana）

本文档说明 ATP 平台的 metrics 维度可观测性组件如何启动、查询与扩展。指标维度（Prometheus + Grafana）与链路维度（OpenTelemetry + Jaeger）正交互补 — trace 维度参见 `docs/tracing-guide.md`。

## 一、启停

可观测性栈默认不启动，使用 Compose profile `observability` 显式拉起：

```bash
# 启动 prometheus + grafana + celery-exporter
docker compose --profile observability up -d prometheus grafana celery-exporter

# 停止
docker compose --profile observability down
```

仅启核心栈时，可观测性服务不消耗资源：

```bash
docker compose up -d           # 不含 prometheus/grafana/celery-exporter
```

## 二、访问入口

| 服务 | 地址 | 凭证 |
|------|------|------|
| Grafana | http://localhost:3000 | admin / admin（首次登录改密） |
| Prometheus | http://localhost:9090 | — |
| Celery Exporter | http://localhost:9808/metrics | — |
| Backend `/metrics` | http://localhost:8000/metrics | — |
| Worker `/metrics` | http://localhost:9091/metrics（容器内）| — |

启动后 Grafana 自动加载 Prometheus 数据源与 `ATP Overview` 仪表盘（来自 `docker/grafana/dashboards/atp-overview.json`）。

> **Worker `/metrics`**：Celery worker 是独立进程，通过 `prometheus_client.start_http_server(WORKER_METRICS_PORT)` 在每个子进程初始化时尝试启动。多 worker 子进程共享同一物理端口，首个子进程成功绑定后其余 OSError 静默。可通过 `WORKER_METRICS_PORT=0` 关闭。Prometheus 抓取目标 `atp-worker` 已在 `docker/prometheus.yml` 配置。

## 三、自定义业务指标

封装位于 `backend/app/core/metrics.py`，所有 Counter / Histogram 都通过 helper 函数构造，缺 `prometheus_client` 依赖时退化为 no-op，不会破坏本地测试。

| 指标名 | 类型 | label | 说明 |
|--------|------|-------|------|
| `atp_stats_cache_total` | Counter | `result=hit/miss/error` | 统计接口缓存命中分布 |
| `atp_slow_queries_total` | Counter | — | 超过 `SLOW_QUERY_THRESHOLD_MS` 的 SQL 数（与 A.4 日志同源） |
| `atp_celery_timeouts_total` | Counter | `kind=soft/hard` | Celery 软/硬超时次数 |
| `atp_run_retention_deleted_total` | Counter | `model` | 归档清理删除的 run 数 |
| `atp_adb_reconnect_total` | Counter | `result=success/failure/not_tcp_serial/adb_not_found` | ADB ensure_reachable 调用结果分布（Q7 A.3.2） |
| `atp_adb_heartbeat_lost_total` | Counter | `executor=android/perf/stability/fluency` | 心跳监控判定设备失联次数 |
| `atp_adb_ensure_reachable_duration_seconds` | Histogram | — | 可达性探测延迟分布（含 reconnect 时间） |

FastAPI 请求级指标由 `prometheus-fastapi-instrumentator` 自动注入：

- `http_requests_total{handler,method,status}`
- `http_request_duration_seconds_bucket{handler,method,le}`（用于 `histogram_quantile`）
- `http_request_size_bytes` / `http_response_size_bytes`

Celery 指标由 `celery-exporter` 订阅 Redis broker 后导出（无需 worker 代码改动）：

- `celery_queue_length{queue_name}`
- `celery_task_runtime_seconds{...}`
- `celery_task_succeeded_total / failed_total / retried_total`

## 四、Grafana 仪表盘

预置 `ATP Overview` 面板含 10 个图：

1. HTTP 请求 RPS（按 handler 分组）
2. HTTP P95 延迟（5min 滑窗）
3. 统计接口缓存命中率（5min）
4. 最近 1h 慢查询计数
5. Celery soft/hard 超时速率
6. Celery 队列长度（按 queue_name）
7. **ADB reconnect 调用结果分布（按 result label 5min rate）**
8. **ADB heartbeat 失联事件（按 executor 1h 增量）**
9. **ADB ensure_reachable 延迟 P50/P95/P99**
10. **慢查询速率（超过 `SLOW_QUERY_THRESHOLD_MS` 的 SQL 5min rate）**

可在 Grafana UI 中复制为自定义看板。

### 慢查询定位

慢查询计数来自 `backend/app/core/slow_query.py`，超过 `SLOW_QUERY_THRESHOLD_MS` 时会同时：

- 写入结构化 warning 日志，包含 `trace_id`、SQL 前 500 字符和参数摘要。
- 增加 Prometheus 指标 `atp_slow_queries_total`。
- 给当前 OTel span 标记 `atp.slow_query=true` 与 `atp.slow_query_ms`。

排查时先看 Grafana 的 `Slow queries` 和 `Slow query rate`，确认时间窗口；再用同一时间段在日志中按
`slow_query` 或 `trace_id` 检索，必要时跳转 Jaeger 查看对应请求链路。

## 五、Grafana 告警模板

告警模板位于 `deploy/grafana/alerts/atp-alerts.yaml`，使用 Grafana unified alerting provisioning 格式，默认引用 Prometheus datasource UID `prometheus`。

模板预置 7 类告警：

1. API 5xx 错误率超过 5%
2. Celery 队列堆积超过 100
3. PostgreSQL 连接数超过 `max_connections` 的 80%
4. Celery 任务失败率大于 0
5. ATP/Celery 超时开始增长
6. **ADB reconnect 失败率 > 30%（且 5min 总尝试 > 5）**
7. **ADB heartbeat 1h 内任一 executor 失联 > 3 次**

Compose 本地栈可将该文件挂载到 Grafana 的 `/etc/grafana/provisioning/alerting/`；生产环境建议由平台侧统一管理 contact point、notification policy 与 mute timing。

## 六、添加新指标的范式

```python
# backend/app/core/metrics.py
NEW_METRIC = _counter("atp_xxx_total", "what this counts", ("label_name",))
```

业务代码中：

```python
from app.core.metrics import NEW_METRIC
try:
    NEW_METRIC.labels(label_name="value").inc()
except Exception:
    pass  # 任何 metric 异常都不应破坏业务逻辑
```

## 七、与 Jaeger（链路追踪）的关系

| 维度 | 工具 | 解决的问题 |
|------|------|------------|
| Trace | Jaeger（OpenTelemetry） | 单次请求/任务的调用链与每段耗时 |
| Metric | Prometheus + Grafana | 时间序列上的整体趋势与告警 |
| Log | Stdout（带 trace_id） | 单条日志事件细节 |

三者通过 `trace_id`（HTTP header / log field / OTel span attribute `app.trace_id`）串联。

## 八、生产部署建议

- Prometheus 存储默认 `tsdb` 路径不挂卷，重启清空 — 长期保留请挂 PV 或接入远端存储
- Grafana 已挂 `grafana_data` 卷保留仪表盘与配置
- Celery Exporter 仅订阅事件，无持久化需求
- 生产应启用 Grafana 反向代理 + HTTPS + RBAC，不直接暴露 3000 端口
