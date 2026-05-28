# ATP 平台 Q6 实施计划

> 生成日期：2026-05-25
> 前置：Q5 三 Phase（P1 预留清账 / P2 工程质量 / P3 业务深化 A/B/C）全部收口 2026-05-23；Q5 长尾 #1-#4（类型饼图 / 复合索引 / 回滚审计 / 清理 UI）2026-05-25 收口
> 推进策略：Phase 1（Q5 长尾清账 7 项）→ Phase 2（P3.A AI 自愈 iter4：反馈回流 + prompt 调优）

---

## 总览

Q5 完成了"清账 + 工程质量 + 业务深化（自愈/数据集/多租户）"三波收口。Q6 定位为 **看板/工程长尾收口 + AI 自愈第二代闭环**：

- **Phase 1（3-4 周）** Q5 长尾清账 — Task.md 中 7 项遗留待办 + Redis cache 二次澄清
- **Phase 2（3-4 周）** P3.A iter4：反馈数据回流 prompt 调优 + 多模态截图引入

---

## Phase 1：Q5 长尾清账

### P1.1 看板异常告警 [P0]

**现状**：`Task.md` Phase 4.6 P3 标注未完成；DashboardView 与 statistics 端点均已就绪，但无任何告警机制。

**实施**：
- 后端模型：`backend/app/models/dashboard_alert.py` — `DashboardAlertRule(id, project_id, metric, op, threshold, window_minutes, suppress_minutes, notification_config_id, enabled)`；`DashboardAlertEvent(id, rule_id, triggered_at, actual_value, snoozed_until)`
- Alembic 迁移 0030 — 两表 + 索引
- Schemas + CRUD API：`backend/app/api/v1/dashboard_alerts.py`（list/create/update/delete + 列表事件）
- Celery beat：`check-dashboard-alerts`（每小时；按规则 metric 取 statistics 数据 → 比较 → 触发通知 → 写 event 并设 suppress_until）
- 复用现有 notifier：通过 `notification_config_id` 关联，邮件 / 企微 / 钉钉通用
- 前端：`DashboardView.vue` 顶部红色标记 + `views/system/DashboardAlertRulesView.vue` 规则配置弹窗
- 配置项：`DASHBOARD_ALERT_DEFAULT_SUPPRESS_MIN`（默认 60）

### P1.2 项目级 vs 全局看板切换 [P1]

**现状**：DashboardView 已有项目下拉，但默认无清晰"全局/项目"切换体验，统计端点已支持 project_id。

**实施**：
- 前端：DashboardView 顶部新增 `a-segmented` Tab：`全局 | 单项目`
- "单项目"模式下显示项目下拉；"全局"模式下不传 project_id
- localStorage 记忆上次选择（key: `atp:dashboard:scope`）
- 视觉区分：全局模式 Header 加 "🌐 全局"，项目模式 "📁 项目名"
- 项目模式下，调用项目级 statistics 端点；全局保持现状

### P1.3 看板数据导出 PNG/CSV [P1]

**实施**：
- 前端 PNG：echarts 实例 `getDataURL({ pixelRatio: 2, backgroundColor: '#fff' })` → trigger download
  - 每个 LazyChartCard 右上角 `<a-dropdown>`：导出 PNG / 导出 CSV
- 后端 CSV：`GET /statistics/export/csv?chart=pass_rate_trend&project_id=&days=&aggregate=` — 复用现有 statistics 函数计算 + StringIO CSV
- 支持 chart 枚举：`pass_rate_trend / duration_trend / failure_top / executor_top / trigger_type / plan_trend / suite_trend / case_type_distribution`
- 不实现批量"全看板 ZIP"导出（避免阻塞主流程）

### P1.4 自定义看板 [P2]

**实施**：
- 前端：DashboardView 顶部新增 `a-button` "看板设置"
- 弹窗内 checkbox 控制每个 LazyChartCard 显隐 + drag-and-drop 排序（vuedraggable）
- 持久化到 localStorage（key: `atp:dashboard:layout`）；不进数据库
- 重置按钮恢复默认布局

### P1.5 Redis 高频查询缓存澄清 [P2]

**现状**：`statistics.py` 9 个端点已 `@cached_json`（Q4-A 已落地）；`cases/runs.py` 列表已 keyset 分页。本项实际指的是**其它高频读操作**。

**实施**：
- 扫描 Q5 后新增的高频 GET 端点（healing 推荐 / dataset list / mobile statistics）
- 对命中率验证 > 30% 的端点接 `@cached_json` TTL 60s
- 不做 cache invalidate hook（让 TTL 自然失效，避免 invalidate 复杂度）
- 单测：cache hit/miss 流程

### P1.6 前端 any 类型工程化收口 [P1]

**现状**：147 处 `any` / 集中在 ~20 个文件。Top 5：EnvironmentList (15) / CaseList (14) / SpecialTaskListView (12) / WebCaseDrawer (12) / CaseFormDrawer (12) = 65。2026-05-28 已完成批 1 Top 5 页面：EnvironmentList / CaseList / SpecialTaskListView / WebCaseDrawer / CaseFormDrawer。

**实施（分 4 批）**：
- **批 1** Top 5 文件（65 处）— 类型从 `@/api` 类型导入；catch (e: any) → `unknown` + 类型守卫（已完成）
- **批 2** 中频文件（ApkList / GlobalVariableLibrary / DeviceList / ReportDetailView / ReportCenterView / LowcodeStepEditor / AndroidStepEditor / StorageManagementView / MockRuleList / CaseDetail，约 60 处；已完成）
- **批 3** 长尾（剩余 ~20 处；已完成）
- **批 4** 收尾扫描 + ESLint 规则：`@typescript-eslint/no-explicit-any: warn`（当前前端未接入 ESLint 依赖/配置，先以 `rg "\bany\b" frontend/src -g "*.ts" -g "*.vue"` 收尾验证；后续引入 ESLint 时补 warn 规则）
- 每批结束跑 `npm run type-check`；不修改运行时行为，仅类型修正

### P1.7 部署/运维持续打磨 [P2]

**实施**（拆细 3 项小工程）：
- Helm values 注释完善：`deploy/helm/atp/values.yaml` 每个字段加 `#` 注释 + values.schema.json 描述
- 备份恢复演练脚本：`scripts/restore-postgres.sh` 配套 `backup-postgres.sh`；文档 `docs/disaster-recovery.md`
- Grafana 告警规则模板：`deploy/grafana/alerts/atp-alerts.yaml` 预置 5 条规则（API 错误率 / Worker 队列堆积 / DB 连接耗尽 / Celery 失败率 / Run 超时率）

### 里程碑

- [x] P1.1 看板异常告警
- [x] P1.2 项目级 vs 全局看板切换
- [x] P1.3 看板数据导出 PNG/CSV
- [x] P1.4 自定义看板
- [x] P1.5 Redis 高频查询缓存澄清
- [x] P1.6 前端 any 类型收口（批 1-4）
- [ ] P1.7 部署/运维持续打磨（Helm 注释 + 恢复脚本 + Grafana 告警模板）

---

## Phase 2：P3.A AI 自愈 iter4 — 反馈回流 + prompt 调优

### P2.1 反馈数据采集与周期聚合 [P0]

**现状**：StepResult 已有 `healing_feedback` (adopted/rejected/none) + 时间戳（Q5-P3.A iter3 落地）。

**实施**：
- 新增模型 `backend/app/models/healing_feedback.py`：
  - `HealingFeedbackAggregate(id, error_fingerprint, case_type, total_count, adopted_count, rejected_count, adopted_rate, last_aggregated_at)`
- Alembic 迁移 0031 — 表 + 唯一索引 `(error_fingerprint, case_type)`
- Celery 周任务 `aggregate_healing_feedback`（周一凌晨 04:17）：
  - 扫描过去 7 天 step_results 含 feedback 的记录
  - 按 `(error_fingerprint, case_type)` 分组汇总
  - upsert 到 `healing_feedback_aggregates`
- 单测：聚合逻辑、upsert 行为、空数据兜底

### P2.2 prompt 示例库 + few-shot 注入 [P0]

**实施**：
- 新增模型 `HealingPromptExample(id, error_fingerprint, case_type, step_context_json, suggestion_text, source_step_result_id, marked_high_quality, marked_by, marked_at, created_at)`
- Alembic 迁移 0032
- API：
  - `GET /api/v1/ai-healing/examples?error_fingerprint=&case_type=&high_quality=`
  - `POST /api/v1/ai-healing/examples/from-step/{step_result_id}` — 从 adopted=true 的 step_result 提取
  - `PATCH /api/v1/ai-healing/examples/{id}` — admin 标注 high_quality
  - `DELETE /api/v1/ai-healing/examples/{id}`
- ai_healing service：调用 LLM 前查询同 fingerprint Top-3 `high_quality=true` 示例，inject 到 system prompt 作 few-shot
- 配置项：`AI_HEALING_FEW_SHOT_ENABLED` (default true) + `AI_HEALING_FEW_SHOT_TOP_N` (default 3)
- 前端：`views/system/HealingExamplesView.vue` admin 标注页面（列表 + 标注按钮 + 详情查看）
- 单测：示例查询、few-shot 注入流程、高质量过滤

### P2.3 反馈采纳率报表 [P1]

**实施**：
- API：`GET /api/v1/ai-healing/stats`
  - `total_feedback_count`
  - `adopted_rate`（按 case_type 分组）
  - `top_error_fingerprints`（Top 10 + 各 fingerprint 的 adopted_rate）
  - `recent_trend`（最近 30 天日聚合）
- 前端：`views/system/AIHealingStatsView.vue`
  - KPI 卡片：总反馈数 / 总采纳率 / 高质量示例数
  - 按 case_type 通过率柱状图
  - 错误特征 Top-10 表（点击展开查看示例）
  - 30 天趋势折线图
- 复用 `@cached_json` TTL 5min

### P2.4 多模态截图引入 [P2]

**实施**：
- `AILLMConfig` 新增 `supports_vision` boolean 字段 + alembic 迁移 0033
- ai_healing service：当 `step_result.screenshot_url` 非空且 `config.supports_vision=True` 时
  - 从 MinIO 下载截图 → base64 编码
  - inject 到 LLM messages 的 image content block（OpenAI Vision / Claude Vision 标准格式）
- Feature flag `AI_HEALING_VISION_ENABLED` (default **false**)
- 独立限额 `AI_HEALING_VISION_DAILY_LIMIT`（default 50，小于普通 limit）
- 失败兜底：图片下载失败 / 编码失败 → fallback 到纯文本调用，写 warning 日志
- 单测：vision flag on/off / 下载失败兜底 / 限额命中

### 里程碑

- [ ] P2.1 反馈数据采集与周期聚合
- [ ] P2.2 prompt 示例库 + few-shot 注入
- [ ] P2.3 反馈采纳率报表
- [ ] P2.4 多模态截图引入

---

## 风险与兜底

| 风险 | 缓解策略 |
|------|----------|
| P1.1 告警风暴 | 每规则 + 每项目至少 1h 抑制窗口；告警去重（同规则同窗口只发 1 次） |
| P1.4 自定义看板 localStorage 跨设备不同步 | 仅 localStorage 不进 DB；如有跨设备需求，留待 Q7 用户 settings 表 |
| P1.6 any 收口引入运行时回归 | 仅类型修正，不动逻辑；分批 + 每批 type-check + 关键页面手测 |
| P1.7 备份恢复脚本误操作生产库 | 脚本第一行 `[[ "$1" == "--i-know-this-overwrites" ]]` 强制确认参数 |
| P2.2 prompt 示例库噪声放大 | 仅 admin 标注 `high_quality=true` 的示例才进入 few-shot；可一键关闭 `AI_HEALING_FEW_SHOT_ENABLED=false` |
| P2.4 多模态 LLM 调用成本激增 | feature flag default off + 独立 daily limit + 失败 fallback 到纯文本 |

---

## 实施顺序建议

```
Phase 1（3-4 周）
  P1.1 告警 (P0，先) ────────────────────────────────────┐
  P1.6 any 收口（穿插 4 批，每批跨越 ~1 周）             │
  P1.2 / P1.3 (P1) ─────────────────────────────────────┤
  P1.4 / P1.5 / P1.7 (P2，按团队带宽插入)               │
                                                          ↓
Phase 2（3-4 周）
  P2.1 聚合 (P0) → P2.2 示例库 (P0) → P2.3 报表 (P1) → P2.4 多模态 (P2)
```

实际推进可像 Q4/Q5 一样按"清账 → 业务"串行，或 P1/P2 部分并行（前后端不同人手时）。

---

## 当前进度记录

- Phase 1：已启动；2026-05-27 完成 P1.1 看板异常告警（规则/事件模型、迁移、CRUD API、项目权限、Celery Beat 统计检查、通知触发、抑制窗口、前端规则配置页、Dashboard 项目级告警提示与测试）；完成 P1.2 项目级 vs 全局看板切换（显式 scope segmented、项目下拉仅单项目模式显示、localStorage 记忆、全局模式不传 project_id）；完成 P1.3 看板 PNG/CSV 导出（图表菜单 PNG getDataURL + 后端 CSV export 端点）；完成 P1.4 自定义看板（localStorage 图表显隐、拖拽/按钮排序、重置默认布局）；完成 P1.5 Redis 高频查询缓存澄清（dataset list + mobile stats 统一 60s TTL 自然失效缓存）；2026-05-28 完成 P1.6 批 1，完成 EnvironmentList / CaseList / SpecialTaskListView / WebCaseDrawer / CaseFormDrawer 的显式 any 收口并通过前端 type-check；完成 P1.6 批 2（ApkList / GlobalVariableLibrary / DeviceList / LowcodeStepEditor / AndroidStepEditor / StorageManagementView / ReportCenterView / ReportDetailView / MockRuleList / CaseDetail）并通过前端 type-check；完成 P1.6 批 3/4 长尾与收尾扫描，`frontend/src` 中除 locale 文案 key `any_method` 外无显式 any，前端 type-check 通过
- Phase 2：未启动

---

## 与 Q5 的衔接

- **延续**：Q5 P3.A iter3 已落地 `healing_feedback` 字段与采纳/拒绝按钮，Q6 P2.x 直接以该数据为输入
- **延续**：Q5 长尾收口 #4 已建 `RunRetentionView`，Q6 P1.1 告警规则页可复用其 system admin 路由模式
- **新增依赖**：Q6 P2.4 vision 调用要求 AILLMConfig 模型升级，对历史配置数据 backfill `supports_vision=false`
