# ATP 平台 Q10 实施计划

> 生成日期：2026-05-30
> 前置：Q1–Q9 功能全部收口，处于「release-readiness baseline」；后端 726 测试扎实、可观测性基建（OTel + Prometheus + Grafana）到位
> 定位：从「功能完整」推进到「质量可度量、回归可防护、工程可信赖」。**质量门禁优先**——先打可度量/防回退的地基，再叠安全扫描与测试扩展

---

## 复盘输入

Q1–Q9 已把规划内的业务能力做完，没有「必须做」的大功能在等待。对照质量基线，识别出四块明显缺口：

| 维度 | 现状 | 缺口 |
|------|------|------|
| 后端测试 | 130 文件 / 726 passed，`api`(58)/`services`(27)/`worker`(23) 扎实 | 无覆盖率度量、无门禁 |
| 后端代码质量 | 仅 `pytest`，根有 `pyproject.toml` | 无 lint(ruff) / 格式化 / 类型检查(mypy) |
| 前端测试 | 仅 5 个 Playwright E2E（nightly，mock 模式） | **零单元/组件测试**（无 vitest / test-utils） |
| 集成测试 | 3 个核心流程（auth / case-run / mock，nightly） | 套件/计划/Android/通知/缺陷未覆盖 |
| 安全扫描 | **完全没有** | 无 SAST / 依赖漏洞 / 镜像 / 密钥扫描 / dependabot |
| CI 门禁 | push/PR 跑 pytest + 前端 type-check/build | 无 lint / coverage / 安全 gate |
| 可观测性 | OTel + Prometheus + Grafana + 慢查询/告警已就绪 | 无 SLO / 错误预算 / 合成监控 |

**结论**：后端单测扎实、可观测性基建到位；但前端测试几乎为零、安全扫描完全空白、CI 缺质量门禁、覆盖率不可度量。Q10 聚焦补齐这四块，并遵循 Q7 的教训——不堆新业务长尾，专注让平台自身的质量成为标杆。

---

## Q10 主线

### P0-1：后端代码质量门禁

目标：建立 lint / format / 类型检查门禁，统一代码风格，让低级缺陷在 CI 阶段被拦截。

范围：

- 引入 `ruff`：lint（规则集 E/F/I/UP/B/SIM 等）+ format，配置写入 `pyproject.toml`。
- 全量 `ruff check` 扫描：能自动修复的修复，存量噪音用 `per-file-ignores` 基线豁免，逐步收敛。
- `ruff format` 一次性统一格式：作为**独立 commit**，并登记到 `.git-blame-ignore-revs`，避免污染 `git blame`。
- 引入 `mypy`：渐进式启用，首批覆盖 `core/`、`schemas/`、`services/`，`strict` 选项分模块逐步打开。
- 新建 `.pre-commit-config.yaml`：ruff + ruff-format + trailing-whitespace / end-of-file-fixer 等基础 hook。
- CI 新增 lint job：`ruff check` + `ruff format --check`（+ mypy 选定模块）。

验收：

- `ruff check` 与 `ruff format --check` 在 CI 通过，存量豁免清单可见且有收敛计划。
- 开发者本地可一键运行 `pre-commit run --all-files`。
- mypy 对选定模块零 error（其余模块暂以 `ignore_errors` 标注，列入后续收敛）。

### P0-2：测试覆盖率度量与门禁

目标：让覆盖率从「不可见」变为「可量化、防回退」。

范围：

- 引入 `pytest-cov`，配置 `pyproject.toml` 的 `[tool.coverage]`（source、omit 测试/迁移、分支覆盖）。
- 跑出当前后端覆盖率基线，写入 `docs/code-quality.md` 作为锚点。
- CI pytest 步骤加 `--cov --cov-report=xml --cov-report=term-missing --cov-fail-under=<基线-1%>`：低于门槛 fail。
- 覆盖率 XML/HTML 报告产出为 CI artifact，便于审阅未覆盖行。
- 前端覆盖率随 P0-3 的 vitest 一并接入（`@vitest/coverage-v8`）。

验收：

- CI 每次 PR 报告后端覆盖率，低于门槛阻断合并。
- 覆盖率基线被记录，门槛只升不降（防回退）。

### P0-3：前端单元测试体系从 0 到 1

目标：补齐**最大缺口**——前端目前零单元/组件测试。

范围：

- 引入 `vitest` + `@vue/test-utils` + `jsdom` + `@vitest/coverage-v8`。
- 新建 `frontend/vitest.config.ts`（或合并入 vite config），`package.json` 加 `test` / `test:coverage` 脚本与 devDependencies。
- 首批测试聚焦高价值、稳定、纯逻辑的目标：
  - `stores/auth.spec.ts` —— login / logout / token 持久化 / user 状态。
  - `api/http.spec.ts` —— JWT 拦截器注入、401 跳转重定向。
  - `utils/websocket.spec.ts` —— 自动重连与回调分发逻辑。
  - 1–2 个纯组件：`KvEditor` / `ModuleTree` 的渲染与事件。
- CI frontend job 新增 `npm run test`（与 type-check/build 并列）。

验收：

- `npm run test` 通过并产出前端覆盖率报告。
- CI 拦截前端单测失败；后续新增前端模块默认带测试成为约定。

### P1-1：自动化安全扫描

目标：从零建立安全扫描自动化，覆盖代码、依赖、镜像、密钥四个面。

范围：

- **SAST**：`bandit` 扫描后端，配置写入 `pyproject.toml`（`[tool.bandit]`），基线豁免误报。
- **依赖漏洞**：`pip-audit`（后端）+ `npm audit` 或 `osv-scanner`（前端）。
- **镜像扫描**：`trivy` 扫 backend / worker / frontend 镜像，与 `release-readiness` 流程联动。
- **密钥扫描**：`gitleaks`（CI + pre-commit）。
- 新建 `.github/dependabot.yml`：覆盖 pip / npm / docker / github-actions 四个生态，按周更新。
- 新建 `.github/workflows/security.yml`：PR 跑轻量项，nightly 跑全量；**仅 high/critical 阻断**，medium 及以下记录不阻断，控制噪音。

验收：

- PR / nightly 跑安全扫描，high/critical 漏洞阻断合并。
- dependabot 自动提交依赖更新 PR。
- 扫描结果有分级与豁免清单，噪音可控。

### P2-1：集成 / E2E 覆盖扩展 + SLO 薄切

目标：织密回归网，并基于已有可观测性基建定义服务质量目标。

范围：

- **集成测试扩展**：补 suite-run / plan-trigger / notification / bug-report 等流程（2–4 个），复用 `backend/tests/integration` 真实 pg+redis+minio 基座。
- **E2E 扩展**：补 suite / plan 关键路径 spec（视成本量力而行）。
- **flaky 治理**：引入 `pytest-rerunfailures` 或显式标记 + 文档化处理约定。
- **SLO 薄切**：基于已有 Grafana 定义 2–3 个核心 SLO（API 可用性、关键端点 P95 延迟、run 成功率）+ 错误预算面板；合成探测（synthetic probe）作为设计稿留待后续。
- Q10 验收摘要与文档收口。

验收：

- 集成 / E2E 用例数较 Q9 显著增加，覆盖主要业务流程。
- Grafana 可见 SLO 与错误预算面板。
- `docs/q10-acceptance-summary.md` 产出，README / Task.md 同步。

---

## 建议排期

### Phase 1（1 周）：后端代码质量门禁 [P0-1]

- [ ] `ruff` lint + format 配置写入 `pyproject.toml`。
- [ ] 全量扫描 + 自动修复 + 存量基线豁免清单。
- [ ] `ruff format` 一次性统一（独立 commit + `.git-blame-ignore-revs`）。
- [ ] `mypy` 渐进式覆盖 core / schemas / services。
- [ ] `.pre-commit-config.yaml` 新建。
- [ ] CI 新增 lint job。

输出：

- `pyproject.toml`、`.pre-commit-config.yaml`、`backend/requirements-dev.txt`
- `.github/workflows/ci.yml`、`.git-blame-ignore-revs`
- `docs/code-quality.md`

### Phase 2（0.5–1 周）：测试覆盖率门禁 [P0-2]

- [ ] `pytest-cov` 接入，`[tool.coverage]` 配置。
- [ ] 跑出后端覆盖率基线并记录。
- [ ] CI 加 `--cov-fail-under` 门禁 + 报告 artifact。

输出：

- `pyproject.toml`、`backend/requirements-dev.txt`
- `.github/workflows/ci.yml`、`docs/code-quality.md`

### Phase 3（1.5–2 周）：前端单元测试从 0 到 1 [P0-3]

- [ ] `vitest` + `@vue/test-utils` + `jsdom` + coverage 接入。
- [ ] `vitest.config.ts` + `package.json` 脚本与依赖。
- [ ] 首批测试：auth store / http 拦截器 / websocket / 1–2 纯组件。
- [ ] CI 前端 test 步骤。

输出：

- `frontend/package.json`、`frontend/vitest.config.ts`
- `frontend/src/**/*.spec.ts`
- `.github/workflows/ci.yml`、`docs/frontend-testing.md`

### Phase 4（1 周）：自动化安全扫描 [P1-1]

- [ ] bandit SAST + 基线。
- [ ] pip-audit + npm audit / osv-scanner 依赖扫描。
- [ ] trivy 镜像扫描（联动 release-readiness）。
- [ ] gitleaks 密钥扫描（CI + pre-commit）。
- [ ] `.github/dependabot.yml` 四生态。
- [ ] `.github/workflows/security.yml`（分级阻断）。

输出：

- `.github/dependabot.yml`、`.github/workflows/security.yml`
- `pyproject.toml`（bandit）、`.pre-commit-config.yaml`（gitleaks）
- `docs/security-scanning.md`

### Phase 5（1 周）：集成扩展 + SLO + 收口 [P2-1]

- [ ] 集成测试补 suite / plan / notification / bug-report 流程。
- [ ] E2E 补 suite / plan 关键路径。
- [ ] flaky 治理（rerunfailures + 标记 + 文档）。
- [ ] SLO 薄切（3 条 SLO + 错误预算面板）。
- [ ] Q10 验收摘要 + README / Task.md 收口。

输出：

- `backend/tests/integration/*`、`frontend/e2e/*`
- `deploy/grafana/dashboards/`、`deploy/grafana/alerts/`
- `docs/q10-acceptance-summary.md`、`README.md`、`Task.md`

### 排期总览

```
Phase 1 后端质量门禁 ────── 1 周     [P0]
Phase 2 覆盖率门禁 ──────── 0.5-1 周  [P0]
Phase 3 前端单测从 0 到 1 ── 1.5-2 周  [P0]  ← 最大缺口
Phase 4 安全扫描自动化 ──── 1 周     [P1]
Phase 5 集成扩展+SLO+收口 ─ 1 周     [P2]
                            ≈ 5-6 周
```

---

## 非目标

- 不追求 100% 覆盖率：设现实基线，只防回退，不为指标写无意义测试。
- 不一次性全量启用 strict mypy：按模块渐进，避免一次性海量报错阻塞推进。
- 不把 `ruff format` 的大 diff 与功能改动混在一个 commit。
- 不引入重型 SLO / APM 平台：SLO 复用已有 Grafana，合成探测先做设计稿。
- 不在 Q10 新增业务功能方向（专注质量基础设施）。

---

## 风险

| 风险 | 缓解 |
|------|------|
| `ruff format` 一次性大 diff 污染 `git blame` | 独立 commit + 登记 `.git-blame-ignore-revs` |
| mypy 全量报错过多阻塞推进 | 渐进式，按模块开启，未覆盖模块临时 `ignore_errors` |
| `cov-fail-under` 设太高阻塞日常 PR | 取当前基线略降 1–2% 作门槛，后续只升不降 |
| 安全扫描误报噪音淹没真问题 | 基线豁免 + 分级（仅 high/critical 阻断） |
| 前端单测引入改动构建配置导致回归 | vitest 独立配置，不影响 vite build；先小批量验证 |
| 存量代码 lint 噪音过大 | 首轮以 `per-file-ignores` 圈定豁免，列收敛计划逐步清零 |

---

## 与 Q9 的衔接

- **延续**：Q9 已建立 `release-readiness` workflow 与镜像构建检查，Q10 P1-1 的 trivy 镜像扫描可直接挂接该流程。
- **延续**：Q9 的后端权限审计补齐了 admin 端点契约测试，Q10 P0-2 覆盖率门禁会把这类契约测试纳入度量。
- **延续**：Q9 已有 Prometheus + Grafana 业务指标，Q10 P2-1 的 SLO 直接基于既有指标定义，无需新埋点。
- **新增依赖**：P0-1 的 lint/format 是后续所有改动的统一基线；P0-2 的覆盖率门禁与 P0-3 的前端测试框架是后续测试扩展（P2-1）的前置地基，故排在前。

---

## 验收标准

Q10 完成时应满足：

- ✅ CI 在 push/PR 上跑 ruff lint + format check，存量豁免有收敛计划。
- ✅ 后端覆盖率被度量并设防回退门禁；覆盖率基线记录在案。
- ✅ 前端从零建立 vitest 单测体系，核心 store / util / 组件有测试，CI 拦截失败。
- ✅ 安全扫描（SAST + 依赖 + 镜像 + 密钥）自动化运行，dependabot 启用，high/critical 阻断。
- ✅ 集成 / E2E 覆盖主要业务流程，flaky 有治理约定。
- ✅ Grafana 可见 SLO 与错误预算面板。
- ✅ 各阶段子任务都有对应 commit + 测试/CI 覆盖。
- ✅ `docs/q10-acceptance-summary.md` 编制完成，README / Task.md 同步。

---

## 当前进度记录

- Phase 1：未启动
- Phase 2：未启动
- Phase 3：未启动
- Phase 4：未启动
- Phase 5：未启动
