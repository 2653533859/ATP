# Celery 队列规划

ATP 默认 worker 监听全部队列，适合本地开发和小型部署：

```bash
CELERY_QUEUES=default,android,mobile_special,ios,ai,maintenance,performance
celery -A app.worker.celery_app worker --loglevel=info --pool=solo -Q "$CELERY_QUEUES"
```

生产环境可以按队列拆分 worker，避免长任务、外部 LLM 调用、维护任务或压测任务挤占普通用例执行。
套件和计划的入口会根据内容选择队列：纯设备类型的执行直接进入对应专用队列，混合内容留在
`default` 队列编排，并将设备子用例转投到对应队列。

## 队列分工

| 队列 | 任务 | 说明 |
|------|------|------|
| `default` | 默认配置下的协议/Web 用例、混合 `run_test_suite`/`run_test_plan`、`check_cron_plans` | 高频主链路与混合执行编排 |
| `web.<deployment>` | 设置 `WEB_EXECUTION_QUEUE` 后的 Web 用例及纯 Web 套件/计划 | 共享 Broker 时隔离不同部署或不同版本的浏览器 Worker |
| `protocol.<deployment>` | 设置 `PROTOCOL_EXECUTION_QUEUE` 后的 API、GraphQL、WebSocket、gRPC 用例及纯协议套件/计划 | 共享 Broker 时隔离不同部署或不同版本的协议执行器 |
| `android` | Android 用例、纯 Android 套件/计划、ADB 扫描、Worker 心跳和设备操作 | 由 Windows Android Worker 消费，在本机调用 `adb`；控制任务与长时专项执行隔离 |
| `ios` | iOS 用例，以及只包含 iOS 用例的套件/计划 | 由 macOS/iOS Worker 消费，在本机连接 Appium/XCUITest |
| `mobile_special` | `run_mobile_special_task` | 只承载需要真机的 Android 专项执行，避免控制面扫描被长任务或历史消息阻塞 |
| `ai` | AI 自愈诊断、反馈聚合 | 依赖外部 LLM，便于限流和降级 |
| `maintenance` | 通用清理/告警/备份、Android 周期扫描派发、专项调度检查、过期专项运行与设备租约回收 | 后台维护任务；周期扫描先检查 TTL Worker 注册中心，离线时不向 `android` 投递 |
| `performance` | `run_performance_test`、`check_performance_schedules`、性能节点心跳 | 共享的压测控制/调度队列；专用节点 Worker 还必须同时消费自己的 `performance.<node>` 队列 |

路由配置位于 `backend/app/worker/celery_app.py` 的 `task_routes`。
状态流转、重试、超时和恢复策略见 [Worker State, Retry, Timeout, and Recovery Policy](./worker-lifecycle.md)。

### 套件与计划的路由边界

- 套件内所有用例都是同一设备类型时，套件任务进入该设备队列并在本地 Worker 内联执行。
- 计划内所有套件都只包含同一设备类型时，计划任务进入该设备队列；只要包含混合套件或普通
  Web/API 用例，计划任务就留在 `default` 队列。
- 混合套件或混合计划由 `default` Worker 编排，Android/iOS 子用例通过显式队列投递并等待
  结果。生产环境不要让普通 Linux Worker 消费 `android`/`ios` 队列。

## Docker Compose

公网部署使用 Windows Android Worker 时，Linux 普通 Worker 必须排除 `android,mobile_special`，Windows 主机按 [`android-windows-worker.md`](android-windows-worker.md) 运行 `android,mobile_special`。整个共享 Redis 只能运行一个当前版本 Beat；迁移后必须停止旧部署的 Beat，以及仍消费当前 `default`、`maintenance` 或 `performance` 队列的旧 Worker。
Windows 本地启动也要区分两种模式：`local-all` 的普通 Worker 可以监听全部队列，适合 Backend、基础设施和 ADB 都在同一台机器；`android-agent` 只启动专用 Android Worker，适合远程 Backend/Redis/MinIO；`performance-agent` 只启动专用性能队列。普通 Worker 的进程识别会排除 `android-win-*` 和 `performance-win-*`，避免把专用 Worker 误当成普通 Worker 管理；Android 模式仍会按队列配置双向阻止 `android`/`mobile_special` 重叠消费。

默认 `worker` 服务监听全部队列。只跑普通执行队列：

```bash
CELERY_QUEUES=default docker compose up -d worker
```

需要独立扩展 Android 专项时，可以复制 `worker` 服务为新服务，改环境变量：

```yaml
environment:
  - CELERY_QUEUES=android,mobile_special
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
  CELERY_QUEUES: default,ios,ai,maintenance,performance
  WEB_EXECUTION_QUEUE: default
  PROTOCOL_EXECUTION_QUEUE: default
performanceWorker:
  enabled: false
  queues: performance
  nodeId: ""
  nodeQueue: performance
```

生产隔离建议：

- 普通执行 worker：`CELERY_QUEUES=default`，按业务吞吐扩容。
- 共享 Broker 的 Web worker：Backend 设置 `WEB_EXECUTION_QUEUE=web.<deployment>`，对应 Worker 的
  `CELERY_QUEUES` 必须包含同名队列；旧部署不要监听该队列。
- 共享 Broker 的协议 worker：Backend 设置 `PROTOCOL_EXECUTION_QUEUE=protocol.<deployment>`，对应 Worker 的
  `CELERY_QUEUES` 必须包含同名队列；API、GraphQL、WebSocket、gRPC 会统一路由到该队列。
- Windows Android worker：`CELERY_QUEUES=android,mobile_special`，按可用真机数量扩容，详见 [`android-windows-worker.md`](android-windows-worker.md)。
- AI worker：`CELERY_QUEUES=ai`，按 LLM 限额和成本控制副本。
- 维护 worker：`CELERY_QUEUES=maintenance`，少量副本即可。
- 压测 worker：`CELERY_QUEUES=performance` 或 `performance.<node>,performance`，低并发运行，配独立 CPU/内存限制与网络出口策略。

Chart 内置可选 `performanceWorker` Deployment。生产启用示例：

```yaml
worker:
  queues: default,ios,ai,maintenance
config:
  CELERY_QUEUES: default,ios,ai,maintenance
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

使用专用压测节点时，`performanceWorker.queues` 必须同时包含与 `nodeQueue` 完全一致的队列名和共享的 `performance` 队列；Windows
`windows-local.ps1` 在检测到 `PERFORMANCE_NODE_ENABLED=true` 且有节点 ID 时也会自动补齐这两个队列。队列名称允许字母、数字、点号、下划线和短横线；Chart
启动命令会自动补上共享队列。worker 启动后会主动注册 `nodeId` 并持续刷新心跳。`nodeEgressAllowlist` 是应用层目标域名限制，Kubernetes 原生出口隔离请通过
`performanceWorker.networkPolicy.enabled/egress` 配置，并显式放行 DNS、数据库、Redis、MinIO 和目标服务。
发布后的真实队列、节点心跳和 Worker 镜像验收可使用
[`docs/performance-environment-acceptance.md`](performance-environment-acceptance.md) 中的命令。
