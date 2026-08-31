# ATP Kubernetes Helm Chart 部署指南

## 发布前仓库校验

`make validate-deployment-readiness` 只验证仓库内的配置契约，不代表真实集群已经验收。
默认模式会把缺少 Docker/Compose、Helm、`.env` 或 POSIX shell 的项目明确打印为 `SKIP`，并在摘要显示跳过数量。
发布操作员应执行 `make validate-deployment-readiness ARGS=--strict`；严格模式会把任何环境依赖缺失转为失败。

> 状态：完整 Chart 已就位 (`deploy/helm/atp/`)，需运维侧准备外部 PostgreSQL / Redis / MinIO 与镜像仓库。
> 适用场景：生产部署、跨节点扩缩容、HPA 弹性伸缩。
> 对照 Compose（`docker-compose.yml`）：Compose 仍为开发与小型部署首选，Helm Chart 为生产推荐。

## 一、Chart 结构

```
deploy/helm/atp/
├── Chart.yaml
├── values.schema.json
├── values.yaml
└── templates/
    ├── _helpers.tpl
    ├── configmap.yaml
    ├── secret.yaml
    ├── migrate-job.yaml          # Helm pre-install/pre-upgrade Alembic 迁移
    ├── backend-deployment.yaml   # backend + Service
    ├── worker-deployment.yaml
    ├── performance-worker-deployment.yaml # 可选独立压测 worker
    ├── performance-worker-service.yaml    # 专用 worker metrics Service
    ├── beat-deployment.yaml      # 强制单副本 + Recreate 策略
    ├── flower-deployment.yaml    # flower + Service
    ├── ingress.yaml              # /api /ws /mock /metrics 路由
    └── hpa.yaml                  # backend / worker 自动扩缩容
```

## 二、前置条件

| 依赖 | 推荐 | 说明 |
|------|------|------|
| Kubernetes | ≥ 1.26 | autoscaling/v2 HPA |
| Ingress Controller | nginx-ingress | values.ingress.className |
| PostgreSQL 16 | 托管 RDS | values.secrets.POSTGRES_* |
| Redis 7 | 托管 ElastiCache | values.secrets.REDIS_* |
| MinIO | 集群 / S3 兼容 | values.secrets.MINIO_* |
| Prometheus Operator | kube-prometheus-stack 或等价实现 | 提供 ServiceMonitor CRD，并按 selector 选择 ATP ServiceMonitor |
| Metrics Server | 必装 | HPA 依赖 |
| 镜像仓库 | 内网 Harbor | values.image.repository |

## 三、镜像构建

```bash
# 后端
docker build -t registry.local/atp/backend:1.0.0 backend/
# Worker（含 Playwright Chromium + ADB + k6）
docker build -t registry.local/atp/worker:1.0.0 -f backend/Dockerfile.worker backend/
# 前端
docker build -t registry.local/atp/frontend:1.0.0 frontend/

docker push registry.local/atp/backend:1.0.0
docker push registry.local/atp/worker:1.0.0
docker push registry.local/atp/frontend:1.0.0
```

## 四、安装

```bash
# 1. 调整 values
cp deploy/helm/atp/values.yaml my-values.yaml
$EDITOR my-values.yaml

# 2. 先在测试 namespace 试运行
kubectl create namespace atp-staging
helm install atp deploy/helm/atp/ -n atp-staging -f my-values.yaml --dry-run

# 3. 正式安装
helm install atp deploy/helm/atp/ -n atp-staging -f my-values.yaml

# 4. 验证
kubectl get pods -n atp-staging
kubectl get hpa -n atp-staging
kubectl get ingress -n atp-staging
```

## 五、数据库迁移

Chart 内置 `pre-install` / `pre-upgrade` Job，会在安装或升级时先执行：

```bash
alembic upgrade head
```

迁移失败时 Helm 发布会停止，先查看迁移 Job Pod 日志，再修复配置或迁移脚本后重试。手工迁移、回滚与 drift
排查流程见 `docs/migrations.md`。

## 六、与 Compose 的差异

| 维度 | Compose | Helm |
|------|---------|------|
| 编排 | 单机 | K8s 多节点 |
| 扩缩容 | 手动 `--scale` | HPA 自动 |
| 配置管理 | `.env` 文件 | ConfigMap + Secret（建议接 ExternalSecrets / SOPS） |
| 外部依赖 | 内置 postgres/redis/minio | 默认外部托管 |
| 真机调试 | 推荐 | 不建议（K8s 集群通常无 ADB 真机；ADB_SCAN_ENABLED=false） |
| 可观测性 | profile=observability | 接入集群 Prometheus + Grafana（与 Q3/Q4 B.* 一致） |

## 七、Celery 队列与资源

默认 Linux worker 监听 `default,ios,ai,maintenance,performance` 五类队列。Android 任务由 Windows Android Worker 监听 `android,mobile_special`；生产使用 Windows Android Worker 时，Linux Worker 必须排除这两个队列，并按队列拆分 worker 副本：

- `default`：普通用例、套件、计划执行。
- `android`：普通 Android 用例，由 Windows Android Worker 在本机调用 ADB。
- `mobile_special`：Android 专项与 ADB 扫描，由 Windows Android Worker 消费。
- `ai`：AI 自愈诊断与反馈聚合。
- `maintenance`：清理、备份、告警。
- `performance`：HTTP 压测任务，worker 镜像内置 k6，建议低并发独立 worker，避免挤占功能测试资源。

详细队列规划见 `docs/celery-queues.md`。

使用 Windows Android Worker 时，可直接套用
`deploy/helm/atp/values-android-worker.example.yaml`：它将
`ADB_SCAN_ENABLED=true`、`ADB_SCAN_MODE=worker` 和 `ANDROID_WORKER_QUEUE=mobile_special`
注入 Backend/Beat，同时让 Linux Worker 继续只监听
`default,ios,ai,maintenance,performance`。该 overlay 默认使用外部 Secret，不会把
数据库、Redis、MinIO 或加密密钥写入仓库。Windows Agent 仍需使用独立的
`config/startup-profiles/android-agent.env`。

Chart 已为 backend / worker / beat / flower 提供 baseline `resources.requests/limits`。上线前应结合实际用例规模、
浏览器并发、Android 真机数量、LLM 调用频率与压测 VUs / duration 调优。

独立 performance worker 示例：

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
  metricsPort: 9092
  autoIdentity: false
  nodeEnabled: true
  nodeId: worker-a
  nodeName: Worker A
  nodeQueue: performance.node-a
  nodeMaxVus: 100
  nodeMaxConcurrency: 2
  nodeEgressAllowlist: api.example.test
  networkPolicy:
    enabled: true
    egress:
      - to:
          - ipBlock: {cidr: 10.20.0.0/16}
        ports:
          - {protocol: TCP, port: 443}
  resources:
    requests: {cpu: 1000m, memory: 1Gi}
    limits: {cpu: 2000m, memory: 2Gi}
service:
  performanceWorker:
    type: ClusterIP
    port: 9092
hpa:
  performanceWorker:
    enabled: true
    minReplicas: 1
    maxReplicas: 3
    targetCPUUtilizationPercentage: 70
```

开启后，默认 worker 不再消费 `performance` 队列，压测任务由 `performance-worker` Deployment 单独承载。专用
`performance-worker` 必须同时消费共享 `performance` 队列和节点队列；`performanceWorker.queues` 应包含与 `nodeQueue` 完全一致的队列名，Chart
启动命令会自动补上共享队列。建议同时配置
`PERFORMANCE_TARGET_ALLOWLIST`、`PERFORMANCE_MAX_VUS`、`PERFORMANCE_MAX_DURATION_SECONDS` 和节点级
`nodeEgressAllowlist`；启用 NetworkPolicy 时还必须显式配置 DNS、数据库、Redis、MinIO 与目标服务出口。
如果需要用多个副本作为独立性能节点，将 `autoIdentity` 设为 `true`；每个 Pod 会用自身 hostname 生成唯一节点和
`performance.<pod>` 队列，避免多个副本共享队列后误消费其他节点的定向任务。固定节点身份时保持
`autoIdentity=false`，并为每个 Helm release 使用 `replicas: 1`、不同的 `nodeId` 和 `nodeQueue`。
部署完成后的真实 Worker、TLS、allowlist、取消和资源采样验收命令见
[`docs/performance-environment-acceptance.md`](performance-environment-acceptance.md)。

### P4 真实 Kubernetes 最小验收 overlay

`deploy/helm/atp/values-performance-acceptance.example.yaml` 是与上述脚本契约配套的最小真实集群
配置：2 个自动身份性能 Worker、跨节点反亲和、明确的 CPU/内存 requests/limits、普通 Worker 排除
`performance` 队列、Backend/性能 Worker 的 ServiceMonitor，以及外部 Secret 引用。它不安装 PostgreSQL、Redis、
MinIO 或 Prometheus，也不包含真实凭据；source MinIO 由 `secret.existingName` 提供，target MinIO
只在 [`deploy/performance-acceptance/minio-dr.env.example`](../deploy/performance-acceptance/minio-dr.env.example)
中作为独立 DR 验收端点配置。

复制 overlay 后先替换镜像 tag、实际目标/Prometheus 主机、Prometheus selector label 和 Secret 名称，
再按 `performance-environment-acceptance.md` 执行 `helm lint`、`helm template`、部署、容量预检、
ServiceMonitor target 查询和跨端点 MinIO smoke。Chart 渲染或契约测试通过不代表真实集群、监控或
灾备验收通过。

## 八、升级与回滚

```bash
helm upgrade atp deploy/helm/atp/ -n atp-staging -f my-values.yaml
helm rollback atp <REVISION> -n atp-staging
```

## 九、备份恢复

Helm values 默认启用 `DB_BACKUP_ENABLED=true`，由 Celery beat 调度 PostgreSQL 备份任务，备份对象写入 MinIO 的 `pg-backups/` 前缀。

恢复演练与生产恢复步骤见 `docs/disaster-recovery.md`。恢复脚本 `scripts/restore-postgres.sh` 必须显式传入 `--i-know-this-overwrites`，避免误覆盖数据库。

### MinIO 生命周期（显式启用）

Chart 不负责安装 MinIO，只在 `storageLifecycle.enabled=true` 时通过 Helm hook
调用 `app.ops_minio_lifecycle`。该命令默认只清理未完成的 multipart upload；它会保留
不是 `atp-managed-` 命名空间的既有生命周期规则，并只替换 ATP 自己管理的规则。

如需为临时对象配置过期规则，必须使用非空的相对前缀，并确认该前缀不包含仍被数据库引用的截图、报告、APK、脚本或
`pg-backups/` 对象：

```yaml
storageLifecycle:
  enabled: true
  abortIncompleteMultipartDays: 1
  expirationRules:
    - id: scratch-objects
      prefix: tmp/
      days: 7
```

该 hook 使用 ATP backend 镜像和外部 Secret 中的 `MINIO_*` 配置；默认关闭，不会因普通
API/Worker 启动而改变 bucket 策略。Docker Compose 可用
`docker compose --profile storage-lifecycle run --rm minio-lifecycle` 显式执行同一套合并逻辑。

## 十、生产 checklist

生产 values 应使用外部 Secret，并在 Prometheus Operator 集群中开启
`metrics.serviceMonitor.enabled`。开启 `performanceWorker.enabled` 后，Chart 会同时
创建专用 metrics Service 和 ServiceMonitor，采集性能 Worker 的 `/metrics`；Helm chart 会在 `ingress.tls.enabled=true` 时
自动加上 HTTP→HTTPS 重定向；`secret.create=false` + `secret.existingName` 可绑定
ExternalSecrets/SOPS 创建的 Secret。`make validate-deployment-readiness` 只验证
仓库内的配置契约，不会把真实集群状态误判为已验收。
Windows 无 Git Bash、WSL 或其他 POSIX shell 时，校验器会跳过 shell 语法检查；
发布操作员应使用 `python scripts/validate-deployment-readiness.py --require-helm
--require-shell`，确保发布机具备完整校验能力。

- [ ] PostgreSQL / Redis / MinIO 数据已备份并验证恢复（参见 `docs/disaster-recovery.md`）
- [ ] MinIO lifecycle 规则已由目标环境管理员确认；若启用 `storageLifecycle`，已验证规则前缀不删除数据库仍引用的对象
- [ ] values.secrets 已通过 ExternalSecrets / SOPS 注入，未明文提交
- [ ] Ingress TLS 已配置，HTTP 自动重定向 HTTPS
- [ ] Prometheus 已通过 ServiceMonitor 抓取 backend 与（启用时）performance-worker `/metrics`
- [ ] Grafana 告警模板已按环境导入（参见 `deploy/grafana/alerts/atp-alerts.yaml`）
- [ ] Beat 单副本 + Recreate 已确认（防重复触发 cron）
- [ ] alembic migration 已先于流量切入
- [ ] 资源 requests/limits 已根据实际负载调优
