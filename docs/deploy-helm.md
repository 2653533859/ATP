# ATP Kubernetes Helm Chart 部署指南

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

默认 worker 监听 `default,mobile_special,ai,maintenance,performance` 五类队列。生产建议按队列拆分 worker 副本：

- `default`：普通用例、套件、计划执行。
- `mobile_special`：Android 专项与 ADB 扫描。
- `ai`：AI 自愈诊断与反馈聚合。
- `maintenance`：清理、备份、告警。
- `performance`：HTTP 压测任务，worker 镜像内置 k6，建议低并发独立 worker，避免挤占功能测试资源。

详细队列规划见 `docs/celery-queues.md`。

Chart 已为 backend / worker / beat / flower 提供 baseline `resources.requests/limits`。上线前应结合实际用例规模、
浏览器并发、Android 真机数量、LLM 调用频率与压测 VUs / duration 调优。

独立 performance worker 示例：

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
  metricsPort: 9092
  resources:
    requests: {cpu: 1000m, memory: 1Gi}
    limits: {cpu: 2000m, memory: 2Gi}
hpa:
  performanceWorker:
    enabled: true
    minReplicas: 1
    maxReplicas: 3
    targetCPUUtilizationPercentage: 70
```

开启后，默认 worker 不再消费 `performance` 队列，压测任务由 `performance-worker` Deployment 单独承载。建议同时配置
`PERFORMANCE_TARGET_ALLOWLIST`、`PERFORMANCE_MAX_VUS` 与 `PERFORMANCE_MAX_DURATION_SECONDS`，并通过网络策略限制压测出口。

## 八、升级与回滚

```bash
helm upgrade atp deploy/helm/atp/ -n atp-staging -f my-values.yaml
helm rollback atp <REVISION> -n atp-staging
```

## 九、备份恢复

Helm values 默认启用 `DB_BACKUP_ENABLED=true`，由 Celery beat 调度 PostgreSQL 备份任务，备份对象写入 MinIO 的 `pg-backups/` 前缀。

恢复演练与生产恢复步骤见 `docs/disaster-recovery.md`。恢复脚本 `scripts/restore-postgres.sh` 必须显式传入 `--i-know-this-overwrites`，避免误覆盖数据库。

## 十、生产 checklist

生产 values 应使用外部 Secret，并在 Prometheus Operator 集群中开启
`metrics.serviceMonitor.enabled`。Helm chart 会在 `ingress.tls.enabled=true` 时
自动加上 HTTP→HTTPS 重定向；`secret.create=false` + `secret.existingName` 可绑定
ExternalSecrets/SOPS 创建的 Secret。`make validate-deployment-readiness` 只验证
仓库内的配置契约，不会把真实集群状态误判为已验收。

- [ ] PostgreSQL / Redis / MinIO 数据已备份并验证恢复（参见 `docs/disaster-recovery.md`）
- [ ] values.secrets 已通过 ExternalSecrets / SOPS 注入，未明文提交
- [ ] Ingress TLS 已配置，HTTP 自动重定向 HTTPS
- [ ] Prometheus 已 ServiceMonitor 抓取 backend `/metrics`
- [ ] Grafana 告警模板已按环境导入（参见 `deploy/grafana/alerts/atp-alerts.yaml`）
- [ ] Beat 单副本 + Recreate 已确认（防重复触发 cron）
- [ ] alembic migration 已先于流量切入
- [ ] 资源 requests/limits 已根据实际负载调优
