# ATP v5.9.0 研发任务规划书
## 全链路代码覆盖率动态染色与增量发布准入中台 (Full-Link Code Coverage Dynamic Staining & Incremental Quality Gate Hub)

**规划日期**：2026-10-18
**目标版本**：v5.9.0
**核心目标**：构建工业级全链路代码覆盖率动态染色与增量发布准入中台。实现“多源覆盖率合并 ➔ Git Diff 增量行级染色 ➔ 未覆盖高危分支挖掘 ➔ 补测用例反向推导 ➔ 增量覆盖率门禁阻断 ➔ 源码在线红黄绿染色透视 ➔ 64 位 SHA-256 存证证书”的全链路闭环。

---

## 1. 架构拓扑与全景流程

```mermaid
flowchart TD
    subgraph Phase 1 [Phase 1: 多源覆盖率数据摄取与增量 Diff 行级染色引擎]
        T1_1["T1.1 多源覆盖率报告解析与合并器 (coverage_report_ingestor)"]
        T1_2["T1.2 Git Diff 增量代码行覆盖率染色计算器 (diff_coverage_staining_engine)"]
        T1_3["T1.3 代码覆盖率与增量染色 REST API (/api/v1/code-coverage/*)"]
        T1_1 --> T1_2 --> T1_3
    end

    subgraph Phase 2 [Phase 2: 未覆盖高危分支分析与自动化测试补齐推荐器]
        T2_1["T2.1 未覆盖高危分支路径漏洞挖掘器 (uncovered_branch_risk_analyzer)"]
        T2_2["T2.2 缺失用例场景反向合成与测试输入推导器 (coverage_gap_test_synthesizer)"]
        T2_3["T2.3 增量覆盖率发布准入卡点与红线裁决器 (incremental_coverage_gate_evaluator)"]
        T2_1 --> T2_2 --> T2_3
    end

    subgraph Phase 3 [Phase 3: 覆盖率全景染色看板与源码级透视工作台]
        UI3_1["UI3.1 源码文件逐行覆盖率动态高亮染色抽屉 (CoverageSourceStainingDrawer)"]
        UI3_2["UI3.2 增量覆盖率发布门禁配置与高危分支补测弹窗 (CoverageGateConfigModal)"]
        UI3_3["UI3.3 全链路代码覆盖率与质量门禁工作台中枢 (/workbench/code-coverage)"]
        UI3_1 --> UI3_2 --> UI3_3
    end

    subgraph Phase 4 [Phase 4: 生产发布阻断安全沙箱、合规存证与全量发布]
        T4_1["T4.1 质量门禁发布强阻断与非合规豁免审批看门狗 (coverage_release_blocker_guard)"]
        T4_2["T4.2 覆盖率评估报告与染色结果 64 位 SHA-256 存证证书器 (coverage_evidence_signer)"]
        T4_3["T4.3 v5.9.0 全链路代码覆盖率中台综合验收与发布说明"]
        T4_1 --> T4_2 --> T4_3
    end

    Phase 1 --> Phase 2 --> Phase 3 --> Phase 4
```

---

## 2. 任务分解清单 (Phase 1 ~ Phase 4)

### Phase 1：多源覆盖率数据摄取与增量 Diff 行级染色引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **多源覆盖率报告解析与合并器** | `backend/app/services/coverage_report_ingestor.py` | 支持 JaCoCo XML、Coverage.py JSON 与 LCOV 格式解析与多环境覆盖率并集融合；单测独立通过；见 docs/evidence/coverage-report-ingestor-t1-1-2026-10-18.md |
| T1.2 `[x]` | **Git Diff 增量代码行覆盖率染色计算器** | `backend/app/services/diff_coverage_staining_engine.py` | 映射变更行号，精准计算增量行/分支覆盖率，生成红（未覆盖）、黄（部分覆盖）、绿（全覆盖）行级染色元数据；单测独立通过；见 docs/evidence/diff-coverage-staining-engine-t1-2-2026-10-18.md |
| T1.3 `[ ]` | **代码覆盖率与增量染色 REST API** | `backend/app/api/v1/code_coverage_api.py` | 挂载 `/api/v1/code-coverage/*` 路由，提供覆盖率报告上报、增量 Diff 比对与文件逐行染色查询端点；单测独立通过。 |

---

### Phase 2：未覆盖高危分支分析与自动化测试补齐推荐器

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[ ]` | **未覆盖高危分支路径漏洞挖掘器** | `backend/app/services/uncovered_branch_risk_analyzer.py` | 深度识别未覆盖的支付异常、权限鉴权与重试分支，评估严重度（P0/P1/P2）；单测独立通过。 |
| T2.2 `[ ]` | **缺失用例场景反向合成与测试输入推导器** | `backend/app/services/coverage_gap_test_synthesizer.py` | 依据未覆盖分支逻辑，推导边界输入并生成用例建议草稿；单测独立通过。 |
| T2.3 `[ ]` | **增量覆盖率发布准入卡点与红线裁决器** | `backend/app/services/incremental_coverage_gate_evaluator.py` | 对标发布准入红线（如增量覆盖率 ≥ 85%），未达标自动出具阻断结论与整改清单；单测独立通过。 |

---

### Phase 3：覆盖率全景染色看板与源码级透视工作台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[ ]` | **源码文件逐行覆盖率动态高亮染色抽屉** | `frontend/src/views/workbench/components/CoverageSourceStainingDrawer.vue` | 源码在线红黄绿行级染色、分支命中指示与未覆盖悬浮提示；单测独立通过。 |
| UI3.2 `[ ]` | **增量覆盖率发布门禁配置与高危分支补测弹窗** | `frontend/src/views/workbench/components/CoverageGateConfigModal.vue` | 可视化交互配置增量门禁阈值、豁免白名单与缺失用例导出；单测独立通过。 |
| UI3.3 `[ ]` | **全链路代码覆盖率与质量门禁工作台中枢页面** | `frontend/src/views/workbench/CodeCoverageWorkbenchView.vue` | 落地路由 `/workbench/code-coverage`，集成 4 大 Bento KPI、文件覆盖率列表与交互联动；单测独立通过。 |

---

### Phase 4：生产发布阻断安全沙箱、合规存证与全量发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[ ]` | **质量门禁发布强阻断与非合规豁免审批看门狗** | `backend/app/services/coverage_release_blocker_guard.py` | CI/CD 流水线发布强阻断拦截，防范绕过门禁，支持合规审批单豁免；单测独立通过。 |
| T4.2 `[ ]` | **覆盖率评估报告与染色结果 64 位 SHA-256 存证证书器** | `backend/app/services/coverage_evidence_signer.py` | 规范化确定性 JSON，签发不可篡改的 64 位 SHA-256 指纹与 HMAC-SHA256 签名存证证书；单测独立通过。 |
| T4.3 `[ ]` | **v5.9.0 全链路代码覆盖率中台综合验收与发布说明** | 全局回归与文档 | 全套后端与前端测试 100% PASS，归档 `docs/v5.9.0-release-notes.md` 与专项交付证据。 |

---

## 3. 质量门禁规则

1. **后端质量门禁**：
   - `pytest` 单测 100% PASS；
   - `pytest-standalone-sweep.py` 隔离单跑 100% PASS；
   - `ruff check` 零警告；
   - `ruff format --check` 格式全合规；
   - `mypy` 强类型安全通过。
2. **前端质量门禁**：
   - `vitest` 前端单测 100% PASS；
   - `vue-tsc --noEmit` 0 错误；
   - `vite build` 生产打包成功。
3. **专项证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
