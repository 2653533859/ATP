# ATP 平台 Q9 实施计划

> 生成日期：2026-05-29
> 前置：Q8 已完成，AI 自愈 iter5、AI 用例生成 MVP、Dataset v2 薄切、用户设置服务端持久化与性能压测中心均已落地
> 定位：从“功能薄切完成”推进到“可发布、可观测、可治理”，优先消化 Q8 验收摘要里的发布风险和生产反馈闭环

---

## 复盘输入

Q8 已完成：

- AI 自愈 iter5：结构化建议、人审应用、回归 run 关联与运行详情页接入。
- AI 用例生成 MVP：需求/OpenAPI/cURL 输入到可编辑草稿，前端生成抽屉接入。
- Dataset v2：schema_fields 持久化、上传预览与 schema 校验薄切。
- User Settings：服务端偏好 API，Dashboard layout 同步到服务端并保留 localStorage fallback。
- 性能压测中心：k6 脚本上传、独立 performance 队列、worker 执行、summary 解析、前端指标/threshold/raw summary 展示，并已跑通最小 k6 demo。

Q8 验收遗留风险：

- 发布前需要在 CI 或 Docker 环境跑完整后端回归。
- worker 镜像需要在 Docker-enabled CI 验证 k6 multi-stage 构建路径。
- Dataset v2 需要决定 invalid rows 是 soft-block 还是 hard-block。
- AI healing 需要把生产采纳指标反馈到 iter5 阈值和 prompt examples。

---

## Q9 主线

### P0-1：Release Readiness 与 CI/CD 硬化

目标：把 Q8 的新能力变成可发布版本，降低迁移、镜像、回归与发布流程风险。

范围：

- Full backend regression 在 CI 中可一键跑通，并记录稳定基线。
- Docker-enabled CI 验证 backend / worker / frontend 镜像构建，特别是 worker k6 multi-stage。
- Alembic zero-state upgrade、head check、Helm migrate Job 纳入发布 checklist。
- 生成 Q9 release checklist，覆盖配置、迁移、队列、worker 拆分、回滚与烟测。

验收：

- CI 至少包含 full backend regression、frontend type-check/build、Docker image build 三类检查。
- worker 镜像中 `k6 version` 在 CI 构建阶段被验证。
- 发布 checklist 能指导一次 staging dry-run。

### P0-2：AI 生产反馈闭环

目标：让 AI 自愈 iter5 与 AI 用例生成从“可用”走向“可运营”，把采纳率、失败原因、成本和质量反馈用于后续 prompt / example 调优。

范围：

- AI healing adoption / rollback / regression pass rate 指标沉淀为可查询报表。
- AI case generation 草稿保存率、编辑幅度、失败类型与限额命中统计。
- Prompt example 推荐策略根据采纳质量和业务类型调整。
- Vision 调用成本与失败降级数据进入 Dashboard 或 AI 报表。

验收：

- 可按项目、case_type、error_fingerprint 查看 AI healing 应用效果。
- 可看到 AI 生成草稿从生成到保存/放弃的漏斗。
- prompt/example 调整有前后对比数据。

### P1-1：Dataset v2 治理化

目标：从“schema 校验薄切”推进到“可治理的数据集生命周期”，为参数化执行和 AI 生成提供稳定数据基础。

范围：

- 明确上传校验策略：默认 soft-block，项目可配置 hard-block。
- 数据集版本历史与回滚。
- 引用影响面：用例、套件、计划、AI 草稿引用关系。
- 参数化执行可选 strict schema enforcement。

验收：

- 上传 preview 能清楚展示 invalid rows，并按策略决定是否允许覆盖。
- 数据集可回滚到历史版本。
- 删除或修改数据集前能看到影响面。

### P1-2：Performance Center 生产化

目标：把 Q8 的 k6 thin slice 扩展为安全、可控、可长期运行的压测能力。

范围：

- 目标域名 allowlist 与最大 VUs / duration 后端限制。
- performance worker 独立部署建议落入 Helm values 示例。
- 压测趋势图与 run 对比。
- raw summary 生命周期与清理策略。

验收：

- 超出 allowlist / duration / VUs 的压测请求会被拒绝并返回明确错误。
- 压测 run 能按时间展示 RPS、P95/P99、错误率趋势。
- 存储清理策略覆盖 performance raw summary。

### P1-3：Q8 能力产品化收口

目标：提升新入口的一致性、可发现性和用户体验，减少“功能存在但难用”的摩擦。

范围：

- Performance Center、Dataset Library、AI Generate、AI Healing UI 文案与状态统一。
- 关键失败态和空态补齐。
- 角色权限与只读态 UI 对齐后端权限。
- README / docs 首页补 Q8/Q9 能力索引。

验收：

- 非管理员/只读用户不会看到不可执行操作，或操作明确 disabled。
- 主要新页面都有空态、错误态、加载态和成功反馈。
- README 能快速导航到 Q8/Q9 相关文档。

---

## 建议排期

### Phase 1（1 周）：Release Readiness 基线

- [x] 梳理 Q8 变更面与 release checklist。
- [x] CI full backend regression 命令固化。
- [x] Docker image build / worker k6 build check 纳入 CI 或文档化 fallback。
- [x] Staging dry-run checklist 输出。

输出：

- `docs/q9-release-checklist.md`
- `docs/q9-release-evidence.md`
- `.github/workflows/release-readiness.yml`
- backend/frontend/build 验收记录

### Phase 2（2 周）：AI 反馈闭环

- [x] AI healing adoption / rollback / regression pass rate 聚合。
- [x] AI case generation 草稿漏斗统计。
- [x] AI 报表页补 production feedback 维度。
- [x] prompt example 选择策略引入质量权重。

输出：

- AI stats API / service 更新
- AI 报表 UI 更新
- 反馈聚合测试

### Phase 3（2 周）：Dataset v2 治理

- [x] 上传校验 soft-block / hard-block 策略设计。
- [x] Dataset version model 与迁移。
- [x] Dataset rollback API 与 UI。
- [x] 引用影响面查询。
- [x] 参数化执行 strict schema enforcement 开关。

输出：

- Dataset version migration / model / API
- Dataset Library UI 更新
- `docs/dataset-v2.md` 更新

### Phase 4（1-2 周）：Performance Center 生产化

- [x] allowlist / max VUs / max duration 安全限制。
- [x] Helm values 示例补 performance worker 独立部署。
- [x] 压测趋势图与 run 对比。
- [x] raw summary 清理策略验证。

输出：

- performance API / service 更新
- PerformanceCenterView 趋势与对比 UI
- docs / Helm 更新

### Phase 5（1 周）：产品化与文档收口

- [x] Q8/Q9 新页面权限态、空态、错误态扫描。
- [x] README 新能力索引更新。
- [x] Q9 acceptance summary。
- [x] 全量或聚焦回归记录。

输出：

- `docs/q9-acceptance-summary.md`
- README / Task.md 更新
- 回归证据

---

## 非目标

- 不在 Q9 引入新的大型执行引擎。
- 不让 AI 自动跳过人审直接改写脚本或用例。
- 不把压测扩展成完整 APM 平台。
- 不把 Dataset v2 强制切换到所有历史用例；兼容读取优先。

---

## 风险

| 风险 | 缓解 |
|------|------|
| CI 全量回归耗时过长 | 分 full / focused / nightly 三档，PR 先跑 focused |
| Docker-enabled CI 与本地环境不一致 | 镜像构建检查只依赖 Dockerfile 与锁定版本，staging dry-run 再验证服务编排 |
| Dataset hard-block 影响现有参数化用例 | 默认 soft-block，hard-block 需项目显式开启 |
| AI 指标采样不完整导致误判 | 指标先只做观测，不直接驱动自动策略 |
| 压测能力误打敏感目标 | allowlist、VUs/duration 限制和独立 worker 资源隔离 |
