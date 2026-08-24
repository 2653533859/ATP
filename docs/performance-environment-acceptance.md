# 性能 Worker 环境验收 Runbook

> 2026-08-24 N6.7：隔离 Compose 已包含独立通用 `worker` 和独立 `web-recorder` 服务；录制 Worker 固定使用 Worker 模式、Redis 路由前缀、Xvfb `:99` 和 `init: true`，q19 已完成注册、Chromium 录制、快照、PNG 截图、停止和重启恢复验收。Trace/HAR/Console/网络日志/运行报告完整链路、Android、真实性能节点和外部通知/缺陷平台仍需单独验收。

## 2026-08-17 当前代码隔离栈验收

已在 `172.31.27.133` 的 `/opt/atp-q18-acceptance-20260817` 使用当前代码部署隔离 Compose 栈。由于旧 q17 栈占用默认回环端口，当前栈使用 Backend `28080`、Prometheus `28090`、Worker metrics `28092`；旧栈未停止。Backend `/health`、Prometheus `/-/ready` 和 PromQL 均通过，Backend 与 `performance-worker` 两个 target 均为 `up`。

Worker 镜像已固定使用 PostgreSQL 16.15 客户端。实际日备份已上传 `pg-backups/daily/`，从 MinIO 下载后恢复到临时数据库并验证 53 张 public 表，临时数据库随后删除。完整脱敏证据见 [`performance-linux-q18-acceptance-2026-08-17.json`](evidence/performance-linux-q18-acceptance-2026-08-17.json)。

这次验收只关闭 Linux Docker Compose 隔离环境、Prometheus 采集和单次备份恢复门禁；没有关闭 Kubernetes 多节点、生产 Prometheus 历史、跨主机 MinIO 灾备或外部通知投递门禁。

## Prometheus 监控验收

性能环境 smoke 现在可以把 Prometheus readiness 和 PromQL 查询纳入同一份 JSON 证据。`--prometheus-url` 只接受不带用户信息、查询参数或片段的 HTTP(S) 根地址；查询内容通过请求参数编码，不从命令行读取 Token 或密码。

隔离 Compose 栈现在默认启动 Prometheus（宿主机回环端口 `18090`），同时抓取 Backend、通用执行 Worker 和专用性能 Worker；配置位于 `deploy/performance-acceptance/prometheus.yml`，保留 7 天本地历史。生产 Kubernetes 使用 Helm 的 `performance-worker` Service + ServiceMonitor，仍需在目标集群用 Prometheus Operator 实际确认 target 为 `up`。

```bash
python scripts/performance-environment-smoke.py \
  --prometheus-url https://prometheus.example.test \
  --prometheus-query 'up{job="atp-backend"}' \
  --report docs/evidence/performance-prometheus-2026-08-12.json
```

该检查依次验证 `/-/ready` 返回 HTTP 200，以及 `/api/v1/query` 返回 `status=success` 和数组形式的 `data.result`。没有真实 Prometheus 时，命令必须保持失败或明确跳过，不能用本地测试结果替代目标环境证据。

## 2026-08-12 Windows 本地真实执行补充

Windows 本地已完成平台级 k6/Locust 验收：主 Worker 节点 `perf-node-local-01` 消费 `performance` 队列，使用 ATP `/health` 作为本地目标；k6 run `8` 成功并回传 20 次迭代和 3 条资源指标，Locust run `10` 成功并回传 168 次请求、错误率 0。证据分别为 [`performance-windows-local-k6-smoke-2026-08-12.json`](evidence/performance-windows-local-k6-smoke-2026-08-12.json) 和 [`performance-windows-local-locust-smoke-2026-08-12.json`](evidence/performance-windows-local-locust-smoke-2026-08-12.json)。

这只证明 Windows 本地 Worker 的真实队列投递、执行器启动、结果摘要和指标回传。Windows 本地 Prometheus 目标指标闭环也已完成，证据见 [`performance-windows-local-prometheus-target-metrics-2026-08-12.json`](evidence/performance-windows-local-prometheus-target-metrics-2026-08-12.json)；Linux/Kubernetes 镜像、真实外部目标、生产 Prometheus/SLO 历史、TLS gRPC/JMeter 专用节点及 Android 设备仍需按本 Runbook 独立验收。

## Worker 测试外部依赖隔离修复（2026-08-12）

- `test_tasks_mobile_special_dispatch.py` 与 `test_tasks_performance.py` 现在使用 Fake control client，不会在测试期间连接本机真实 Redis；显式取消测试仍单独覆盖取消分支。
- Worker 全量 `427 passed`，完整非集成后端 `1889 passed`，覆盖率 `82.13%`。
- 远程 SSH/MCP 会话恢复失败；Windows 本机 k6/Locust、资源指标和本地 Prometheus 目标指标链路已有独立证据，真实外部目标、生产 metrics、Kubernetes/Prometheus 历史及其余外部环境验收仍需在目标主机继续执行。

## 2026-08-13 外部目标连接复核

- 对已配置 Linux 目标执行只读系统概览检查时，MCP 返回 `Transport closed`，本次未取得主机、Worker、Prometheus 或目标服务证据。
- 在连接恢复前，继续保留 Linux/Kubernetes 性能 Worker、真实 TLS 目标、取消、allowlist、资源采样和生产 Prometheus 为待验收项；本机回归与 Windows 本地指标证据不替代外部结论。

## 2026-08-12 实际 Linux 验收记录

- 已从 Windows 生成并校验性能验收 bundle，使用显式 allowlist 收集 323 个文件；当前 SHA-256 以包旁 `.sha256` sidecar、`Task.md` 和 `MEMORY.md` 的同步记录为准，不包含真实 `.env`、证书或私钥。
- 已部署到 `172.31.27.133:/opt/atp-q17-acceptance` 的独立 Compose 项目。PostgreSQL、Redis、MinIO、Backend、验收目标和性能 Worker 均已启动，Backend `/health` 返回 `status=ok`，迁移容器以 0 退出；主机已有服务未被修改。
- API/节点 smoke 已通过：四类执行器 ready，`worker-a` online，队列为 `performance.worker-a`，目标 `http-target` 命中 egress allowlist。报告路径为远端 `docs/evidence/performance-api-node-2026-08-12.json`。
- 远端真实 k6 run 首次执行暴露验收脚本的两个缺陷：JSON 报告不能序列化 `Path`，以及写请求未带 `X-Requested-With` 被 CSRF 拒绝；已修复并补充回归测试（本地脚本 `17 passed`）。Windows 本机 k6/Locust 已完成真实 run；远端真实目标、metrics、取消、Kubernetes/Prometheus 验收仍需在目标工具镜像更新后重跑，未将旧失败报告记为通过。

本文用于 Q17-03/Q17-04 的 Linux/Kubernetes 外部环境验收。仓库内的单元测试和本地真实 gRPC server 联调只能证明实现链路可运行，不能替代真实镜像、真实证书、真实目标服务和真实 Celery 队列的验收。

性能验收 Compose 栈同时包含单副本 Beat。它仅用于隔离环境的计划任务/备份联调，生产仍必须保证 Beat 单副本；备份任务在 Worker 内直接使用 `pg_dump` + Python MinIO SDK，不依赖容器内的仓库根目录脚本或 `mc` CLI。

> 当前状态（2026-08-11）：Windows 本地已完成门禁验证，JMeter 5.6.3 使用仓库内无凭据 JMX 对本地 `/login` 完成 1 请求、0 错误并生成 JTL/HTML 报告，证据目录为 `.local-run/jmeter-smoke-20260811-233647/`。当前主机没有 Docker/Kubernetes，尚未部署 ATP 专用 Worker 镜像或外部 gRPC/Locust 目标；建立隔离部署后，必须重新执行本文全部命令并保存 JSON 证据，才能关闭 Q17-04。

## Windows 打包并传输验收栈

在 Windows 开发机上使用仓库内的 PowerShell 入口生成不含真实凭据和本地依赖的验收包。脚本只收集性能 Compose、Backend/Worker 构建上下文、目标服务夹具、验收工具和本 Runbook，不会把根目录 `.env`、启动档案、`node_modules`、虚拟环境、测试缓存或 `.local-run` 带入压缩包。

```powershell
./scripts/package-performance-acceptance.ps1
```

默认输出到 `.local-run/atp-performance-acceptance-<timestamp>.zip`，并生成同名 `.sha256` 校验文件。需要覆盖同名输出时必须显式使用 `-Force`：

```powershell
./scripts/package-performance-acceptance.ps1 `
  -OutputPath .local-run/atp-performance-acceptance-latest.zip `
  -Force
```

命令输出 JSON，包含包路径、SHA-256、文件数、源 Git commit 和 `worktree_dirty` 标记。目标 Linux 主机收到压缩包后，应在隔离目录解压，先核对 `.sha256` 和 `bundle-manifest.json`，再按本文 Compose 命令构建；真实 `.env.performance-acceptance` 必须在目标主机单独创建，不能从开发机复制。

## ARM64 Docker Compose 隔离验收栈

仓库提供了一个独立 Compose 栈，用于没有 Kubernetes 的 Linux 主机。它使用独立的 PostgreSQL、Redis、MinIO 命名卷，不复用主机上已有服务；`acceptance-target` 同时提供真实网络可达的 TLS gRPC 和 HTTP/Locust 目标。

```bash
cp .env.performance-acceptance.example .env.performance-acceptance
# 编辑 .env.performance-acceptance，至少替换 APP_SECRET_KEY、数据库密码、MinIO 密码和首个管理员密码
docker compose --env-file .env.performance-acceptance \
  -f docker-compose.performance-acceptance.yml build
docker compose --env-file .env.performance-acceptance \
  -f docker-compose.performance-acceptance.yml up -d
```

ARM64 主机应在目标主机上直接构建镜像，避免把其他架构的本地镜像误推送到目标环境。确认服务状态：

```bash
docker compose --env-file .env.performance-acceptance \
  -f docker-compose.performance-acceptance.yml ps
curl http://127.0.0.1:18080/health
```

Compose 会等待迁移完成并确认 Backend `/health` 为 healthy 后才启动通用执行 Worker、专用性能 Worker 和验收工具，避免 API 尚未就绪时误报队列或执行器失败。

启动后可直接验证隔离 Prometheus：

```bash
curl http://127.0.0.1:18090/-/ready
curl --get --data-urlencode 'query=up{job=~"atp-backend|atp-worker|atp-performance-worker"}' \\
  http://127.0.0.1:18090/api/v1/query
```

三个 target 都必须返回 `up=1`；这只关闭隔离栈指标采集门，不替代生产 Prometheus 的长期历史和告警验收。需要确认队列注册时，可在目标主机执行：

```bash
docker compose --env-file .env.performance-acceptance \
  -f docker-compose.performance-acceptance.yml exec -T worker \
  celery -A app.worker.celery_app inspect ping --timeout=10
docker compose --env-file .env.performance-acceptance \
  -f docker-compose.performance-acceptance.yml exec -T worker \
  celery -A app.worker.celery_app inspect active_queues --timeout=10
```

仓库内的 [`jmeter_smoke.jmx`](../deploy/performance-acceptance/jmeter_smoke.jmx) 是无凭据的最小 JMeter 回归样例，只访问 ATP `/login`，可用于确认 JMeter、JTL 和 HTML 报告生成链路：

```bash
jmeter -n -t deploy/performance-acceptance/jmeter_smoke.jmx \
  -l /tmp/atp-jmeter-smoke.jtl \
  -e -o /tmp/atp-jmeter-smoke-html
```

该样例只证明当前机器上的 JMeter 可执行，不替代 Docker Worker 中的 JMeter 验收。

在 ATP 中创建 gRPC 压测定义时上传 [`acceptance.proto`](../deploy/performance-acceptance/acceptance.proto)，并使用以下关键配置。`tls_root_certificates_file` 指向 Worker 只读挂载的公有 CA 证书，不是密码或私钥：

```json
{
  "target": "grpc-target:50051",
  "service": "demo.v1.Greeter",
  "method": "Unary",
  "request": {"name": "ATP"},
  "use_tls": true,
  "tls_server_name": "grpc-target",
  "tls_root_certificates_file": "/etc/atp/tls/server.crt",
  "concurrency": 1,
  "iterations": 5,
  "duration_seconds": 30
}
```

创建压测定义并拿到 ID 后，在 Compose 网络内运行验收工具：

```bash
docker compose --env-file .env.performance-acceptance \
  -f docker-compose.performance-acceptance.yml run --rm acceptance-tools \
  --api-base-url http://backend:8000 \
  --node-id worker-a --expected-queue performance.worker-a \
  --target grpcs://grpc-target:50051 --require-tls \
  --ca-file /etc/atp/tls/server.crt --require-node-allowlist \
  --smoke-test-id <GRPC_TEST_ID> --smoke-executor grpc \
  --idempotency-key "ci-${CI_PIPELINE_ID:-manual}-grpc-smoke" \
  --require-metric-source performance-worker \
  --require-metrics --report /evidence/performance-grpc-smoke.json
```

验收工具默认最多等待 60 秒，直到专用 Worker 的 Redis 心跳把节点状态刷新为 `online`；若目标环境启动较慢，可显式增加 `--node-ready-timeout-seconds`，避免把正常的启动竞态误判为节点故障。

真实 smoke/cancel 触发会把 `--idempotency-key`（或 `ATP_PERFORMANCE_IDEMPOTENCY_KEY`）作为基值，并自动追加 `-smoke`/`-cancel` 作用域。CI 重试应固定该基值，避免 HTTP 超时后重复创建 Run；本地未提供基值时每次命令会生成新键。脚本会在发送前校验幂等键格式，验收报告不会写入账号密码或 Token。

`--require-metric-source` 可重复传入，要求每个来源至少有一条 `metrics` 非空的采样；例如 `performance-worker` 验证 Worker 资源采集，`target-service-prometheus` 验证目标 Prometheus 采集。仅有 `errors` 或空指标的样本不会被当作通过证据。

如果该压测定义已设置成功基线，可追加 `--require-baseline` 检查基线对比响应；发布回归验收再追加 `--fail-on-baseline-regression`，任一核心指标方向为 `regression` 时命令退出失败。未设置基线时不要开启这两个参数，否则应保持验收失败而不是降级为“无基线也通过”。

Locust 定义上传 [`locust_smoke.py`](../deploy/performance-acceptance/locust_smoke.py)，目标使用 `http-target:8080`，将上面命令中的目标替换为 `http://http-target:8080`，并使用 `--smoke-executor locust`。取消验收仍使用一条持续时间足够长的已存在定义和 `--cancel-test-id`。

## 1. 验收前提

- 发布机可以访问 Kubernetes API，并安装 `kubectl`、`helm` 和 Python 3.12+。
- ATP API 已完成迁移，`/health` 可访问。
- PostgreSQL、Redis、MinIO 和 ATP API 的地址通过 ExternalSecret、SOPS 或平台 Secret 注入，仓库不保存真实凭据。
- 已准备两个项目内的压测定义：
  - 一个 `executor=grpc` 的短时 TLS smoke 定义，目标为专用 gRPC 服务，运行时间建议至少 10 秒；
  - 一个 `executor=locust` 的短时 HTTP smoke 定义；
  - 如需取消验收，再准备一个持续时间至少 60 秒的 gRPC 或 Locust 定义。
- gRPC `.proto`、service/method、请求体、TLS 配置和目标地址已经过人工确认；敏感 metadata 只能使用 `{{ENV_KEY}}` 占位符。

## 2. 构建并发布 Worker 镜像

`backend/Dockerfile.worker` 会把 k6 二进制复制到 Python Worker 镜像，并在构建阶段验证 k6、Locust、grpcio、grpcio-tools、JMeter 以及 Chromium/Firefox/WebKit。发布机示例：

```bash
IMAGE=registry.example.test/atp/worker:2026-08-07-q17
docker build -f backend/Dockerfile.worker -t "$IMAGE" backend
docker push "$IMAGE"
```

Helm values 至少需要把普通 Worker 从 `performance` 队列移开，并为专用 Worker 指定稳定节点身份。实际 Secret 使用外部 Secret 管理器：

```yaml
image:
  repository: registry.example.test/atp
  worker:
    tag: 2026-08-07-q17

worker:
  queues: default,ios,ai,maintenance
config:
  CELERY_QUEUES: default,ios,ai,maintenance
  PERFORMANCE_EXECUTORS: k6,locust,grpc,jmeter

performanceWorker:
  enabled: true
  queues: performance.worker-a,performance
  nodeEnabled: true
  nodeId: worker-a
  nodeName: Performance Worker A
  nodeQueue: performance.worker-a
  nodeMaxVus: 100
  nodeMaxConcurrency: 2
  nodeEgressAllowlist: grpc.example.test,http.example.test
  networkPolicy:
    enabled: true
    egress:
      # 必须按集群实际地址补齐 DNS、PostgreSQL、Redis、MinIO 和目标服务。
      - to:
          - namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: kube-system}}
        ports: [{protocol: UDP, port: 53}, {protocol: TCP, port: 53}]
      - to:
          - ipBlock: {cidr: 10.20.0.0/16}
        ports: [{protocol: TCP, port: 443}]
```

部署后检查：

```bash
helm upgrade --install atp deploy/helm/atp \
  --namespace atp-staging --create-namespace \
  -f values-staging.yaml
kubectl -n atp-staging rollout status deployment/atp-atp-performance-worker --timeout=180s
kubectl -n atp-staging get pods -l app.kubernetes.io/component=performance-worker -o wide
```

## 3. 自动化验收命令

验收工具只读取 `ATP_TOKEN`，或通过环境变量读取 `ATP_USERNAME`/`ATP_PASSWORD`。凭据不会进入命令参数、终端输出或 JSON 报告。

### 3.1 Docker Compose/Linux Worker

目标主机没有 Kubernetes 时，可直接在安装 Docker 的 Linux 主机上检查 Worker 容器或镜像：

```bash
python scripts/performance-environment-smoke.py \
  --docker-container atp-performance-worker \
  --report docs/evidence/performance-docker-worker-2026-08-07.json
```

如果只需要验收刚构建的镜像，不启动常驻容器：

```bash
python scripts/performance-environment-smoke.py \
  --docker-image registry.example.test/atp/worker:2026-08-07-q17 \
  --report docs/evidence/performance-worker-image-2026-08-07.json
```

镜像模式会临时启动容器执行依赖探测，不读取应用配置，也不会连接数据库、Redis 或 MinIO。

### 3.2 Worker、节点、目标和真实 gRPC smoke

```bash
export ATP_TOKEN='由安全渠道注入的短期 Token'
python scripts/performance-environment-smoke.py \
  --api-base-url https://atp-staging.example.test \
  --namespace atp-staging \
  --deployment atp-atp-performance-worker \
  --node-id worker-a \
  --expected-queue performance.worker-a \
  --target grpcs://grpc.example.test:443 \
  --require-tls \
  --ca-file /etc/atp/ca.pem \
  --require-node-allowlist \
  --verify-worker-image \
  --smoke-test-id 42 \
  --smoke-executor grpc \
  --require-metrics \
  --report docs/evidence/performance-grpc-smoke-2026-08-07.json
```

这条命令依次验证：

1. ATP `/health`、执行器 ready 状态和鉴权；
2. `worker-a` 节点在线、能力声明包含 `grpc`、队列/节点约束可用；
3. DNS、TCP 和真实 TLS 证书校验；
4. Kubernetes Deployment、Pod Ready 状态及镜像内 `grpcio`、`grpcio-tools`、Locust、k6、JMeter、Chromium/Firefox/WebKit；
5. 已存在的 gRPC 测试通过指定节点真实入队、执行、落库并生成结果；
6. 至少一条资源采样记录存在。

### 3.3 Locust smoke

用另一个已配置的 Locust 测试定义执行，避免把 gRPC 结果误当成 Locust 验收：

```bash
python scripts/performance-environment-smoke.py \
  --api-base-url https://atp-staging.example.test \
  --node-id worker-a \
  --expected-queue performance.worker-a \
  --target https://http.example.test \
  --require-node-allowlist \
  --smoke-test-id 43 \
  --smoke-executor locust \
  --report docs/evidence/performance-locust-smoke-2026-08-07.json
```

### 3.4 取消验收

取消测试必须使用一个持续时间足够长的测试定义，否则运行可能在停止请求到达前自然完成：

```bash
python scripts/performance-environment-smoke.py \
  --api-base-url https://atp-staging.example.test \
  --node-id worker-a \
  --expected-queue performance.worker-a \
  --target grpcs://grpc.example.test:443 \
  --require-tls \
  --ca-file /etc/atp/ca.pem \
  --require-node-allowlist \
  --cancel-test-id 44 \
  --cancel-after-seconds 3 \
  --report docs/evidence/performance-cancel-2026-08-07.json
```

工具不会自动创建或删除压测定义，也不会在没有显式 `--smoke-test-id`/`--cancel-test-id` 时产生目标流量。

## 4. 通过标准与证据

每次验收必须保存 JSON 报告、命令执行时间、镜像 tag、Helm values 的脱敏版本和以下日志/状态证据：

| 项目 | 必须证据 | 失败处理 |
|---|---|---|
| 镜像 | `grpcio`、`grpcio-tools`、Locust、k6、JMeter 和 Chromium/Firefox/WebKit 命令输出 | 重新构建 Worker 镜像 |
| 节点 | API 返回 `status=online`、执行器能力和最近心跳 | 检查节点 ID、队列、Redis、数据库和 Worker 日志 |
| 队列 | Celery Worker 收到 `run_performance_test`，并使用目标节点队列 | 检查 `nodeQueue` 与 `queues` 是否完全一致 |
| TLS | DNS、TCP、证书链和 SNI 校验记录 | 检查 CA、证书 SAN、NetworkPolicy 和服务端监听地址 |
| gRPC/Locust | run 进入 `running`，终态为 `success`，摘要 `iterations > 0`，错误率不超过命令阈值 | 保存 run 错误、Worker 日志和目标服务日志，禁止仅依据前端提示判断 |
| 取消 | stop 请求后终态为 `cancelled` | 检查 Redis 取消标记、Worker 子任务终止和 run 状态流转 |
| 资源采样 | run 关联至少一条 CPU/内存/数据库/Redis/MinIO 样本 | 检查采样开关、采样间隔和节点指标端点 |
| 网络隔离 | 应用 allowlist 与 Kubernetes Egress 均允许目标且拒绝未授权目标 | 先修复 allowlist/NetworkPolicy，再重跑正向 smoke |

任何一项缺少日志或外部状态证据都标记为 `BLOCKED`，不能仅凭 HTTP 200、前端状态或单个 pytest 结果判定环境验收完成。

## 5. 回滚与故障排查

```bash
helm history atp -n atp-staging
helm rollback atp <REVISION> -n atp-staging
kubectl -n atp-staging logs deployment/atp-atp-performance-worker --since=15m
kubectl -n atp-staging describe pod -l app.kubernetes.io/component=performance-worker
```

常见故障顺序：先确认 Worker Pod Ready，再确认节点心跳和 Celery 队列，随后确认 NetworkPolicy/DNS/TLS，最后查看目标服务的 gRPC status 或 Locust aggregate 结果。不要把目标服务拒绝、证书失败和 Worker 未消费任务混写成同一个“压测失败”。
