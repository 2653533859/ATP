# UI3.3 变异得分 (Mutation Score) 与断言盲区热力报告页面验收 (2026-10-16)

## 概述与结论

UI3.3（变异得分与断言盲区热力报告页面）已完成全量交付与验证，至此 **ATP v3.7.0 Phase 3（代码变异测试执行与断言盲区热力工作台）100% 达成全量大闭环**：
1. **API 客户端扩展 (`frontend/src/api/ciImpact.ts` & `frontend/src/api/index.ts`)**：
   - 增加 `calculateMutationScore`（向后端触发用例变异得分与断言充分性重算）、`listMutationScoreReports`（拉取历史变异得分报告列表）与 `getMutationScoreReport`（获取指定报告详情）；
   - 建立 `AssertionAdequacyLevel`（`EXCELLENT` | `ADEQUATE` | `INSUFFICIENT` | `WEAK`）、`OperatorScoreBreakdown`、`AssertionBlindspotItem`、`MutationScoreReport`、`CalculateMutationScoreRequest` 等强类型接口契约。
2. **变异得分与断言盲区热力报告大盘全景视图 (`MutationScoreHeatmapReportView.vue`)**：
   - **头部 Hero 区域**：
     - 展示大盘定位与作用，支持一键切换「卓越断言（88%）」和「存在盲区（50%）」快速推演预设；
     - 「重算变异得分」弹窗入口，支持指定 Run ID 触发重评；
   - **综合变异得分与充分性评级裁决大横幅 (Verdict Banner)**：
     - 圆环呈现变异得分百分比（如 87.5%）；
     - 四级断言充分性彩色徽章（EXCELLENT 绿 / ADEQUATE 蓝 / INSUFFICIENT 橙 / WEAK 红）；
     - 细致的质量门禁准入指导建议（如「通过准入门禁 (≥85%)」或「阻断合流门禁 (<50%)」）；
   - **4 大 KPI 指标网格**：
     - 已注入变异体总数、成功击毙变异体数（Killed）、存活变异体数（Survived）、超时变异体数（Timed Out）；
   - **五大一阶算子击毙率雷达图 (ECharts Radar)**：
     - 实测算子击毙率 vs 85% 卓越基线雷达图双系列对比，配套五大算子详细效能与进度条卡片；
   - **断言盲区代码行级热力清单 (Assertion Blindspots Heatmap Table)**：
     - 支持按 ROR/LCR/AOR/RVO/BVO 算子单选过滤；
     - 呈现代码文件相对路径与行号徽章；
     - 红/绿底行级代码差异（`original_line` vs `mutated_line`）；
     - **用例断言修复指引 (Suggested Fix)**：明确给出该代码行需要增加什么断言才能抓住该缺陷，支持一键复制修复指引文本。
3. **路由配置 (`frontend/src/router/index.ts`)**：
   - 注册路由 `/quality/mutation-score`（路由名 `mutation-score-heatmap-report`），受工程师与管理员权限管控。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/quality/MutationScoreHeatmapReportView.spec.ts`：**2 passed in 66ms**；
   - 质量中心核心测试套件：**22 passed in 909ms**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 8.47s, 0 errors**。
