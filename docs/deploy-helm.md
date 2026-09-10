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

迁移 Job 是 Helm Hook，会先于普通 ConfigMap 创建。为避免首装时出现资源顺序竞态，Job 将
`.Values.config` 中的非敏感配置直接以内联环境变量注入，并只从已存在的 Secret 读取敏感配置；业务
Deployment 仍通过 ConfigMap + Secret 读取同一套配置。

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
- `android`：Android 用例、ADB 扫描、Worker 心跳和设备操作，由 Windows Android Worker 消费。
- `mobile_special`：仅承载 Android 专项执行；专项调度、清理和租约回收由 Linux `maintenance` Worker 消费。
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

### 单节点 K3s 开发/联调 overlay

`deploy/helm/atp/values-performance-single-node.example.yaml` 专用于当前单节点 K3s 的开发/联调：它固定为
1 个性能 Worker，使用稳定的 `atp-single-node` 身份和 `performance.atp-single-node` 队列，普通 Worker 不消费
性能队列；同时关闭跨节点反亲和、HPA、Ingress 与 ServiceMonitor。该组合适配没有 Ingress Controller、Prometheus
Operator CRD 的单节点环境，**不关闭 P4**，也不替代多节点短压、发布级 Prometheus、独立 MinIO 或跨主机恢复证据。

该 overlay 将三个组件的 `imagePullPolicy` 固定为 `Never`，防止从不受控的外部仓库隐式拉取。操作员必须先以同一
不可变 tag 构建并核验 backend、worker、frontend 镜像，再使用与 values 中完全一致的镜像引用导入 K3s containerd；
随后通过 ExternalSecret/SOPS 创建 `atp-single-node-secrets`，并把示例目标替换为可清理的联调目标。完整 Chart 会执行
pre-install/pre-upgrade 迁移并启动核心服务，因此在确认镜像、外部 Secret 及 PostgreSQL/Redis/MinIO 联通前，只允许
执行 `helm lint` 与 `helm template`，不得直接安装。

当前目标 Linux 已按上述边界创建 `atp-single-node` namespace 和 `atp-single-node-secrets`。目标 q19 Compose 的
PostgreSQL、Redis、MinIO 端口仅绑定宿主机回环地址，因此单节点 overlay 开启 `podNetwork.hostNetwork`，并将
Secret 的三个 Host/Port 指向宿主机回环端点；Secret 值未写入仓库。端点修改仅用于当前开发联调，不适用于普通
多节点部署；临时 Pod 到三项服务的 TCP 连通性已通过并清理。

单节点没有 Prometheus Operator 时，可以使用仓库内有界采样器持续留存开发/联调证据：

```bash
python3 scripts/k3s-observability-sampler.py \
  --source-revision "$(git rev-parse HEAD)" \
  --context atp-single-node \
  --namespace atp-single-node \
  --selector app.kubernetes.io/instance=atp-single-node \
  --duration-seconds 60 \
  --interval-seconds 10 \
  --output docs/evidence/c1-k3s-bounded-observability.json
```

脚本通过 Kubernetes Metrics API 采集节点和 Pod CPU/内存，通过 API proxy 读取 Backend、普通 Worker 和
Performance Worker 的 `/metrics`，只保存指标族摘要，不保存指标原文。节点/Pod 不 Ready、发生重启或 Pressure、
资源样本缺失、必需组件缺失、指标端点不可读都会生成告警并以非零状态退出。它适合可重复的单节点有界观察，不能
替代 Prometheus TSDB、ServiceMonitor target、告警规则执行或长期 SLO 历史。2026-09-10 当前环境实测证据见
[`evidence/c1-k3s-bounded-observability-2026-09-10.json`](evidence/c1-k3s-bounded-observability-2026-09-10.json)。

由于 `hostNetwork` Pod 会直接占用宿主机端口或 X11 抽象套接字，Backend、Worker、Flower、Performance Worker 和 Web
Recorder Deployment 使用 `RollingUpdate(maxSurge=0,maxUnavailable=100%)`，确保单副本更新时先释放旧资源再创建新
Pod；否则默认 `maxSurge` 会让新 Pod 因端口或 display 冲突阻塞原子升级。Beat 固定使用 `Recreate`。Flower 内存 limit
同时提升至 `512Mi`，避免长时间运行时因默认 `256Mi` limit 被 OOMKilled。

长期运行 Deployment 的 Pod template 包含生成 ConfigMap 的校验值；Chart 自建 Secret 时还包含生成 Secret 的校验值。
因此 Helm 更新环境配置会触发进程重建，不会出现资源对象已更新但 Pod 仍读取旧环境的假升级。外部 Secret 的内容不在
Chart 中，外部控制器更新后仍需由其 rollout 机制或显式重启承载 Pod。

当前提交 `1bccfef4` 的 backend、worker、frontend 镜像已分别按 overlay 中的精确引用构建并导入 K3s containerd。随后使用临时 tag 覆盖执行了服务端 dry-run，修复后的 Chart 已在目标单节点实际安装：Release `atp-single-node` 为 `deployed`，迁移 Hook 成功，5 个核心 Deployment 均为 `1/1`，Backend `/health` 返回 200，安装后约 30 秒复核无新增重启。该结果仅证明单节点开发/联调安装可用，不关闭 P4/P9；脱敏证据见 [`evidence/k3s-single-node-helm-install-2026-09-04.json`](evidence/k3s-single-node-helm-install-2026-09-04.json)。

2026-09-09 将提交 `5c0f6908` 的完整 Backend 源码叠加到已验证的 `1bccfef4` 基础镜像，并将完整 Worker
源码叠加到已验证的 `init-reaper-0f553ae3e046` 基础镜像，生成并导入不可变标签 `5c0f6908`；该方式用于规避构建时
Debian 软件源临时不可达，同时保留既有系统依赖。Release revision 11 完成迁移到 `20260908_0070`，5 个核心 Pod
均 Ready、零重启且 `/health` 返回 200。升级过程中发现 Backend 默认滚动策略与单节点宿主机 8000 端口冲突，现场
修复后恢复升级；上述无 surge 策略及其回归测试已固化到 Chart。该证据仍不等于三角色或五域真实任务验收。
提交 `74a15fa4` 的 Chart 随后通过服务端 dry-run，并以 `--rollback-on-failure --wait` 固化为 revision 12；集群中
Backend 策略为 `RollingUpdate(surge=0,unavailable=100%)`。升级后五个核心 Pod 持续 30 秒 Ready、零重启，迁移
仍为 `20260908_0070 (head)`，Backend `/health` 保持 200。

该单节点 overlay 使用 `hostNetwork`，因此当前 K3s Backend 的宿主机访问端口为 `8000`。宿主机上的 `29080`
属于旧 q19 Docker Backend；它可能复用同一 PostgreSQL 数据库，但不代表 revision 12 的应用代码。Windows 本地 Vite
或验收脚本必须指向 `http://192.168.3.196:8000`，不得用 `29080` 作为当前 K3s 版本、角色矩阵或发布证据。

2026-09-09 B1.4 过期确认实测发现，Backend 在领域 API 返回 HTTP 409 后会回滚事务；旧实现随后读取已过期的
`ExecutionCommand.id`，可能触发 SQLAlchemy `MissingGreenlet` 并把首次拒绝升级为 HTTP 500。提交 `86668152`
改为在回滚前保存命令主键，并以不可变 Backend 标签升级到 Helm revision 13。五个核心 Pod Ready、零重启，
`/health` 返回 200；新建成功终态 Performance Run 后，首次停止与同键重放均返回 409，Backend 日志无新异常。

2026-09-09 B2.1 在 revision 18 启用独立 Web Recorder，并以
`atp:single-node:web-recording:commands` 与宿主机旧 Compose Recorder 隔离。部署过程发现 ConfigMap 更新不会自动重建
Pod，以及 X11 `:99` 在旧 Pod 退出后可能短暂残留；Chart 已加入配置校验 rollout、Recorder 无 surge、Tini、Xvfb
存活/socket 门禁和有界 display 回退。最终 Worker 池仅有 1 个当前 K3s Worker，三浏览器录制及目标不可达恢复通过。

2026-09-09 B2.2 发现共享 Redis 时，遗留 ATP Worker 与当前 K3s Worker 同时监听 `default` 会导致 Web
回放落到错误版本。可在 Backend 与当前 Worker 同时设置 `WEB_EXECUTION_QUEUE=web.<release>`，并把该队列加入
当前 Worker 的 `CELERY_QUEUES`；其他部署不要监听这个队列。`default` 保持默认值以兼容未共享 Broker 的部署。
单节点环境使用 `web.atp-single-node` 后，Chromium、Firefox、WebKit 回放及视觉基线闭环通过。

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
