# ATP Q2 优化执行计划（落地版）

> 生成日期：2026-04-03
> 用途：作为跨设备、跨会话可持续推进的统一执行清单
> 适用范围：基于当前代码现状，对 Q2 相关优化方向进行收敛、排序和落地说明

---

## 1. 背景

仓库内现有两份 Q2 规划文档：

- `docs/implementation-plan-2026-Q2.md`
- `docs/implementation-plan-2026-Q2-detail.md`

两份文档存在以下差异：

1. 总规划版范围更大，包含批量操作、AI 用例生成、i18n
2. 详细版更聚焦当前阶段，主要围绕 A/B/C/D 四个方向
3. 部分文档描述与当前代码实现不完全一致
   - 实际运行详情页文件是 `frontend/src/views/run/RunDetail.vue`
   - 实际套件配置入口在 `frontend/src/views/suite/SuiteList.vue`
   - 当前已存在请求级 `trace_id` 中间件：`backend/app/middleware/trace.py`
   - 当前统计接口已存在基础 Redis 缓存：`backend/app/api/v1/statistics.py`
   - 当前已存在基础 MinIO 清理任务：`backend/app/worker/tasks_cleanup.py`

因此，本执行计划以 **detail 版为主**，再结合代码现实做进一步收敛。

---

## 2. 本轮最终范围

本轮执行范围确定为以下四个方向：

### B. 看板 Redis 缓存 + 数据库索引优化
目标：降低 Dashboard 高频统计接口对数据库的压力，提升页面响应稳定性。

### D. 存储清理增强（保守落地版）
目标：把当前“只删对象、不管 DB 引用”的清理逻辑升级为“先识别、可预览、再安全清理”。

### C. 执行链路追踪增强（轻量关联版）
目标：把现有 HTTP trace_id 扩展到执行链路，先做到“可关联、可定位”，不引入完整 tracing 平台。

### A. 套件并发执行控制（保守版）
目标：在不破坏现有 suite/plan 执行一致性的前提下，逐步提升套件执行效率。

---

## 3. 暂缓范围

以下内容明确不纳入本轮落地：

- 批量操作
- AI 用例生成
- 前端 i18n
- Redis Stream 全量 trace 存储
- Jaeger / OpenTelemetry 全链路 tracing
- plan 级并发执行扩展
- 历史运行记录的大规模自动删除
- 分级存储 / 冷热分层迁移

---

## 4. 实施顺序

### Phase 0：文档与共享约定校准
先统一术语、文件路径、共享 contract，减少后续返工。

已完成项：
- 抽出 tracing helper：`backend/app/core/tracing.py`
- 抽出 object ref helper：`backend/app/core/object_refs.py`
- `TraceMiddleware` 改为复用 tracing helper：`backend/app/middleware/trace.py`
- 日志配置改为复用 tracing helper，并兼容已有 root handlers：`backend/app/core/logging.py`
- `exports` 改为复用共享 object ref helper，并修复 HTML 报告转义与对象变异问题：`backend/app/api/v1/exports.py`
- 修正规划文档中的部分错误路径和实现假设

### Phase 1：方向 B
优先落地统计缓存统一、缓存失效、索引优化。

### Phase 2：方向 D
在现有清理任务基础上，做 preview-first 的 DB-aware 清理链路。

### Phase 3：方向 C
把 trace_id 透传到触发接口、Celery worker、运行记录和诊断视图。

### Phase 4：方向 A
最后推进套件执行优化；顺序模式仍保留为默认值。

---

## 5. 共享实现约定

### 5.1 trace_id 约定

统一使用：
- `backend/app/core/tracing.py`

当前约定：
- HTTP 请求阶段由 `TraceMiddleware` 生成 trace_id
- 日志通过 `get_trace_id()` 读取
- 后续 case / suite / plan trigger 接口需要把 trace_id 透传到 worker
- 后续优先持久化到 `TestRun` / `SuiteRun` / `PlanRun` 的字段或最小可用关联结构中

### 5.2 MinIO 对象引用约定

统一使用：
- `backend/app/core/object_refs.py`

当前约定：
- DB 中长期保存对象引用时，优先保存 object key
- presigned URL 只用于展示/下载，不作为长期唯一来源
- 历史遗留字段若已保存 URL，统一通过 `extract_object_name()` 做兼容解析

---

## 6. 各方向落地说明

---

## 6.1 方向 B：看板 Redis 缓存 + 数据库索引优化

### 目标
提升 Dashboard 页面统计接口响应稳定性，降低数据库压力。

### 当前现状
- 统计接口已存在基础缓存：`backend/app/api/v1/statistics.py`
- Redis JSON cache helper 已存在：`backend/app/core/redis_client.py`
- Dashboard 会并行请求多个统计接口：`frontend/src/views/dashboard/DashboardView.vue`
- 当前索引覆盖不完整，尤其是统计相关组合条件

### 核心文件
- `backend/app/api/v1/statistics.py`
- `backend/app/core/redis_client.py`
- `backend/app/worker/tasks.py`
- `backend/alembic/versions/`（新增索引迁移）
- `frontend/src/views/dashboard/DashboardView.vue`
- `backend/tests/api/test_statistics.py`

### 执行步骤
1. 统一 statistics 缓存读写逻辑
2. 增加缓存异常时的安全降级
3. 增加统计缓存失效机制
4. 新增统计相关复合索引
5. 视需要补充存储统计 API，为方向 D 复用

### 当前已完成
- `backend/app/api/v1/statistics.py` 已改为 best-effort cache read/write，Redis 异常不会中断统计接口
- `backend/app/worker/tasks.py` 已在 case / suite / plan 终态后失效 `atp:stats:*`
- 已新增索引迁移：`backend/alembic/versions/20260403_0015_add_stats_indexes.py`

### 收尾阶段（更完整版）
目标：补齐 **非 worker 写路径** 导致的统计缓存陈旧问题，并补足聚焦测试。

#### 本轮新增范围
- 在 API 层补一个 best-effort 的 stats cache invalidation helper
- 在真正影响统计结果的管理写接口上，增加 post-commit invalidation
- 补齐 statistics 聚焦测试，覆盖尚未补到的趋势接口与 DB 聚合路径

#### 计划接入的写接口
- `backend/app/api/v1/cases.py`
  - `create_case`
  - `copy_case`
  - `delete_case`
- `backend/app/api/v1/projects.py`
  - `create_project`
  - `delete_project`
  - `create_module`
  - `delete_module`

#### 本轮暂不扩大
- `update_case` / `update_project` / `update_module`
- case review workflow
- suite / plan CRUD 侧额外 invalidation
- project 维度精细化 key 删除

### 推荐索引候选
- `test_runs(status, created_at)`
- `test_runs(triggered_by, created_at)`
- `suite_runs(status, created_at)`
- `plan_runs(status, created_at)`
- 视查询形态复核 `modules.project_id` 等 join 列

### 验证
- `backend/tests/api/test_statistics.py`
- `backend/tests/api/test_case_management_api.py`
- `backend/tests/api/test_projects_modules.py`
- `backend/tests/worker/test_tasks_stats_invalidation.py`
- Redis 异常时统计接口与管理写接口仍可用
- Dashboard 多接口加载前后响应对比
- Alembic upgrade/downgrade 正常

---

## 6.2 方向 D：存储清理增强

### 目标
把现有 MinIO 清理逻辑升级为“预览 → 确认 → 执行”的安全清理模式，并避免 DB 留下坏引用。

### 当前现状
- 已存在基础清理任务：`backend/app/worker/tasks_cleanup.py`
- 当前只按 prefix + 时间删除对象
- 当前 DB 中存在截图/视频/报告等对象引用，且部分是 URL、部分是 object key
- 删除对象后，现有 DB 引用可能失效

### 核心文件
- `backend/app/worker/tasks_cleanup.py`
- `backend/app/core/minio_client.py`
- `backend/app/core/object_refs.py`
- `backend/app/api/v1/exports.py`
- `backend/app/worker/tasks.py`
- `backend/app/api/v1/storage.py`（预计新增）
- `frontend/src/views/system/StorageManagementView.vue`（预计新增）
- `frontend/src/router/index.ts`
- `frontend/src/layouts/MainLayout.vue`

### 执行步骤
1. 统一对象引用格式
2. 扩展清理逻辑为 preview-first
3. 增加 DB-aware 引用修复/置空逻辑
4. 增加存储管理 API
5. 增加前端存储管理页面

### 本轮不做
- 分级存储
- 历史运行记录大规模自动删除
- 复杂 max_size 淘汰策略

### 验证
- 预览结果与实际执行一致
- 执行后 DB 不残留明显坏引用
- 导出/缺陷附件等历史流程回归正常
- 管理接口权限正确

---

## 6.3 方向 C：执行链路追踪增强

### 目标
把现有请求级 trace_id 扩展到执行链路，先做到“请求 → 触发接口 → Celery → Worker → Run 详情”的最小闭环。

### 当前现状
- 请求级 trace_id 中间件已存在：`backend/app/middleware/trace.py`
- 日志已支持 trace_id：`backend/app/core/logging.py`
- 尚未透传到 case/suite/plan 的 Celery task
- 运行记录模型中尚无显式 trace_id 字段

### 核心文件
- `backend/app/core/tracing.py`
- `backend/app/middleware/trace.py`
- `backend/app/core/logging.py`
- `backend/app/api/v1/cases.py`
- `backend/app/api/v1/suites.py`
- `backend/app/api/v1/plans.py`
- `backend/app/worker/tasks.py`
- `backend/app/models/case.py`
- `backend/app/models/suite.py`
- `backend/app/models/plan.py`
- `frontend/src/views/run/RunDetail.vue`
- `frontend/src/api/index.ts`

### 执行步骤
1. trigger 接口透传 trace_id
2. worker 任务记录结构化日志
3. 持久化最小 trace 关联信息
4. RunDetail 展示 trace 诊断信息
5. 如确有必要，再增加只读 trace API

### 本轮不做
- Redis Stream trace events
- Jaeger / OpenTelemetry
- span 级完整存储与展示

### 验证
- 触发接口返回/透出 trace_id
- 日志中可按 trace_id 串联任务
- RunDetail 可展示关联 trace 信息
- 失败路径 trace_id 不丢失

---

## 6.4 方向 A：套件并发执行控制

### 目标
在保持默认顺序执行的前提下，为 suite 提供保守的并发执行能力。

### 当前现状
- 当前 `run_test_suite` 为顺序执行：`backend/app/worker/tasks.py`
- plan 依赖 suite 的同步完成语义
- `SuiteRun.case_run_ids`、`PlanRun.suite_run_ids` 都是 JSON 聚合结构
- 当前前端套件配置入口在 `frontend/src/views/suite/SuiteList.vue`

### 核心文件
- `backend/app/worker/tasks.py`
- `backend/app/models/suite.py`
- `backend/app/models/plan.py`
- suite 相关 schemas / APIs
- `frontend/src/views/suite/SuiteList.vue`
- `frontend/src/api/index.ts`

### 执行步骤
1. 提取 suite 执行公共逻辑
2. 扩展 `Suite.config`
3. 增加 suite 级并发配置
4. 采用 bounded concurrency / 分批策略
5. 前端补套件执行策略配置 UI
6. 如后端聚合稳定，再考虑套件运行进度展示

### 配置建议
```json
{
  "execution_mode": "sequential | parallel",
  "max_workers": 5,
  "fail_strategy": "fast-fail | continue | require-minimum-pass-rate",
  "min_pass_rate": 0.8
}
```

### 本轮限制
- sequential 仍为默认
- 仅先支持 suite 级并发
- 暂不做 plan 级并发

### 验证
- sequential 行为保持不变
- parallel 汇总正确
- fail strategy 正确生效
- plan 执行流程不被破坏
- 前端配置表单默认值/显隐逻辑正确

---

## 7. 风险与兜底策略

### 高风险 1：suite/plan 聚合状态一致性
风险来源：当前是 JSON 聚合，不是关系型子任务模型。

兜底：
- 顺序模式保留默认
- 先不做 plan 级并发
- 先完成 trace 增强，再推进并发

### 高风险 2：对象引用格式不统一
风险来源：有 object key，也有 presigned URL。

兜底：
- 统一走 `extract_object_name()`
- preview-first，先不直接全量删

### 高风险 3：统计缓存失效过粗或过频
风险来源：失效策略不合理会导致缓存收益下降。

兜底：
- 优先 namespace/project 维度失效
- 先覆盖终态写入场景

### 高风险 4：trace 方案过重
风险来源：引入完整 tracing 平台会拉高复杂度。

兜底：
- 本轮只做 trace_id 关联链路
- 完整 tracing 能力后续独立评估

---

## 8. 建议的开发顺序

按以下顺序推进：

1. Phase 0 收尾与共享 contract 固化
2. 方向 B
3. 方向 D
4. 方向 C
5. 方向 A

---

## 9. 验证清单

### Backend
```bash
python -m pytest backend/tests -q
```

建议按方向补充聚焦测试：
- statistics
- cleanup
- trace
- suite execution

### Frontend
```bash
cd frontend && npm run type-check
cd frontend && npm run build
```

### 手工验证
1. Dashboard 切换筛选条件，观察统计加载性能
2. 预览并执行一次存储清理，检查对象与 DB 状态一致性
3. 触发 case / suite / plan 执行，验证 trace_id 可追踪
4. 执行一个启用并发配置的 suite，核对汇总结果

---

## 10. 当前进度记录

### 已完成
- Phase 0 基础对齐已完成
- 共享 tracing helper 已建立
- 共享 object ref helper 已建立
- 相关基础测试已补充并通过

### 进行中
- 方向 B：统计缓存统一、缓存失效、索引优化

### 待开始
- 方向 D
- 方向 C
- 方向 A
