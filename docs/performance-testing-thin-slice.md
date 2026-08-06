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

## 数据模型草案

`PerformanceTest`：

| 字段 | 说明 |
|------|------|
| `id` | 压测脚本定义 ID |
| `project_id` | 所属项目 |
| `name` | 压测名称 |
| `executor` | 第一阶段固定为 `k6` |
| `script_object_name` | MinIO 脚本对象路径 |
| `default_options` | k6 options JSON，例如 VUs、duration、thresholds |
| `creator_id` | 创建人 |

`PerformanceRun`：

| 字段 | 说明 |
|------|------|
| `id` | 压测执行 ID |
| `performance_test_id` | 关联脚本定义 |
| `environment_id` | 目标环境 |
| `status` | `pending/running/success/failed/cancelled` |
| `started_at/finished_at` | 执行时间 |
| `summary` | 平台标准摘要指标 |
| `raw_result_object_name` | k6 summary JSON 产物路径 |
| `error_message` | 失败原因 |

## API 草案

- `POST /api/v1/projects/{project_id}/performance/scripts`：上传 k6 脚本，返回 `script_object_name`。
- `POST /api/v1/performance/tests`：创建压测脚本定义。
- `GET /api/v1/projects/{project_id}/performance/tests`：查询项目下压测脚本列表。
- `POST /api/v1/performance/tests/{id}/run`：触发一次压测。
- `GET /api/v1/performance/runs/{id}`：查看压测执行详情。
- `GET /api/v1/performance/runs?project_id={project_id}`：查询项目下压测执行列表。

脚本上传约定：

- 第一阶段仅支持 `.js` / `.mjs` k6 脚本。
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
- `backend/app/worker/tasks_performance.py`
- `backend/alembic/versions/20260529_0036_add_performance_tests.py`
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

- 执行状态自动刷新、进度/日志摘要和安全停止。
- 结果导出、基线回归、阈值门禁和 CI/定时触发。

### Phase 3：专业能力

- 关联系统资源指标，支持独立压测节点和分布式压测。
- 评估 Locust/gRPC 等执行器，增加数据集参数化和复杂用户行为编排。

本次开发已落地 Phase 1，保持现有 PerformanceTest / PerformanceRun 数据模型和 k6 队列契约兼容：新增 performanceScriptGenerator 与可视化创建模式；触发 run 时校验环境归属，敏感环境变量不写入 options_snapshot，由 performance worker 在执行时解密注入；run_k6_script 通过 ATP_K6_OPTIONS 将可视化压力配置传给生成脚本。Q16-06 至 Q16-11 仍待后续迭代。

## 下一步计划

- [x] Worker 单测覆盖 k6 执行成功、k6 非零退出、未生成 summary 三类路径。
- [x] API 行为测试覆盖压测定义创建、触发 run、重名冲突与缺失定义 404。
- [x] Worker 镜像补 k6 安装，Compose / Helm 文档写明 performance worker 独立部署。
- [x] 前端新增压测中心页面：定义列表、触发执行、run 指标摘要与详情抽屉。
- [x] 新增 k6 脚本上传接口并接入前端表单自动回填对象名。
- [x] 补齐最小 k6 demo 脚本与 summary 样例，解析测试覆盖样例契约。
- [x] 前端详情抽屉展示 threshold 状态，并提供 raw summary 预签名访问入口。
- [x] 执行一次最小 k6 demo，回填真实 `summary.json` 样例。
- [x] Q9 Phase 4 补齐安全限制、独立 performance worker Helm 示例、趋势/对比 UI 与 raw summary 清理策略验证。
