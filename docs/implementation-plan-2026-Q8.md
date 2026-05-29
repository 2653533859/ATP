# ATP 平台 Q8 实施计划

> 生成日期：2026-05-28
> 前置：Q7 工程清账完成，迁移、可观测性、队列与部署基线已收口
> 定位：在干净工程地基上推进 2 条业务主线 + 2 条工程增强，避免再次堆积长尾

---

## 复盘输入

Q6/Q7 已完成：

- AI 自愈 iter4：反馈聚合、few-shot 示例、多模态 vision flag 与统计页。
- Android 真机自愈：ADB reconnect、心跳监控、Prometheus 指标、Grafana panel 与告警。
- 部署与迁移清账：纯 Alembic 首建、Compose migrate、Helm migrate Job、Celery 队列拆分、慢查询面板。

仍需在生产或联调环境回填真实数据：

- AI 自愈采纳率：按 `case_type`、`error_fingerprint`、是否注入 few-shot 对比。
- vision 诊断效果：启用前后采纳率、成本、失败截图可用率。
- ADB 自愈效果：重连成功率、心跳失联频率、ensure_reachable P95/P99。
- 慢查询 Top 10：结合日志 `trace_id` 与 Jaeger span attribute 定位。

---

## Q8 主线

### P0-1：AI 自愈 iter5 生产化

目标：把 Q6 的 AI 自愈能力从“诊断建议”推进到“可控自动修复 + 回归验证”。

范围：

- 自愈建议结构化：输出 locator、等待条件、断言修正、步骤替换候选。
- 人审后自动应用：仅对低代码步骤和安全白名单字段自动写回。
- 自愈后回归：自动触发单用例回归 run，并关联原失败 run。
- vision 灰度：仅对支持 vision 的模型和配置开启，按项目限额控制成本。
- 报表：展示建议采纳率、应用成功率、回归通过率、成本估算。

验收：

- 低代码 Web/Android 步骤可完成人审应用与回归验证闭环。
- 所有自动写回有审计日志和回滚入口。
- vision 调用有项目级开关、每日限额和失败降级。

### P0-2：AI 用例生成 MVP

目标：从需求文本、接口文档或截图生成可编辑的用例草稿，减少手写成本。

范围：

- 输入：需求文本、OpenAPI 片段、接口 cURL、页面截图说明。
- 输出：标准化 `TestCase` 草稿、步骤、断言、标签、优先级和摘要。
- 草稿态工作流：默认 `draft + pending review`，不能直接执行。
- 复用现有 AILLMConfig、prompt example、项目权限与审计能力。
- 前端入口：用例列表/创建抽屉内新增“AI 生成草稿”。

验收：

- API / Web 低代码两类草稿生成可用。
- 生成结果必须可编辑、可保存、可进入评审流程。
- 失败、超时、限额命中都有明确 UI 状态和后端错误码。

---

## P1 工程增强

### P1-1：性能压测中心调研与薄切

目标：验证 k6 或 Locust 与现有项目/环境/报告模型的集成方式。

范围：

- 先支持 HTTP 压测脚本上传与执行。
- 结果只做基础指标：RPS、P95/P99、错误率、吞吐趋势。
- 不纳入普通功能测试 pass/fail 统计，单独报表。

### P1-2：测试数据集 v2

目标：增强现有 dataset 能力，支撑 AI 生成和参数化执行的长期治理。

范围：

- dataset schema 校验。
- 版本历史与回滚。
- 使用影响面：哪些用例/套件/计划引用了该数据集。
- 导入预览与字段映射。

### P1-3：用户偏好服务端持久化

目标：把关键 localStorage 偏好迁移到 `user_settings`，支持跨设备一致体验。

范围：

- 语言、Dashboard 布局、默认项目、表格列配置。
- 前端先读服务端，失败时回退 localStorage。
- 管理员不读取或覆盖其他用户偏好。

---

## 建议排期

### Phase 1（1 周）：数据复盘与 AI 自愈 iter5 设计

- [x] 汇总 Q7 观测指标与 AI 自愈反馈。
- [x] 输出 iter5 数据模型和安全边界。
- [x] 明确哪些字段允许自动应用。

输出：

- `docs/ai-healing-iter5-design.md`
- `backend/app/services/ai_healing_iter5.py`
- `backend/tests/services/test_ai_healing_iter5.py`

### Phase 2（2 周）：AI 自愈 iter5 MVP

- [x] 结构化建议。
- [x] 人审应用。
- [x] 回归 run 关联。
- [x] 审计与回滚。
- [x] 前端运行详情页接入修复预览、应用并触发回归。

输出：

- `backend/app/api/v1/ai_healing_iter5.py`
- `backend/app/schemas/ai_healing_iter5.py`
- `frontend/src/views/run/RunDetail.vue`
- `backend/tests/api/test_ai_healing_iter5_api.py`

### Phase 3（2 周）：AI 用例生成 MVP

- [x] 后端生成服务与 prompt。
- [x] API/Web 草稿生成。
- [x] 前端生成抽屉。
- [x] 生成草稿保存前编辑。
- [x] 评审流接入。

输出：

- `backend/app/api/v1/ai_case_generation.py`
- `backend/app/services/ai_case/`
- `backend/app/schemas/ai_case.py`
- `frontend/src/views/case/AIGenerateDrawer.vue`
- `backend/tests/api/test_ai_case_generation_api.py`
- `backend/tests/services/test_ai_case_parsers.py`
- `backend/tests/services/test_ai_case_llm_client.py`

### Phase 4（1 周）：P1 薄切与收口

- [x] 压测中心调研 demo。
- [x] dataset v2 设计稿。
- [x] dataset v2 schema 校验薄切 API。
- [x] 数据集上传前校验/预览 UI。
- [x] dataset v2 schema_fields 持久化与 UI 编辑器。
- [x] user_settings schema 与 API 草案。
- [x] Dashboard layout 偏好接入服务端同步，保留 localStorage 降级。
- [x] Q8 文档、测试、部署说明收口。

已完成输出：

- `backend/app/models/user_setting.py`
- `backend/app/api/v1/user_settings.py`
- `backend/alembic/versions/20260528_0034_add_user_settings.py`
- `frontend/src/views/dashboard/DashboardView.vue`
- `docs/user-settings.md`
- `backend/app/services/dataset_schema.py`
- `backend/alembic/versions/20260528_0035_add_dataset_schema_fields.py`
- `frontend/src/views/system/DatasetLibrary.vue`
- `docs/dataset-v2.md`
- `docs/performance-testing-thin-slice.md`
- `docs/q8-acceptance-summary.md`
- `backend/app/models/performance.py`
- `backend/app/api/v1/performance.py`
- `backend/app/worker/tasks_performance.py`
- `backend/alembic/versions/20260529_0036_add_performance_tests.py`

### Phase 5（1 周）：性能压测中心联调与前端化

- [x] performance 队列隔离、Compose / Dockerfile / Helm 默认队列同步。
- [x] `PerformanceTest` / `PerformanceRun` 模型与 Alembic 迁移。
- [x] 压测定义 CRUD、执行触发与 run 查询 API。
- [x] `run_performance_test` Celery 任务骨架与 k6 summary 解析。
- [x] Worker 单测：mock `download_file` / `subprocess.run` / `upload_file`，覆盖 success / failed / missing summary。
- [x] API 行为测试：创建压测定义、触发 run、项目内重名冲突与缺失定义 404。
- [x] Worker 镜像补 k6 安装方式，并在 Docker 不可用环境保留静态检查。
- [x] 前端 `PerformanceCenterView`：压测定义列表、创建/编辑、触发执行、run 列表。
- [x] 前后端脚本上传：`.js/.mjs` k6 脚本上传到 `performance/scripts/{project_id}/` 并自动回填对象名。
- [x] Demo 资产：补 `examples/performance/k6-smoke.js` 与 summary fixture，并用解析测试锁定契约。
- [x] 前端详情抽屉：RPS、P95/P99、错误率、threshold 状态与 raw summary 链接。
- [x] 执行最小 k6 demo，回填真实 `summary.json` 样例。
- [x] 文档收口：补 API 示例、k6 脚本上传约定、生产 performance worker 部署建议。

建议执行顺序：

1. [x] 先补后端 API/worker 单测，锁住行为。
2. [x] 再补 worker 镜像 k6 安装与部署文档。
3. [x] 最后接前端页面和类型定义，跑 `npm run type-check` / `npm run build`。

---

## 非目标

- 不在 Q8 一次性覆盖全部移动端复杂场景生成。
- 不让 AI 直接修改脚本文件并跳过人审。
- 不把压测结果混入功能测试通过率。
- 不引入新的大而全工作流引擎。

---

## 风险

| 风险 | 缓解 |
|------|------|
| AI 自动修复误改用例 | 人审应用、白名单字段、审计日志、快照回滚 |
| vision 成本不可控 | 项目级开关、每日限额、失败降级纯文本 |
| 生成用例质量不稳定 | 强制草稿态、评审流、示例库迭代 |
| 压测任务挤占执行资源 | 独立队列与 worker，结果单独统计 |
| dataset v2 影响参数化执行 | 先做兼容读取，再逐步启用 schema 校验 |
