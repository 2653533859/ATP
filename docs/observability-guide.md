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

启动后 Grafana 自动加载 Prometheus 数据源与 `ATP Overview` 仪表盘（来自 `docker/grafana/dashboards/atp-overview.json`）。

## 三、自定义业务指标

封装位于 `backend/app/core/metrics.py`，所有 Counter / Histogram 都通过 helper 函数构造，缺 `prometheus_client` 依赖时退化为 no-op，不会破坏本地测试。

| 指标名 | 类型 | label | 说明 |
|--------|------|-------|------|
| `atp_stats_cache_total` | Counter | `result=hit/miss/error` | 统计接口缓存命中分布 |
| `atp_slow_queries_total` | Counter | — | 超过 `SLOW_QUERY_THRESHOLD_MS` 的 SQL 数（与 A.4 日志同源） |
| `atp_celery_timeouts_total` | Counter | `kind=soft/hard` | Celery 软/硬超时次数 |
| `atp_run_retention_deleted_total` | Counter | `model` | 归档清理删除的 run 数 |

FastAPI 请求级指标由 `prometheus-fastapi-instrumentator` 自动注入：

- `http_requests_total{handler,method,status}`
- `http_request_duration_seconds_bucket{handler,method,le}`（用于 `histogram_quantile`）
- `http_request_size_bytes` / `http_response_size_bytes`

Celery 指标由 `celery-exporter` 订阅 Redis broker 后导出（无需 worker 代码改动）：

- `celery_queue_length{queue_name}`
- `celery_task_runtime_seconds{...}`
- `celery_task_succeeded_total / failed_total / retried_total`

## 四、Grafana 仪表盘

预置 `ATP Overview` 面板含 6 个图：

1. HTTP 请求 RPS（按 handler 分组）
2. HTTP P95 延迟（5min 滑窗）
3. 统计接口缓存命中率（5min）
4. 最近 1h 慢查询计数
5. Celery soft/hard 超时速率
6. Celery 队列长度（按 queue_name）

可在 Grafana UI 中复制为自定义看板。

## 五、添加新指标的范式

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

## 六、与 Jaeger（链路追踪）的关系

| 维度 | 工具 | 解决的问题 |
|------|------|------------|
| Trace | Jaeger（OpenTelemetry） | 单次请求/任务的调用链与每段耗时 |
| Metric | Prometheus + Grafana | 时间序列上的整体趋势与告警 |
| Log | Stdout（带 trace_id） | 单条日志事件细节 |

三者通过 `trace_id`（HTTP header / log field / OTel span attribute `app.trace_id`）串联。

## 七、生产部署建议

- Prometheus 存储默认 `tsdb` 路径不挂卷，重启清空 — 长期保留请挂 PV 或接入远端存储
- Grafana 已挂 `grafana_data` 卷保留仪表盘与配置
- Celery Exporter 仅订阅事件，无持久化需求
- 生产应启用 Grafana 反向代理 + HTTPS + RBAC，不直接暴露 3000 端口
