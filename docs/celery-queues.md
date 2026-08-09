# Celery 队列规划

ATP 默认 worker 监听全部队列，适合本地开发和小型部署：

```bash
CELERY_QUEUES=default,mobile_special,ios,ai,maintenance,performance
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
| `performance` | `run_performance_test`、`check_performance_schedules`、性能节点心跳 | 共享的压测控制/调度队列；专用节点 Worker 还必须同时消费自己的 `performance.<node>` 队列 |

路由配置位于 `backend/app/worker/celery_app.py` 的 `task_routes`。
状态流转、重试、超时和恢复策略见 [Worker State, Retry, Timeout, and Recovery Policy](./worker-lifecycle.md)。

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
  CELERY_QUEUES: default,mobile_special,ios,ai,maintenance,performance
performanceWorker:
  enabled: false
  queues: performance
  nodeId: ""
  nodeQueue: performance
```

生产隔离建议：

- 普通执行 worker：`CELERY_QUEUES=default`，按业务吞吐扩容。
- Android worker：`CELERY_QUEUES=mobile_special`，按可用真机数量扩容。
- AI worker：`CELERY_QUEUES=ai`，按 LLM 限额和成本控制副本。
- 维护 worker：`CELERY_QUEUES=maintenance`，少量副本即可。
- 压测 worker：`CELERY_QUEUES=performance` 或 `performance.<node>,performance`，低并发运行，配独立 CPU/内存限制与网络出口策略。

Chart 内置可选 `performanceWorker` Deployment。生产启用示例：

```yaml
worker:
  queues: default,mobile_special,ai,maintenance
config:
  CELERY_QUEUES: default,mobile_special,ai,maintenance
performanceWorker:
  enabled: true
  replicas: 1
  queues: performance.node-a,performance
  concurrency: "1"
  nodeEnabled: true
  nodeId: worker-a
  nodeName: Worker A
  nodeQueue: performance.node-a
  nodeMaxVus: 100
  nodeMaxConcurrency: 2
  nodeEgressAllowlist: api.example.test
  resources:
    requests: {cpu: 1000m, memory: 1Gi}
    limits: {cpu: 2000m, memory: 2Gi}
```

如需更细粒度隔离 Android、AI 或维护任务，可继续使用多份 values 或平台侧 overlay 渲染多个 worker Deployment，
每份只覆盖队列、副本数和资源限制。

使用专用压测节点时，`performanceWorker.queues` 必须同时包含与 `nodeQueue` 完全一致的队列名和共享的 `performance` 队列；Chart
启动命令会自动补上共享队列。worker 启动后会主动注册 `nodeId` 并持续刷新心跳。`nodeEgressAllowlist` 是应用层目标域名限制，Kubernetes 原生出口隔离请通过
`performanceWorker.networkPolicy.enabled/egress` 配置，并显式放行 DNS、数据库、Redis、MinIO 和目标服务。
发布后的真实队列、节点心跳和 Worker 镜像验收可使用
[`docs/performance-environment-acceptance.md`](performance-environment-acceptance.md) 中的命令。
