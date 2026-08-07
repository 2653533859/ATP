# 性能压测中心薄切方案

> 状态：Q8 Phase 5 已完成。本文固定执行器选择、队列隔离和结果契约；当前已具备模型、API、脚本上传、Celery 任务、k6 summary 解析、基础压测中心页面、threshold 展示、raw summary 访问入口，并已用便携版 k6 v0.52.0 跑通最小 demo。

## 目标

- 支持 HTTP 压测脚本上传与异步执行。
- 提供基础结果指标：RPS、P95/P99、错误率、吞吐趋势。
- 压测结果独立展示，不混入功能测试通过率、用例通过率或普通 `TestRun` pass/fail 统计。

## 执行器选择

第一阶段优先选 k6：

- 单二进制/容器执行，适合放入独立 Celery worker 镜像。
- 脚本为 JavaScript，便于用户从 API 示例、cURL 或 OpenAPI 片段改写。
- `--summary-export` 可输出 JSON，便于后端解析并落库。
- threshold 语义清晰，可直接映射为平台的性能门禁。

Locust 暂作为后续备选，适合需要 Python 编排、复杂用户行为和分布式压测的场景。

## Worker 与队列

新增队列：`performance`。

任务名：`run_performance_test`。

执行流：

1. API 创建 `PerformanceRun`，状态为 `pending`。
2. API 将 `run_performance_test` 投递到 `performance` 队列。
3. performance worker 从对象存储下载 k6 脚本到临时目录。
4. worker 执行 `k6 run --summary-export result.json script.js`。
5. worker 解析 `result.json`，上传原始结果产物，并写入摘要指标。

生产环境建议将 `performance` worker 与功能测试 worker 分开部署：

- `CELERY_QUEUES=performance`
- `worker_prefetch_multiplier=1`
- 低并发，按压测规模设置 CPU/内存 limit
- 单独配置网络出口策略和目标域名 allowlist

## 生产安全限制

Q9 Phase 4 在 API 创建 run 或保存默认 options 前增加安全限制：

- `PERFORMANCE_TARGET_ALLOWLIST`：逗号分隔域名；为空时允许所有目标，便于本地开发。配置后，`env.TARGET_URL`、`env.BASE_URL`、`env.URL` 必须命中 allowlist 域名或其子域名。
- `PERFORMANCE_MAX_VUS`：限制 `options.vus` 与 `options.stages[].target` 的最大值。
- `PERFORMANCE_MAX_DURATION_SECONDS`：限制 `options.duration`，或 stages 模式下所有 stage duration 之和。

默认 options 与触发 run 时的 override options 会先合并再校验；不满足限制时返回 `400`，不会创建 run，也不会投递到 performance 队列。

触发压测时会把所选环境的变量加密固化到本次运行快照，Worker 执行时解密使用；因此运行期间修改环境不会改变已经触发的任务。运行详情接口会移除该内部快照以及历史遗留的敏感 `env` 参数。密码、Token 等敏感变量不能直接写入压测参数，必须通过环境注入。

## 趋势、对比与清理

- Performance Center 基于最近 run 展示 RPS、P95/P99 与错误率趋势。
- 执行记录支持勾选 2-4 条 run 对比核心指标，并以第一条选择作为 P95 基线。
- `performance/` 已纳入存储清理默认 prefix；`performance/scripts/*` 被压测定义引用时会阻止删除，`performance/runs/*/summary.json` 可按策略清理。
- 若 DB 中存在缺失的 `PerformanceRun.raw_result_object_name` 引用，存储清理的 orphan repair 会将该字段置空。

## Q16-09 资源指标采样

压测 worker 在 k6 子进程运行期间按 `PERFORMANCE_METRICS_INTERVAL_SECONDS` 采样，并将样本写入 `performance_metric_samples`，通过 `run_id` 与压测执行记录关联。样本包含采集时间、节点标识、采集来源、指标 JSON 和组件级错误列表；单个 PostgreSQL、Redis 或 MinIO 连接失败只会使对应指标缺失，不会改变压测状态。

当前采集指标包括：

- worker 节点 CPU 使用率、内存使用率、已用/可用内存；
- PostgreSQL 活跃连接数、最大连接数、缓存命中率；
- Redis 客户端数、内存使用量、峰值内存、每秒操作数、阻塞客户端数；
- MinIO bucket 可达性、探测耗时，以及按 `PERFORMANCE_MINIO_INVENTORY_INTERVAL_SECONDS` 周期更新的对象数量和总字节数。

查询接口为 `GET /api/v1/performance/runs/{run_id}/metrics?limit=2000`，详情页可按指标切换时间线。`PERFORMANCE_METRICS_ENABLED=false` 可关闭采样；`PERFORMANCE_METRICS_MAX_SAMPLES` 用于限制单次运行的样本数量。

## Q16-10 分布式压测节点与出口隔离

压测节点通过 `PerformanceNode` 注册到数据库，并以稳定的 `node_id`、Celery `queue_name` 和 worker 心跳标识自身。节点状态由后端根据 `enabled`、排空状态和最近心跳计算为 `online/offline/disabled/draining`；节点没有有效心跳时不会接收新任务。

节点能力与运行约束包括：

- `max_vus`：限制该节点承载的单次压测峰值 VUs，覆盖 `vus`、`stages[].target` 和 k6 `scenarios` 中的 VU 配置；
- `max_concurrency`：限制节点上 pending/running/cancelling 运行数量，API、定时调度和 worker 启动前都会检查；
- `egress_allowlist`：按目标 URL hostname 做精确域名/子域名校验，避免节点把流量发往未授权地址；
- Helm `performanceWorker.networkPolicy`：可选的 Kubernetes 原生 Egress NetworkPolicy。启用后只允许 values 中声明的 egress 规则，DNS、数据库、Redis、MinIO 和目标服务的出口都必须显式加入规则。

节点管理接口只允许 engineer/admin：

- `GET /api/v1/performance/nodes`：查看节点状态、队列、容量和最近心跳；
- `POST /api/v1/performance/nodes`、`PATCH /api/v1/performance/nodes/{id}`、`DELETE /api/v1/performance/nodes/{id}`：维护节点登记信息；
- 触发 run 或保存定时执行时传入 `performance_node_id`，任务会投递到该节点的 `queue_name`；未指定节点时保持原有 `performance` 队列行为。

Dedicated worker 示例：

```yaml
performanceWorker:
  enabled: true
  queues: performance.node-a,performance
  nodeEnabled: true
  nodeId: worker-a
  nodeName: Worker A
  nodeQueue: performance.node-a
  nodeMaxVus: 100
  nodeMaxConcurrency: 2
  nodeEgressAllowlist: api.example.test,static.example.test
  networkPolicy:
    enabled: true
    egress:
      # 示例规则；生产环境还需按集群 DNS、数据库、Redis、MinIO 和目标服务补全。
      - to:
          - ipBlock:
              cidr: 10.20.0.0/16
        ports:
          - protocol: TCP
            port: 443
```

本地或 Docker worker 可通过 `.env` 设置 `PERFORMANCE_NODE_ID`、`PERFORMANCE_NODE_QUEUE` 等变量。`PERFORMANCE_NODE_ID` 为空时 worker 不注册显式节点，兼容原有共享 worker；创建登记后必须让对应 worker 至少发送一次心跳，节点才会显示为在线。应用层 allowlist 与 Kubernetes NetworkPolicy 是两层独立防线，不能用其中一层代替另一层。

## Q16-11 数据集参数化与用户行为编排

压测定义可以绑定项目内的测试数据集。保存定义或触发 run 时会校验数据集归属，并固定当前数据集版本到 `PerformanceRun.dataset_version`；worker 优先读取固定版本，避免运行期间编辑数据集改变结果。数据行通过 worker-only 的 `ATP_DATASET_JSON` 环境变量传给生成的 k6 脚本，不会写入用户可见的 `options_snapshot`。

可视化脚本支持使用 `{{FIELD_NAME}}` 引用当前数据行字段；每个 VU 按 `__ITER % rows.length` 轮转数据行。数据集中的 `TARGET_URL`、`BASE_URL` 和 `URL` 也会参与全局/节点出口 allowlist 校验，不能通过参数化绕过网络限制。手写 k6 脚本可以读取 `__ENV.ATP_DATASET_JSON`，自行选择行和编排数据。

可视化场景还支持多个顺序 HTTP 行为步骤：每步独立配置方法、URL、请求头、参数、请求体、期望状态和响应包含检查，步骤之间可配置 `thinkTime`。生成脚本按 VU 迭代顺序执行这些请求，并在每步记录 k6 check 结果。

Q17-01 已接入 Locust：选择 `executor=locust` 后上传 `.py` 脚本，worker 以 headless 模式执行并读取 Locust aggregate CSV，归一为同一套 `rps/p95_ms/p99_ms/error_rate/iterations` 摘要。`users`、`spawn_rate`、`run_time`、`host`、`tags` 和 `exclude_tags` 通过 `default_options` 配置；环境变量和 `ATP_DATASET_JSON` 仍由 worker-only 运行时注入。Locust 脚本是可执行 Python，生产环境必须在专用 worker、最小权限容器和网络出口策略下运行。

gRPC 已接入统一执行器契约，支持 `.proto` 上传、动态 descriptor 编译、Unary/Server Streaming/Client Streaming/Bidi Streaming 并发调用、TLS/metadata 校验、取消和统一结果摘要；详细配置见 `docs/performance-executor-evaluation.md`。Linux/Kubernetes 外部验收使用 `scripts/performance-environment-smoke.py`，操作步骤和证据要求见 `docs/performance-environment-acceptance.md`。

gRPC options 至少包含 `target`、完整 `service`、`method`、`request`、`mode`、`concurrency` 和 `duration_seconds`。客户端流/双向流可用 `requests` 数组；`{{ENV_KEY}}` 会从 worker 运行时环境中解析，敏感 metadata 不得内联写入；自签名或私有 CA 场景使用 `tls_root_certificates_file` 挂载公有 CA 文件。

## 数据模型草案

`PerformanceTest`：

| 字段 | 说明 |
|------|------|
| `id` | 压测脚本定义 ID |
| `project_id` | 所属项目 |
| `name` | 压测名称 |
| `executor` | `k6`、`locust` 或 `grpc` |
| `script_object_name` | MinIO 脚本对象路径 |
| `default_options` | 执行器 options JSON；k6 使用 VUs/duration/thresholds，Locust 使用 users/spawn_rate/run_time，gRPC 使用 target/service/method/request/mode/concurrency |
| `creator_id` | 创建人 |

`PerformanceRun`：

| 字段 | 说明 |
|------|------|
| `id` | 压测执行 ID |
| `performance_test_id` | 关联脚本定义 |
| `environment_id` | 目标环境 |
| `performance_node_id` | 可选的指定压测节点；为空时使用默认 performance 队列 |
| `status` | `pending/running/success/failed/cancelled` |
| `started_at/finished_at` | 执行时间 |
| `summary` | 平台标准摘要指标 |
| `raw_result_object_name` | 执行器 summary JSON 产物路径 |
| `error_message` | 失败原因 |

`PerformanceMetricSample`：

| 字段 | 说明 |
|------|------|
| `run_id` | 关联的压测执行 |
| `captured_at` | UTC 采样时间 |
| `node_id` / `source` | 采样节点和来源 |
| `metrics` | CPU、内存、PostgreSQL、Redis、MinIO 指标 JSON |
| `errors` | 组件探测失败列表，不影响压测结果 |

## API 草案

- `GET /api/v1/performance/executors`：查询执行器能力、脚本后缀和是否可用。
- `POST /api/v1/projects/{project_id}/performance/scripts?executor=k6|locust|grpc`：上传对应执行器脚本或 Proto，返回 `script_object_name`。
- `POST /api/v1/performance/tests`：创建压测脚本定义。
- `GET /api/v1/projects/{project_id}/performance/tests`：查询项目下压测脚本列表。
- `POST /api/v1/performance/tests/{id}/run`：触发一次压测。
- `GET /api/v1/performance/runs/{id}`：查看压测执行详情。
- `GET /api/v1/performance/runs/{id}/metrics`：查看与本次压测时间线关联的资源指标样本。
- `GET /api/v1/performance/runs?project_id={project_id}`：查询项目下压测执行列表。
- `GET /api/v1/performance/nodes`：查看可用压测节点及容量/心跳状态。

脚本上传约定：

- k6 支持 `.js` / `.mjs`，Locust 支持 `.py`，gRPC 支持 `.proto`；worker 通过 `PERFORMANCE_EXECUTORS` 控制实际启用的执行器。
- 单文件大小限制为 2MB。
- 对象路径格式为 `performance/scripts/{project_id}/{uuid}-{filename}`。
- 前端上传成功后自动回填 `script_object_name`，创建/编辑压测定义时持久化该对象名。

创建压测定义示例：

```bash
curl -X POST "$BASE_URL/api/v1/performance/tests" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "name": "homepage smoke",
    "executor": "k6",
    "script_object_name": "performance/scripts/1/example-homepage.js",
    "default_options": {
      "env": {
        "TARGET_URL": "https://example.test"
      }
    }
  }'
```

触发执行示例：

```bash
curl -X POST "$BASE_URL/api/v1/performance/tests/1/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "environment_id": null,
    "performance_node_id": null,
    "options": {
      "env": {
        "TARGET_URL": "https://example.test"
      }
    }
  }'
```

## 结果契约

k6 `summary.json` 解析到平台字段：

| 平台字段 | k6 指标 |
|----------|---------|
| `rps` | `http_reqs.rate` |
| `p95_ms` | `http_req_duration.percentiles.p(95)` |
| `p99_ms` | `http_req_duration.percentiles.p(99)` |
| `error_rate` | `http_req_failed.rate` |
| `iterations` | `iterations.count` |
| `data_received` | `data_received.count` |
| `data_sent` | `data_sent.count` |

Locust aggregate CSV 使用相同的平台字段：`Requests/s` → `rps`，`95%/95%ile` → `p95_ms`，
`99%/99%ile` → `p99_ms`，`Failure Count / Request Count` → `error_rate`，`Request Count` → `iterations`。
Locust 可选 `thresholds` 使用 `{ "p95_ms": ["<500"], "error_rate": ["<0.01"] }` 形式，结果同样进入阈值门禁。

threshold 结果单独记录为 `thresholds`，用于 UI 展示“性能门禁是否通过”，不写入功能测试 pass/fail 口径。

## 安全边界

- 脚本不得提交明文密钥；认证信息通过环境变量或现有全局变量能力注入。
- 限制脚本大小、最大 duration、最大 VUs。
- 第一阶段仅支持 HTTP/HTTPS 目标，不支持本机文件读取或任意系统命令。
- 生产环境增加目标域名 allowlist，避免误压内部敏感服务。
- 原始结果产物进入 MinIO，按项目权限控制访问。

## Demo 验证

仓库内置最小脚本：`examples/performance/k6-smoke.js`。

脚本内容：

```javascript
import http from "k6/http";
import { sleep } from "k6";

export const options = {
  vus: 5,
  duration: "30s",
  thresholds: {
    http_req_duration: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  http.get(__ENV.TARGET_URL);
  sleep(1);
}
```

本地验证命令：

```bash
k6 run --summary-export result.json examples/performance/k6-smoke.js
```

联调环境建议命令：

```bash
TARGET_URL=https://test.k6.io/ k6 run --summary-export result.json examples/performance/k6-smoke.js
```

当前仓库提供真实 demo summary 样例：`docs/fixtures/performance-k6-summary.sample.json`。该样例用于锁定解析契约。

当前执行状态：

- 本地 Windows 环境没有全局 `k6` 与 Docker CLI，已下载便携版 `k6 v0.52.0` 到临时目录执行 demo。
- 已用 `examples/performance/k6-smoke.js` 生成真实 `result.json`，并回填到 `docs/fixtures/performance-k6-summary.sample.json`。
- 真实 k6 summary 中 threshold 布尔值表示“是否 crossed/失败”，后端解析统一归一为 `{ "ok": true/false }` 供 UI 展示。

API/worker 解析以 `result.json` 的 `metrics.http_req_duration`、`metrics.http_req_failed` 和 `metrics.http_reqs` 作为核心样例。

## 已落地文件

- `backend/app/models/performance.py`
- `backend/app/schemas/performance.py`
- `backend/app/api/v1/performance.py`
- `backend/app/services/performance.py`
- `backend/app/services/performance_executor.py`
- `backend/app/services/performance_process.py`
- `backend/app/services/performance_locust.py`
- `backend/app/services/performance_grpc.py`
- `backend/app/services/performance_report.py`
- `backend/app/services/performance_runtime.py`
- `backend/app/services/performance_schedule.py`
- `backend/app/worker/tasks_performance.py`
- `backend/alembic/versions/20260529_0036_add_performance_tests.py`
- `backend/alembic/versions/20260529_0041_add_performance_baseline_schedule.py`
- `scripts/performance-gate.py`
- `backend/Dockerfile.worker` 通过 `grafana/k6:0.52.0` stage 复制 k6 二进制。
- `examples/performance/k6-smoke.js`
- `docs/fixtures/performance-k6-summary.sample.json`

## Q16 升级计划（2026-08-06）

当前薄切能力适合工程师上传 k6 脚本做接口基准压测，但对普通测试人员仍偏简单：请求配置需要写在脚本中，options 需要手写 JSON，环境选择也尚未自动注入变量。Q16 按以下顺序升级：

### Phase 1：可视化场景与环境联动

- 可视化配置 URL、Method、Headers、Params、Body、认证和基础检查。
- 提供 smoke、load、stress、spike、soak 模板，自动生成 k6 脚本；高级用户仍可上传手写 `.js/.mjs`。
- 选择 `Environment` 后自动加载环境变量；敏感变量仅在 worker 执行时解密，不写入可查询的执行快照。
- URL、请求头、参数和请求体支持 `{{VARIABLE_NAME}}` 占位符。
- 前端脚本生成器、API 环境注入和执行契约补回归测试。

### Phase 2：运行与报告

- [x] 执行状态自动刷新、基于压测时长的进度估算、状态摘要和安全停止。
- [x] 结果 JSON/CSV 导出、报告摘要和阈值门禁可读性。
- [x] 基线回归、CI/定时触发和更完整的门禁策略：成功运行可设为基线；定义级 Cron 按时区触发且避免同一压测重叠；CI 可通过 API Key 触发并轮询阈值门禁。

### Phase 3：专业能力

- Q16-09：关联 CPU、内存、PostgreSQL、Redis、MinIO 等系统指标并与压测时间线关联。
- Q16-10：支持分布式压测节点、节点级 VU/并发约束、应用层目标 allowlist 和可选 Kubernetes Egress NetworkPolicy；运行与定时任务可绑定节点队列，前端展示节点状态和资源容量。
- 已接入 Locust/gRPC 执行器，并完成数据集参数化和复杂用户行为编排；后续重点是 Linux/Kubernetes 目标服务联调与真实压测基线。

本次开发已落地 Phase 1，并完成 Q16-06/Q16-07/Q16-08/Q16-09：保持现有 PerformanceTest / PerformanceRun 数据模型和 k6 队列契约兼容；新增 performanceScriptGenerator 与可视化创建模式；触发 run 时校验环境归属，敏感环境变量不写入 options_snapshot，由 performance worker 在执行时解密注入；run_k6_script 通过 ATP_K6_OPTIONS 将可视化压力配置传给生成脚本。Q16-06 增加了 `cancelling` 状态、Redis 取消标记、k6 子进程安全终止、前端 2 秒轮询和进度估算；Q16-07 增加了安全 JSON/CSV 报告导出、脱敏快照、阈值门禁汇总和可读状态行；Q16-08 增加了持久化基线、核心指标回归对比、按时区的 Cron 调度、重叠运行保护、API Key CI 触发和门禁轮询脚本；Q16-09 增加了 worker 资源指标采样、按 run 关联的持久化样本、Prometheus gauge、资源查询 API 和详情时间线。

## 下一步计划

Q16-10/Q16-11 已完成：新增节点注册/心跳、节点队列路由、VU/并发/目标出口约束、性能中心节点状态与节点选择、Helm NetworkPolicy、Locust/gRPC 执行器、数据集参数化和复杂用户行为编排。Q17-02 已完成本地实现，Q17-03 已补齐 Linux/Kubernetes 验收工具、Worker 镜像依赖校验、专用 Worker 健康探针和 ARM64 Docker Compose 隔离验收栈；下一阶段是在目标主机上启动隔离栈，执行真实 gRPC/Locust smoke、取消和资源采样并保存验收证据。

- [x] Worker 单测覆盖 k6 执行成功、k6 非零退出、未生成 summary 三类路径。
- [x] API 行为测试覆盖压测定义创建、触发 run、重名冲突与缺失定义 404。
- [x] Worker 镜像补 k6 安装，Compose / Helm 文档写明 performance worker 独立部署。
- [x] 前端新增压测中心页面：定义列表、触发执行、run 指标摘要与详情抽屉。
- [x] 新增 k6 脚本上传接口并接入前端表单自动回填对象名。
- [x] 补齐最小 k6 demo 脚本与 summary 样例，解析测试覆盖样例契约。
- [x] 前端详情抽屉展示 threshold 状态，并提供 raw summary 预签名访问入口。
- [x] 执行一次最小 k6 demo，回填真实 `summary.json` 样例。
- [x] Q9 Phase 4 补齐安全限制、独立 performance worker Helm 示例、趋势/对比 UI 与 raw summary 清理策略验证。
- [x] Q16-06 执行控制：压测运行状态自动刷新、进度展示、停止确认与 worker 安全终止；补齐 API、worker、runner 回归测试。
- [x] Q16-07 结果导出、报告摘要和阈值门禁可读性：新增 JSON/CSV 导出接口，导出复用脱敏运行快照，详情抽屉展示通过/失败门禁计数。
- [x] Q16-08 基线对比、定时执行和 CI 阈值门禁：成功 run 可设置为性能基线，详情展示 RPS/P95/P99/错误率方向；定义级 Cron 使用配置时区、Environment 与 options；`scripts/performance-gate.py` 通过 `WEBHOOK_API_KEY` 触发压测并以退出码承接门禁结果。
- [x] Q16-10 分布式压测节点：节点注册/心跳、队列绑定、VU/并发/目标出口约束、性能中心节点状态与节点选择、Helm NetworkPolicy 配置及回归测试。

## 2026-08-07 调度与执行器修复

- 性能调度检查、专用节点心跳和共享控制任务统一使用 `performance` 队列；专用 Worker 同时监听 `performance.<node>` 与共享队列，节点压测任务仍按节点队列隔离。
- Worker 启动后通过 `worker_ready` 启动自调度心跳，心跳任务在数据库短暂故障后仍会重新排队；空闲节点不会因只在执行压测时刷新心跳而被误判为离线。
- Webhook 按压测定义的 `executor` 执行校验和节点能力选择；Locust `run_time`、gRPC `duration_seconds` 纳入运行进度估算；定时任务跳过活动 run 时会持久化下一次执行时间。
- 本轮定向回归共 `93 passed`，性能服务与任务回归 `46 passed`；Ruff、格式检查和 `git diff --check` 通过。完整 Worker 套件仍有 8 个既有测试桩隔离失败，未作为本轮通过证据。
