# ATP 平台优化扩展实施计划（详细方案）

> 生成日期：2026-04-02
> 优先级：P0=紧急高价值，P1=高价值，P2=中价值

---

## 方向 A：套件并发执行控制 [P1]

### 现状分析

当前 `run_test_suite` (tasks.py:60-163) 使用 `for` 循环串行 `await dispatch_case()` 执行每个用例。套件内有 100 个用例时即使每个仅 10s，总耗时也达 1000s。

关键发现：
- `run_test_case` Celery task 已存在 (tasks.py:21-57)，但套件执行绕过了它，直接调用 `dispatch_case`
- Suite.config 是空 JSON，可以直接扩展，无需新建表
- SuiteRun.case_run_ids 是 JSON 数组存储结果，改造后需要原子更新机制

### 实施步骤

#### A.1 扩展 Suite.config 支持并发配置

**修改文件**: `backend/app/models/suite.py`

```python
# Suite.config 新增字段:
{
    "execution_mode": "sequential" | "parallel",       # 默认 sequential
    "max_workers": 5,                                  # 并发数，默认 5
    "fail_strategy": "fast-fail" | "continue" | "require-minimum-pass-rate",
    "min_pass_rate": 0.8,                               # fail_strategy=require-minimum-pass-rate 时生效
}
```

#### A.2 并发执行实现

**修改文件**: `backend/app/worker/tasks.py` — 重构 `run_test_suite`

核心逻辑：
- sequential 模式：保留现有 for 循环逻辑
- parallel 模式：使用 `run_test_case.delay()` 批量派发任务，用 `celery.group` 等待所有结果

```python
from celery import group, chord

@celery_app.task(bind=True, name="run_test_suite")
def run_test_suite(self, suite_run_id: int, extra_vars: dict):
    # ... 获取 suite_run 和 suite ...

    mode = suite.config.get("execution_mode", "sequential")

    if mode == "parallel":
        max_workers = suite.config.get("max_workers", 5)
        # 分批：每批 max_workers 个
        job = group(
            run_test_case.s(case_run.id, extra_vars)
            for item in case_items
            for case_run in [create_case_run(db, item)]
        )
        # 使用 chord 汇总结果
        result = job.apply_async()
        # 等待 chord 完成，通过 callback 更新 suite_run 状态
    else:
        # 原有串行逻辑
```

关键改造点：
- `create_case_run` 先创建所有 TestRun 记录（批量 INSERT）
- 并发模式下不再 `await dispatch_case`，改为 `run_test_case.delay()`
- 用 Celery `group().apply_async()` 的 `AsyncResult` 轮询或 chord callback 更新 SuiteRun

#### A.3 SuiteRun 状态同步

并发模式下，SuiteRun 无法在 task 返回时同步获取所有子用例状态。方案：

1. **Celery chord callback**：`group().apply_async(link_error=...)` 在所有子任务完成后触发汇总任务
2. **Redis Pub/Sub 监听**：在 `run_test_suite` 启动一个 Redis subscriber 监听所有子用例的 `atp:run:{run_id}` channel，收集完成事件后更新 SuiteRun

推荐方案 1（chord callback），更简洁且不引入额外依赖。

#### A.4 前端交互

**修改文件**: `frontend/src/views/suite/SuiteForm.vue` (或现有编辑表单)

- 套件配置 Tab 增加执行模式选择（顺序/并行）
- 并行模式显示最大并发数输入 + 失败策略选择
- 执行中套件详情页显示并行任务的整体进度

### 里程碑

- [ ] A.1 Suite.config 并发字段扩展
- [ ] A.2 并发执行引擎（Celery group + chord）
- [ ] A.3 SuiteRun 状态同步机制
- [ ] A.4 前端并发配置 UI

---

## 方向 B：看板 Redis 缓存 + 数据库索引优化 [P1]

### 现状分析

统计 API (`statistics.py`) 已有基础缓存机制：
- `_STATS_CACHE_TTL = 180` (3分钟)
- `_cache_key()` 和 `get_json_cache`/`set_json_cache` 已封装
- **问题**：每个接口独立写缓存，没有统一拦截层；索引不完整

关键缺失索引：
- `(status, created_at)` — 统计查询都需要
- `(status, created_at, case_id)` — 失败 Top 查询
- `(triggered_by, created_at)` — 执行人 Top 查询

### 实施步骤

#### B.1 统一缓存拦截层（装饰器模式）

**新增文件**: `backend/app/core/cache_decorator.py`

```python
def cached_stats(ttl: int = 180, key_prefix: str = "stats"):
    """统计接口缓存装饰器，自动生成 cache_key 并处理命中/写入"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 从 kwargs 提取 project_id, days, case_type
            cache_key = _build_key(key_prefix, func.__name__, kwargs)
            cached = await get_json_cache(cache_key)
            if cached:
                return cached
            result = await func(*args, **kwargs)
            await set_json_cache(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
```

应用到所有 8 个统计接口，无需每个接口单独写缓存逻辑。

#### B.2 缓存失效机制

执行完成后清除相关缓存：
- 在 `dispatch_case` 成功后调用 `delete_json_cache_pattern("atp:stats:*")`
- 也可在 Celery task 成功后通过 `on_success` 回调触发（更精确）

#### B.3 数据库索引优化

**新增迁移文件**: `backend/migrations/versions/YYYYMMDD_HHMMSS_add_stats_indexes.py`

```python
# test_runs 复合索引
op.create_index("ix_test_runs_status_created_at", "test_runs", ["status", "created_at"])
op.create_index("ix_test_runs_triggered_created", "test_runs", ["triggered_by", "created_at"])

# SuiteRun / PlanRun 同理
op.create_index("ix_suite_runs_status_created_at", "suite_runs", ["status", "created_at"])
op.create_index("ix_plan_runs_status_created_at", "plan_runs", ["status", "created_at"])
```

#### B.4 MinIO 存储使用量 API

**新增文件**: `backend/app/api/v1/storage.py`

```python
@router.get("/storage/stats")
async def get_storage_stats(_: User = Depends(require_admin)):
    """返回各 bucket/prefix 的对象数量和总大小"""
    from app.core.minio_client import get_client, settings
    # 遍历 screenshots/, reports/, apks/ 前缀，统计 count + size
```

前端已有系统菜单，可新增"存储管理"页面展示饼图。

### 里程碑

- [ ] B.1 统一缓存装饰器
- [ ] B.2 缓存失效机制
- [ ] B.3 统计查询复合索引
- [ ] B.4 MinIO 存储统计 API

---

## 方向 C：执行链路追踪增强 [P0 补充]

### 现状分析

原方案(Q2-方向一)计划用 Redis Stream 存储 trace，但：
- 项目已有 Flower 监控
- Redis DB2 已被 Pub/Sub + 缓存共用，高频 trace 写入可能影响
- 没有 trace_id 注入到 API 层

### 实施步骤（精简版，复用 Flower）

#### C.1 trace_id 注入

**修改文件**: `backend/app/core/tracing.py` (新建)

```python
import uuid
from contextvars import ContextVar

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

def get_trace_id() -> str:
    return trace_id_var.get()

def generate_trace_id() -> str:
    return uuid.uuid4().hex[:16]
```

**修改文件**: `backend/app/api/v1/suites.py`, `cases.py` 等触发接口

在触发执行的接口中注入 `X-Trace-ID` header 并写入响应：
```python
trace_id = generate_trace_id()
trace_id_var.set(trace_id)
# 写入 SuiteRun / TestRun 的 result_summary 中追溯
```

#### C.2 Celery task 日志增强

**修改文件**: `backend/app/worker/tasks.py`

在 `run_test_case` 和 `run_test_suite` 任务开始/结束时记录结构化日志（含 trace_id）：
```python
logger.info(
    "task_start",
    extra={"trace_id": trace_id, "task": "run_test_case", "run_id": run_id}
)
```

#### C.3 执行链路 API

**新增文件**: `backend/app/api/v1/traces.py`

```python
@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str, ...):
    # 从 Redis Stream 读取 trace events
    # 返回格式: {"spans": [{"name": "...", "start": ..., "duration_ms": ...}]}
```

#### C.4 前端 Trace 面板

**修改文件**: `frontend/src/views/run/RunDetailView.vue`

- 新增 "链路追踪" Tab（折叠面板形式）
- 展示时间线：API 触发 → Queue → Worker → 各 Step
- 使用 Redis DB2 轮询（5s 间隔）获取 trace events

### 里程碑

- [ ] C.1 trace_id 注入框架
- [ ] C.2 Task 日志结构化增强
- [ ] C.3 Trace 查询 API
- [ ] C.4 前端 Trace 面板

---

## 方向 D：存储清理增强（MinIO + DB 同步）[P0 补充]

### 现状分析

已有清理机制：
- `cleanup_expired_files` (tasks_cleanup.py:23) — 删除 MinIO 超过 30 天的文件
- `cleanup_stale_pending_runs` (tasks_cleanup.py:88) — 标记超时 pending 记录为 error
- `cleanup_stale_mobile_special_runs` (tasks_mobile_special.py:173) — 清理超时 mobile special runs

关键问题：
1. **MinIO 文件无关联追踪**：截图/报告 URL 存在 DB 字段中（如 `screenshot_url`），删除 MinIO 文件后 DB 记录仍存在，访问时 404
2. **DB 记录无清理**：终态（passed/failed/error）运行记录永远不删除，只清理 pending 超时
3. **配置不灵活**：`FILE_RETENTION_DAYS` 是全局固定值，无法按项目/Bucket 差异化配置
4. **清理无预览**：`cleanup_expired_files` 直接删除，没有管理员确认环节

### 实施步骤

#### D.1 StoragePolicy 数据模型

**新增文件**: `backend/app/models/storage_policy.py`

```python
class StoragePolicy(Base, TimestampMixin):
    __tablename__ = "storage_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]                          # "screenshots", "reports", "apks"
    prefix: Mapped[str]                         # MinIO 对象前缀
    retention_days: Mapped[int] = 30            # 保留天数
    max_size_gb: Mapped[float | None]           # 可选总大小上限
    enabled: Mapped[bool] = True                # 是否启用
```

Alembic 迁移文件初始化 3 条默认记录（screenshots: 30天, reports: 90天, apks: 180天）。

#### D.2 同步清理任务（MinIO + DB）

**修改文件**: `backend/app/worker/tasks_cleanup.py`

重构 `cleanup_expired_files` 为 `cleanup_expired_artifacts`：

```python
@celery_app.task(name="cleanup_expired_artifacts")
def cleanup_expired_artifacts():
    """
    按 StoragePolicy 配置：
    1. 删除 MinIO 过期文件
    2. 清理关联的 DB 记录（screenshot_url 字段设为 None，或删除孤立的 StepResult）
    3. 按 max_size_gb 控制总大小，超出时优先删旧
    """
    # 实现分 3 步：
    # Step 1: 按 policy 删除 MinIO 对象（已有逻辑扩展）
    # Step 2: 清理 DB 孤立引用（扫描 screenshot_url/video_url 对应的 MinIO 对象不存在时置空）
    # Step 3: 记录清理日志到 Redis 或 DB
```

关键：步骤 1 和 2 需要事务一致性 — 删除 MinIO 成功后更新 DB。建议：
- 先更新 DB（screenshot_url = None）
- 再删除 MinIO 文件（失败不影响 DB）
- 最终记录清理报告

#### D.3 DB 运行记录清理

**新增 Celery 任务**: `cleanup_old_completed_runs`

按 `FILE_RETENTION_DAYS` 或 StoragePolicy 清理终态运行记录：

```python
@celery_app.task(name="cleanup_old_completed_runs")
def cleanup_old_completed_runs():
    """
    清理超过保留期限的终态 (passed/failed/error) TestRun + 关联 StepResult
    需要在删除前：
    1. 将关联的 MinIO 文件 URL 从 DB 中清除（或先删除文件再删记录）
    2. 级联删除 StepResult（已有 cascade="all, delete-orphan"）
    """
```

清理顺序：MobileSpecialRun → PlanRun → SuiteRun → TestRun（从叶子到根，避免外键约束）。

#### D.4 前端存储管理页面

**新增文件**: `frontend/src/views/system/StorageManagementView.vue`

- 各 Bucket 存储使用量（饼图，调用 storage stats API）
- 清理策略配置（新增/编辑 StoragePolicy）
- 手动清理触发按钮（POST /api/v1/admin/storage/cleanup-preview → 预览 → 确认执行）
- 清理日志展示

### 里程碑

- [ ] D.1 StoragePolicy 数据模型 + 迁移
- [ ] D.2 同步清理任务（MinIO + DB 一致性）
- [ ] D.3 DB 运行记录清理任务
- [ ] D.4 前端存储管理页面

---

## 实施顺序

```
第1阶段（1周）
  方向 B (看板缓存) → 改动小、收益快、已有基础设施
  方向 D (存储清理) → 防止生产事故

第2阶段（1-2周）
  方向 C (链路追踪) → 提升调试效率
  方向 A (套件并发) → 提升核心执行体验

第3阶段（收口）
  回归测试 + 文档更新
```

---

## 关键文件清单

| 文件 | 操作 | 方向 |
|------|------|------|
| `backend/app/worker/tasks.py` | 修改 | A, C |
| `backend/app/models/suite.py` | 修改 | A |
| `backend/app/worker/tasks_cleanup.py` | 修改 | D |
| `backend/app/api/v1/statistics.py` | 修改 | B |
| `backend/app/core/cache_decorator.py` | 新建 | B |
| `backend/app/core/tracing.py` | 新建 | C |
| `backend/app/api/v1/traces.py` | 新建 | C |
| `backend/app/api/v1/storage.py` | 新建 | B, D |
| `backend/app/models/storage_policy.py` | 新建 | D |
| `backend/migrations/versions/..._add_stats_indexes.py` | 新建 | B |
| `frontend/src/views/run/RunDetailView.vue` | 修改 | C |
| `frontend/src/views/system/StorageManagementView.vue` | 新建 | D |

---

## 验证方法

1. **方向 B (看板缓存)**：用 `ab -n 100 -c 10` 压测统计 API，对比缓存命中/未命中的响应时间
2. **方向 A (套件并发)**：创建 20 个用例的套件，分别用顺序/并行模式执行，对比总耗时
3. **方向 C (链路追踪)**：触发一个执行，查询 `GET /api/v1/traces/{trace_id}` 验证 span 完整性
4. **方向 D (存储清理)**：手动将一个 MinIO 文件的 last_modified 改为 60 天前，触发清理任务，检查文件是否被删除且 DB 记录正确处理
