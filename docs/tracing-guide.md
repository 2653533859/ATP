# 链路追踪（OpenTelemetry + Jaeger）使用指南

> 适用版本：2026 Q3 收口（方向 G）之后

## 1. 概述

ATP 在 Q2 完成了**应用层 `trace_id` 关联链路**（请求 → Celery → Worker → Run 记录），
在 Q3 方向 G 中升级为**完整分布式 tracing**：

- 通过 OpenTelemetry SDK + Jaeger 提供 span 级耗时、嵌套调用、跨进程上下文
- 现有 application `trace_id`（持久化在 `TestRun.trace_id` / `SuiteRun.trace_id` /
  `PlanRun.trace_id` 字段、HTTP 响应头 `X-Trace-ID`、前端 Trace 面板展示）**全部保留**
- 在每个 OTel span 中通过 attribute `app.trace_id` 关联两者，便于在 Jaeger UI
  里按业务 trace_id 反查

## 2. 两类 trace ID 的关系

| 项 | application `trace_id` | OpenTelemetry TraceID |
|----|------------------------|------------------------|
| 长度 | 16 字符 hex（UUID 前半） | 32 字符 hex（W3C 标准） |
| 生成位置 | `app/middleware/trace.py` HTTP 入口 | OTel SDK 在第一个 span 上自动生成 |
| 持久化 | 写入 `TestRun.trace_id` 等 DB 字段 | 仅 Jaeger 后端存储 |
| 前端展示 | RunDetail 页面 "Trace ID" 字段 | "在 Jaeger 中打开" 按钮跳转 |
| 跨进程传播 | 显式作为 Celery 任务参数透传 | `opentelemetry-instrumentation-celery` 自动 W3C TraceContext |

**关联机制**：worker 的每个 task 入口调用
`attach_app_trace_id_to_current_span(run.trace_id)`，把 application trace_id
写入当前 OTel span 的 `app.trace_id` attribute。Jaeger UI 可通过
`tags={"app.trace_id":"<id>"}` 反查。

## 3. 启用方式

OTel 默认**关闭**——backend / worker 启动时若环境变量
`OTEL_EXPORTER_OTLP_ENDPOINT` 为空字符串，则跳过初始化，所有 OTel 调用降级为
no-op，运行时无副作用。

### 3.1 Docker Compose 一键启用

`docker-compose.yml` 已内置 jaeger 服务（`jaegertracing/all-in-one:1.62`），
backend / worker 默认指向 `http://jaeger:4317`。直接：

```bash
docker compose up -d
```

启动后访问：

- Jaeger UI: `http://localhost:16686`
- OTLP gRPC 端点：`jaeger:4317`（容器内） / `localhost:4317`（宿主机）

### 3.2 关闭 OTel（开发环境只想验证业务逻辑时）

在 `.env` 中显式置空：

```env
OTEL_EXPORTER_OTLP_ENDPOINT=
JAEGER_UI_URL=
```

此时 Jaeger 容器仍可正常启动，但不会接收数据；前端 "在 Jaeger 中打开"
按钮隐藏。

### 3.3 本地 backend / worker 进程启用

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_SERVICE_NAME=atp-backend          # worker 用 atp-worker
export OTEL_TRACES_SAMPLER=parentbased_traceidratio
export OTEL_TRACES_SAMPLER_ARG=0.1            # 10% 采样
export JAEGER_UI_URL=http://localhost:16686   # 前端按钮基础 URL
uvicorn app.main:app --reload --port 8000
```

## 4. 配置项说明（`backend/app/core/config.py`）

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `""` | OTLP gRPC 端点。空 = 不启用 OTel |
| `OTEL_SERVICE_NAME` | `atp-backend` | `service.name` resource attribute，Jaeger 服务下拉框显示 |
| `OTEL_TRACES_SAMPLER` | `parentbased_traceidratio` | 采样器，可选 `traceidratio` |
| `OTEL_TRACES_SAMPLER_ARG` | `0.1` | 比例采样参数，0~1 之间 |
| `JAEGER_UI_URL` | `""` | 前端 "在 Jaeger 中打开" 链接基础 URL，空则隐藏按钮 |

## 5. Jaeger UI 检索

### 按业务 trace_id 反查（推荐）

1. 进入 Jaeger UI: `http://localhost:16686`
2. **Service** 选择 `atp-backend` 或 `atp-worker`
3. **Tags** 输入：`app.trace_id=<run.trace_id>`（前端 RunDetail 可直接复制）
4. 点击 **Find Traces** 即可看到完整 span 树

### 直接点击前端按钮

`RunDetail` 页面 trace_id 字段右侧有 "在 Jaeger 中打开" 链接，自动用
`tags={"app.trace_id":"<id>"}` 拼出 URL 跳转。

### 已埋点的 span 名称

| Span 名称 | 来源 | 主要 attribute |
|-----------|------|-----------------|
| `GET /api/v1/...` | FastAPI 自动 instrumentation | `http.method` / `http.route` / `http.status_code` |
| `run_test_case` / `run_test_suite` / `run_test_plan` | Celery 自动 instrumentation | `celery.task` / `celery.action` / `app.trace_id` |
| `executor.api` / `executor.web.lowcode` / `executor.android` ... | `case_dispatch.py` 手动 | `case.id` / `case.type` / `run.id` / `run.environment` / `app.trace_id` |
| `step.{idx}` | `api_executor.py` 手动（典型接口用例） | `step.index` / `step.name` / `http.request.method` / `http.url` / `http.response.status_code` / `step.status` / `step.duration_ms` |

> 当前仅 `api_executor` 做了 step 级细粒度埋点；其他 executor（graphql / websocket /
> grpc / web / android 系列）目前停留在 `executor.{type}` 级别。后续可按需补全。

## 6. 采样与性能影响

- 默认采样率 10%（`OTEL_TRACES_SAMPLER_ARG=0.1`），即每 10 个 root trace 仅
  完整记录 1 个
- 单个 step span 实测约 0.3~0.6ms 额外开销（包含 attribute 设置、context 切换、
  BatchSpanProcessor 入队）
- 失败链路目前不强制采样；如需 tail-based sampling，可后续通过 OTel Collector
  + Sampling Processor 实现（本期未做）

## 7. dev / prod 行为差异

| 场景 | endpoint 配置 | 采样率建议 |
|------|--------------|-----------|
| 本地开发 | 空 或 `http://localhost:4317` | 100%（`OTEL_TRACES_SAMPLER_ARG=1.0`）方便排查 |
| Docker Compose | `http://jaeger:4317`（默认） | 10% 或更高 |
| 生产环境 | 内部 Collector / Tempo / SaaS endpoint | 1~10%（视 QPS 与存储成本） |

## 8. 排查清单

- **Jaeger UI 看不到任何 trace**：
  1. 检查 `OTEL_EXPORTER_OTLP_ENDPOINT` 是否正确
  2. 检查 jaeger 容器日志 `docker compose logs jaeger`，确认 `COLLECTOR_OTLP_ENABLED=true`
  3. 检查采样率是否过低
- **前端按钮不出现**：
  1. 后端 `JAEGER_UI_URL` 是否配置
  2. `GET /api/v1/traces/config` 是否返回非空 `jaeger_ui_url`
- **worker 没产生 span**：
  1. worker 是 pre-fork 模型，OTel 在 `worker_process_init` 信号中初始化；
     需要保证 worker 用默认的 prefork pool（非 solo）
  2. `celery -A app.worker.celery_app worker -l info`，查看启动日志是否打印
     `OTEL tracer initialized`

## 9. 关键源码索引

| 文件 | 作用 |
|------|------|
| `backend/app/core/otel.py` | `init_tracer` / `shutdown_tracer` / `get_tracer`，endpoint 为空时降级 no-op |
| `backend/app/core/tracing.py` | 既有 application `trace_id` 实现 + 新增 `attach_app_trace_id_to_current_span` |
| `backend/app/main.py` | FastAPI lifespan 初始化 + `FastAPIInstrumentor.instrument_app` |
| `backend/app/worker/celery_app.py` | `worker_process_init` 信号初始化 + `CeleryInstrumentor` |
| `backend/app/worker/case_dispatch.py` | `executor.{type}` 手动 span |
| `backend/app/worker/executors/api_executor.py` | `step.{idx}` 手动 span 示例 |
| `backend/app/api/v1/traces.py` | `GET /traces/config` + `GET /traces/{trace_id}` |
| `frontend/src/views/run/RunDetail.vue` | "在 Jaeger 中打开" 按钮 |
| `docker-compose.yml` | jaeger 服务 + backend / worker 的 OTEL_* 环境变量 |
