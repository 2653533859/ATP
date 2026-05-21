# ATP 平台 Q5 实施计划

> 生成日期：2026-05-21
> 前置：Q4 六方向（A/B/C/D/E/F）全部收口 2026-05-21
> 推进策略：Phase 1 (A) → Phase 2 (C) → Phase 3 (B)，先清账→提质→新主题

---

## 总览

Q4 完成了"性能/运维下沉 + 长期收口"。Q5 定位为 **预留清账 + 工程质量 + 业务深化**：

- **Phase 1 (A)** Q4 预留项清账（1-2 周）— 让进度图真正全绿
- **Phase 2 (C)** 工程化质量提升（1-2 周）— 修复测试污染、提升 CI 可靠度
- **Phase 3 (B)** Q5 业务深化主题（4-6 周）— AI 自愈 / 数据管理 / 多租户

---

## Phase 1：Q4 预留项清账 [P0]

### P1.1 HTML 报告嵌入录像（E.1.2 回收）

**现状**：`web_executor` / `web_lowcode_executor` 已将录像 `.webm` 上传 MinIO 并写入 `run.result_summary["video_url"]`，但 HTML 报告模板未渲染。

**实施**：
- `_build_report_html` 接受 `video_url` 参数（从 `run.result_summary` 提取）
- 模板封面下方新增 `<video controls>` 块（HTML 专用，PDF 跳过）
- 单测：含 video_url 与不含两种情况

### P1.2 定时报告邮件（E.1.4 回收）

**现状**：`notifier.send_email` 已存在；缺触发器与报告生成的整合。

**实施**：
- `backend/app/worker/tasks_report_email.py` — 新增 Celery 任务 `send_scheduled_report_email`
- `Plan` / `TestPlan` 模型增加 `email_recipients` JSON 字段（迁移）
- Plan 完成后自动触发：生成 HTML 报告（复用 `_build_report_html`）→ 调 `notifier.send_email` 内嵌
- 配置项 `REPORT_EMAIL_ENABLED`、`REPORT_EMAIL_FROM`

### P1.3 Mock 独立端口模式（F 回收）

**现状**：`MOCK_STANDALONE_PORT` 配置项与 `docs/mock-standalone.md` 已就位，缺独立启动器。

**实施**：
- `backend/app/mock_main.py` — 独立 FastAPI 子应用，仅含 `/mock/*`
- `docker-compose.yml` 新增 `mock-standalone` service（profile=`mock-standalone`）
- 测试：独立应用 import 可用、不耦合主 backend 中间件

### P1.4 项目维度保留天数（Phase 5.6 P1 回收）

**实施**：
- `Project` 模型增加 `run_retention_days_override` 可空字段
- `execute_old_runs_cleanup` 按 project 维度循环（fallback 到全局 `RUN_RETENTION_DAYS`）
- 清理预览扩展返回按 project 分组的统计

### 里程碑

- [x] P1.1 HTML 报告嵌入录像
- [x] P1.2 定时报告邮件
- [x] P1.3 Mock 独立端口
- [x] P1.4 项目维度保留天数（MVP：模型+预览 API；真实按项目清理留下迭代）

---

## Phase 2：工程化质量提升 [P1]

### P2.1 测试 sys.modules 污染收口

**现状**：D.2 / F.2 实施期间多次遇到 `setdefault` vs 直接覆盖的冲突。

**实施**：
- `tests/conftest.py` 统一 stub `celery`、`celery.utils.log`、`celery.schedules`
- 删除各 test 文件内的 `sys.modules["..."] = ...` 直接赋值，迁移到 setdefault
- 增加 pytest plugin：导入前快照 sys.modules，每个 test 结束时还原

### P2.2 修复 dockerfile 测试 cwd 假设

**实施**：
- `tests/api/test_exports_dockerfile.py` 改为 `repo_root = Path(__file__).resolve().parents[3]`
- 让测试与 cwd 无关

### P2.3 CI 集成测试环境

**实施**：
- `.github/workflows/test-integration.yml` — 启动真实 postgres/redis/minio + 跑标记 `@pytest.mark.integration` 的测试
- 选定 5-8 个关键路径（auth/run/suite/plan/mock）写真实集成测试
- 单元测试与集成测试分离

### P2.4 前端 E2E 覆盖

**实施**：
- `frontend/e2e/` 目录引入 Playwright
- 覆盖：登录、创建用例、执行、看报告、看板 5 条核心路径
- CI 中 nightly 触发

### 里程碑

- [x] P2.1 sys.modules 污染收口（根级 conftest + `_ensure_stub_attrs` helper：4 个目标模块完整字段集 + 补齐不覆盖）
- [x] P2.2 dockerfile/frontend 测试 cwd 修复（顺手在 P2.1 一并收口，新增 `tests/_paths.py` 提供 `repo_path()` 跨 cwd 路径）
- [ ] P2.3 CI 集成测试环境
- [ ] P2.4 前端 E2E 5 条路径

---

## Phase 3：Q5 业务深化主题 [P2]

### P3.A AI 用例自愈

**目标**：失败 step 自动诊断（截图 + DOM + 错误信息 → LLM）并提供修复建议。

**实施**：
- 复用 Q3 E 方向的 LLM 配置（`AILLMConfig`）
- 新增 `backend/app/services/ai_healing.py` — 收集 step 失败上下文 → 调用 LLM
- 失败后异步触发（不阻塞执行），结果写入 `step_result.healing_suggestion`
- 前端 RunDetail 新增"诊断建议"折叠面板

### P3.B 测试数据管理

**目标**：用例执行前后的数据 setup/teardown 与数据集快照。

**实施**：
- `TestDataset` 模型 + CRUD：CSV/JSON 数据集 + 版本快照
- 用例增加 `dataset_id` 关联；执行时按行参数化运行
- 数据准备 hook：执行前调 SQL/HTTP；执行后自动清理

### P3.C 多租户隔离

**目标**：项目级别的资源完全隔离 + 跨项目访问审计。

**实施**：
- 用户-项目 N:N 关联（`UserProject` 表）替代当前全局可见
- API 中间件检查 project_id 归属
- 审计日志记录跨项目访问尝试
- 前端项目切换时刷新可见资源

### 里程碑

- [ ] P3.A AI 用例自愈
- [ ] P3.B 测试数据管理
- [ ] P3.C 多租户隔离

---

## 风险与兜底

| 风险 | 缓解策略 |
|------|----------|
| P1.2 定时邮件附带大附件被 SMTP 拦截 | 默认内嵌精简版报告，full 版本提供 MinIO 链接 |
| P2.1 测试污染收口可能引入新的环境敏感失败 | 分批迁移，每批跑全量回归 |
| P3.A LLM 调用成本失控 | 配置项限制每日调用上限 + 缓存相似失败 |
| P3.B 数据准备 hook 误操作生产库 | 强制 environment != production 校验 |
| P3.C 多租户改造破坏现有调用 | 引入 feature flag `MULTI_TENANT_ENABLED` 默认 off，灰度切换 |

---

## 实施顺序建议

```
Phase 1 (1-2 周)
  P1.1 → P1.2 → P1.3 → P1.4 (独立小项，可并行)

Phase 2 (1-2 周)
  P2.1 → P2.2 (测试基础设施先行)
  P2.3 → P2.4 (CI 与 E2E)

Phase 3 (4-6 周)
  P3.A (最高业务价值，先做)
  P3.B / P3.C (依优先级而定)
```

---

## 当前进度记录

- Phase 1：已完成（P1.1/P1.2/P1.3/P1.4 全部收口 2026-05-21；P1.4 MVP 保留 per-project 真实清理为下迭代）
- Phase 2：进行中（P2.1/P2.2 合并收口 2026-05-21；`tests/` 全套 446 个全绿，无 ignore 项；P2.3/P2.4 待启动）
- Phase 3：未开始
