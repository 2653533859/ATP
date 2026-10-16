# UI3.2 变异体沙箱执行实时进度与 Killed/Survived 监控抽屉验收 (2026-10-16)

## 概述与结论

UI3.2（变异体沙箱执行实时进度与 Killed/Survived 监控抽屉）已完成全量交付与验证：
1. **API 客户端扩展 (`frontend/src/api/ciImpact.ts` & `frontend/src/api/index.ts`)**：
   - 增加 `runMutationExecution`（向沙箱提交变异体列表并调用用例集执行验证）、`listMutationExecutionReports`（拉取历史变异执行报告列表）与 `getMutationExecutionReport`（获取指定运行报告详情）；
   - 建立 `MutantStatus`（`KILLED` | `SURVIVED` | `TIMED_OUT` | `ERROR`）、`MutantExecutionResult`、`MutationExecutionRunReport`、`RunMutationExecutionRequest` 等强类型接口契约。
2. **变异体沙箱实时监控抽屉 (`MutationExecutionLiveMonitorDrawer.vue`)**：
   - **执行控制与参数配置**：
     - 支持变异体 ID 列表批量输入与一键载入示例变异体；
     - 支持单变异体沙箱执行超时控制（`timeout_sec_per_mutant`，默认 3.0s）；
     - 「运行变异体沙箱验证」主操作按钮，带执行中的 loading 与实时状态流；
   - **核心击毙率 KPI 看板 (5 大指标卡片)**：
     - 变异体总数（`total_mutants_tested`）、变异体被击毙数（绿色 `KILLED`，代表断言有效）、变异体存活数（红色 `SURVIVED`，代表断言缺失盲区）、变异超时数（橙色 `TIMED_OUT`）、综合击毙率百分比（`kill_rate_pct`，带动态彩色进度条与判定说明）；
   - **执行结果流与表格筛选矩阵**：
     - 状态筛选 Radio 组：全部 / 仅击毙 / 仅存活 / 超时；
     - 变异体信息列：行号徽章、算子彩色 Tag、变异体 ID 与描述；
     - 执行状态列：Killed（绿）/ Survived（红）/ Timed Out（橙）/ Error（灰）；
     - **击毙用例定位与断言拦截分析**：
       - 若被击毙：明确标出是哪一个用例将其击落（用例名称/ID），并展示捕获的 `AssertionError` 异常信息；
       - 若存活：标红显式告警「变异体存活：所有用例测试均未拦截该代码篡改！需补充针对性断言」。
3. **接口测试工作台集成 (`ApiWorkbenchView.vue`)**：
   - 顶部工具栏挂载「变异沙箱监控」快捷操作入口；
   - 随时一键滑出 1060px 监控抽屉排查断言盲区。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/MutationExecutionLiveMonitorDrawer.spec.ts`：**2 passed in 52ms**；
   - `src/views/workbench/components/CodeMutationOperatorGeneratorModal.spec.ts`：**2 passed in 63ms**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed in 1.4s**；
   - 接口测试工作台核心测试套件：**20 passed in 753ms**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 11.52s, 0 errors**。
