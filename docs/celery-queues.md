# Celery 队列规划

ATP 默认 worker 监听全部队列，适合本地开发和小型部署：

```bash
CELERY_QUEUES=default,mobile_special,ai,maintenance,performance
celery -A app.worker.celery_app worker --loglevel=info --pool=solo -Q "$CELERY_QUEUES"
```

生产环境可以按队列拆分 worker，避免长任务、外部 LLM 调用、维护任务或压测任务挤占普通用例执行。

## 队列分工

| 队列 | 任务 | 说明 |
|------|------|------|
| `default` | `run_test_case`、`run_test_suite`、`run_test_plan`、`check_cron_plans` | 高频主链路执行 |
| `mobile_special` | Android 专项任务、ADB 扫描、专项清理 | 受真机和网络资源约束，建议独立副本 |
| `ai` | AI 自愈诊断、反馈聚合 | 依赖外部 LLM，便于限流和降级 |
| `maintenance` | 文件清理、运行记录清理、存储告警、Dashboard 告警、PostgreSQL 备份 | 后台维护任务，允许低优先级运行 |
| `performance` | `run_performance_test` | HTTP 压测任务，默认用于 k6/Locust 类执行，必须与功能测试 worker 资源隔离 |

路由配置位于 `backend/app/worker/celery_app.py` 的 `task_routes`。

## Docker Compose

默认 `worker` 服务监听全部队列。只跑普通执行队列：

```bash
CELERY_QUEUES=default docker compose up -d worker
```

需要独立扩展 Android 专项时，可以复制 `worker` 服务为新服务，改环境变量：

```yaml
environment:
  - CELERY_QUEUES=mobile_special
```

需要独立执行 HTTP 压测时，同样复制 `worker` 服务并只监听 performance 队列。`backend/Dockerfile.worker`
已从 `grafana/k6` 镜像复制 k6 二进制，压测 worker 不需要额外安装 k6：

```yaml
environment:
  - CELERY_QUEUES=performance
```

## Helm

默认值在 `deploy/helm/atp/values.yaml`：

```yaml
config:
  CELERY_QUEUES: default,mobile_special,ai,maintenance,performance
performanceWorker:
  enabled: false
  queues: performance
```

生产隔离建议：

- 普通执行 worker：`CELERY_QUEUES=default`，按业务吞吐扩容。
- Android worker：`CELERY_QUEUES=mobile_special`，按可用真机数量扩容。
- AI worker：`CELERY_QUEUES=ai`，按 LLM 限额和成本控制副本。
- 维护 worker：`CELERY_QUEUES=maintenance`，少量副本即可。
- 压测 worker：`CELERY_QUEUES=performance`，低并发运行，配独立 CPU/内存限制与网络出口策略。

Chart 内置可选 `performanceWorker` Deployment。生产启用示例：

```yaml
worker:
  queues: default,mobile_special,ai,maintenance
config:
  CELERY_QUEUES: default,mobile_special,ai,maintenance
performanceWorker:
  enabled: true
  replicas: 1
  queues: performance
  concurrency: "1"
  resources:
    requests: {cpu: 1000m, memory: 1Gi}
    limits: {cpu: 2000m, memory: 2Gi}
```

如需更细粒度隔离 Android、AI 或维护任务，可继续使用多份 values 或平台侧 overlay 渲染多个 worker Deployment，
每份只覆盖队列、副本数和资源限制。
