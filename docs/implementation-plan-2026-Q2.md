# ATP 平台优化扩展实施计划

> 生成日期：2026-04-01
> 优先级说明：P0=紧急高价值，P1=高价值，P2=中价值

---

## 方向一：执行链路追踪 (P0)

### 目标
实现请求 → Celery → Worker → Executor 全链路日志/Trace，排查问题从平均 30min 降到 5min。

### 现状问题
- 执行卡住时无法定位卡在哪一步（API、Celery Queue、Worker、Executor）
- 失败日志分散在多个组件，关联困难
- 无请求级别的上下文 ID

### 实施方案

#### 1.1 请求上下文注入
```
API 层 (api/v1/)        → 生成 trace_id，写入 Redis + 返回给前端
                         → 附加 project_id、case_id、trigger_type 到 context
```

**新增文件：**
- `backend/app/core/tracing.py` — TraceContext 管理
- `backend/app/core/celery_tracing.py` — Celery task 包装器

**修改文件：**
- `backend/app/api/v1/` — 所有 run trigger 接口注入 trace_id
- `backend/app/worker/tasks.py` — Celery task 接收并传递 trace_id

#### 1.2 Celery Task 包装器
```python
@app.task(bind=True, base=TracedTask)
def run_test_case(self, case_id, trace_id=None):
    with start_span("executor.run_test_case") as span:
        span.set_tag("case_id", case_id)
        # 执行逻辑
```

#### 1.3 Executor 阶段埋点
```
executor.start()         → span: executor_start
step.before_run()        → span: step:{step_id}
step.execute_request()   → span: step:{step_id}:execute
step.assert_result()     → span: step:{step_id}:assert
step.extract_vars()       → span: step:{step_id}:extract
executor.finish()        → span: executor_end
```

#### 1.4 Trace 存储与查询
- 使用 Redis Stream 存储 trace 数据（TTL=7天）
- 新增 API：`GET /api/v1/traces/{trace_id}` — 返回完整链路
- 新增 API：`GET /api/v1/traces/{trace_id}/spans` — 返回所有 span
- 前端：运行详情页增加「链路追踪」Tab

#### 1.5 前端展示
- `frontend/src/views/run/RunDetailView.vue` — 新增 Trace 面板
- 展示时间线：API → Queue → Worker → 各 Step 执行时长
- 颜色标识：绿色=成功，红色=失败，灰色=进行中

### 依赖
- Redis Stream（已部署，DB2 可复用）
- Python 包：`opentracing` 或 `structlog`

### 里程碑
- [ ] 1.1 TraceContext 管理模块
- [ ] 1.2 Celery Task 包装器
- [ ] 1.3 各 Executor 阶段埋点
- [ ] 1.4 Trace 存储与查询 API
- [ ] 1.5 前端 Trace 面板

---

## 方向二：批量操作 (P1)

### 目标
用例/套件/计划支持批量导入/导出/复制/移动，减少手工操作时间。

### 实施方案

#### 2.1 用例批量操作 API

**新增接口：**
```
POST   /api/v1/cases/batch         — 批量创建用例
PUT    /api/v1/cases/batch         — 批量更新用例
DELETE /api/v1/cases/batch         — 批量删除用例
POST   /api/v1/cases/batch/copy    — 批量复制用例
POST   /api/v1/cases/batch/move    — 批量移动用例（到其他模块/项目）
GET    /api/v1/cases/batch/export  — 批量导出（ZIP，包含 JSON + 附件）
POST   /api/v1/cases/batch/import  — 批量导入（ZIP）
```

**Request Schema：**
```python
class CaseBatchCopyRequest(BaseModel):
    case_ids: list[int]
    target_module_id: int | None
    target_project_id: int | None  # 跨项目复制
    suffix: str = ""  # 复制后名称后缀
```

#### 2.2 套件批量操作 API

**新增接口：**
```
POST   /api/v1/suites/batch/copy    — 批量复制套件
POST   /api/v1/suites/batch/run     — 批量触发套件执行
DELETE /api/v1/suites/batch         — 批量删除
```

#### 2.3 前端批量操作组件

**新增文件：**
- `frontend/src/components/common/BatchOperationBar.vue` — 通用批量操作栏
  - 显示选中数量、操作按钮（下拉菜单）
  - 跨页多选支持
  - 确认对话框（受影响数量提示）

- `frontend/src/components/common/ImportExportDialog.vue` — 导入导出对话框
  - 支持 CSV 模板下载
  - 支持 ZIP 批量导入
  - 导入预览 + 冲突处理

**修改文件：**
- `frontend/src/views/case/CaseListView.vue` — 集成 BatchOperationBar
- `frontend/src/views/suite/SuiteListView.vue` — 集成 BatchOperationBar
- `frontend/src/views/plan/PlanListView.vue` — 集成 BatchOperationBar

#### 2.4 进度追踪
批量操作耗时较长时：
- 返回 202 Accepted + task_id
- WebSocket 实时推送进度（`atp:batch:{task_id}`）
- 前端显示进度条

### 里程碑
- [ ] 2.1 用例批量 CRUD + 导入导出 API
- [ ] 2.2 套件批量操作 API
- [ ] 2.3 BatchOperationBar 组件
- [ ] 2.4 ImportExportDialog 组件
- [ ] 2.5 前端列表页集成批量操作

---

## 方向三：MinIO 存储清理 (P0)

### 目标
防止 MinIO 磁盘占满导致服务中断，自动清理过期报告/截图。

### 现状问题
- 报告、截图、日志不断积累，无自动清理
- 手动清理需要停机或临时脚本

### 实施方案

#### 3.1 清理策略配置表
新建 `SystemConfig` 或独立表 `storage_policy`：
```python
class StoragePolicy(BaseModel):
    artifact_type: ArtifactType  # report / screenshot / video / log / apk
    max_age_days: int            # 超过此天数删除
    max_size_gb: int | None      # 可选，总大小超限时优先删旧
    bucket: str                  # atp-reports / atp-screenshots / etc.
```

#### 3.2 后台清理任务
新增 Celery Beat 定时任务 `cleanup_expired_artifacts`：
- 每日凌晨 3 点执行
- 按 `max_age_days` 删除过期文件
- 按 `max_size_gb` 控制总大小（超限时按时间倒序删）

#### 3.3 分级存储策略
```
热数据 (30天内)    → MinIO 标准存储
温数据 (31-90天)  → MinIO Glacier 即时取回
冷数据 (90天+)    → 导出到 S3 / 阿里云 OSS（可选）
```

#### 3.4 前端存储管理页面
`frontend/src/views/system/StorageManagementView.vue`：
- 各 Bucket 存储使用量（饼图）
- 清理策略配置
- 手动触发清理
- 清理日志

#### 3.5 告警机制
当存储使用率 > 80% 时：
- 站内信通知管理员
- Dashboard 显示警告

### 里程碑
- [ ] 3.1 存储策略数据模型
- [ ] 3.2 cleanup_expired_artifacts Celery 任务
- [ ] 3.3 分级存储策略（可选）
- [ ] 3.4 前端存储管理页面
- [ ] 3.5 存储告警机制

---

## 方向四：AI 用例生成 (P2)

### 目标
用户上传 API Schema (OpenAPI/Postman) 或页面截图，AI 自动生成测试用例。

### 实施方案

#### 4.1 API Schema 导入
支持格式：OpenAPI 3.x JSON/YAML、Postman Collection v2.1

**前端：**
- `ImportApiSchemaView.vue` — 上传/粘贴 Schema
- 自动解析 endpoints 列表
- 用户选择要生成用例的接口 + 填写测试数据映射

**后端：**
```
POST /api/v1/cases/ai/generate-from-schema
body: { schema_url or schema_text, project_id, module_id, options }
→ 调用 LLM API 生成用例 JSON
→ 返回待确认的用例列表
POST /api/v1/cases/ai/confirm 生成正式用例
```

#### 4.2 页面结构分析（远期）
用户上传截图 → AI 识别页面元素 → 生成 Android Lowcode 步骤

#### 4.3 失败原因分析（远期）
执行失败后 → AI 分析日志/截图 → 输出可能原因 + 修复建议

### 里程碑
- [ ] 4.1 OpenAPI/Postman 解析 + LLM 生成
- [ ] 4.2 生成结果预览 + 批量确认
- [ ] 4.3 失败原因 AI 分析（远期）

---

## 方向五：前端国际化 i18n (P2)

### 目标
支持中英文切换，便于出海团队使用。

### 实施方案

#### 5.1 技术选型
- `vue-i18n` — Vue 3 i18n 解决方案
- 共享后端消息模板（通知邮件等）

#### 5.2 实施步骤
1. 抽取所有中文硬编码到 `frontend/src/locales/zh-CN.ts` 和 `en-US.ts`
2. 路由切换语言，URL 参数 `?lang=en`
3. 登录页/导航栏增加语言切换
4. 后端通知模板支持模板变量

#### 5.3 优先级
优先处理：登录页、导航栏、通用按钮、错误提示
后续处理：各业务页面

### 里程碑
- [ ] 5.1 vue-i18n 集成
- [ ] 5.2 登录页 + 导航栏多语言
- [ ] 5.3 业务页面逐步翻译

---

## 实施顺序建议

```
第一阶段（1-2周）
  方向三(存储清理) P0 → 防止生产事故

第二阶段（2-3周）
  方向一(链路追踪) P0 → 提升调试效率
  方向二(批量操作) P1 → 减少手工操作

第三阶段（长期）
  方向四(AI生成) P2 → 差异化竞争力
  方向五(i18n) P2 → 出海准备
```

---

## 附录：关键技术参考

### 执行链路追踪技术方案
- **OpenTelemetry Python SDK** — 自动 instrumentation
- **Redis Stream** — trace events 存储（vs 内存有限、vs ES 部署重）
- **Jaeger** (可选) — trace 可视化（轻量：单个 docker container）

### 批量操作性能优化
- 数据库：批量 INSERT 用 `copy_expert` / `insert_all`
- 复制用例：异步任务后台执行，前端轮询进度
- 导出 ZIP：流式写入，避免内存峰值

### MinIO 清理命令参考
```python
# 列出过期对象
s3_client.list_objects_v2(Bucket='atp-reports', Prefix='2025/')

# 删除对象
s3_client.delete_object(Bucket='atp-reports', Key='path/to/file')
```
