# UI3.1 一阶语法变异算子注入生成与变异代码对比弹窗验收 (2026-10-16)

## 概述与结论

UI3.1（一阶语法变异算子注入生成与变异代码对比弹窗）已完成全量交付与验证，正式拉开 **ATP v3.7.0 Phase 3（代码变异测试执行与断言盲区热力工作台）** 的序幕：
1. **API 客户端扩展 (`frontend/src/api/ciImpact.ts` & `frontend/src/api/index.ts`)**：
   - 增加 `generateMutants`（向目标 Python 源码注入一阶语法变异）、`listMutationReports`（拉取历史变异报告列表）、`getMutationReport`（获取指定报告明细）与 `getMutant`（获取单变异体详情）；
   - 建立 `MutationOperatorType`（`ROR` | `LCR` | `AOR` | `RVO` | `BVO`）、`MutantItem`、`MutationGenerationReport`、`GenerateMutantsRequest` 等强类型接口契约。
2. **一阶语法变异算子注入工作台弹窗 (`CodeMutationOperatorGeneratorModal.vue`)**：
   - **头部 Banner 与背景说明**：
     - 说明 AST 一阶语法变异算子注入机制与断言充分性检测价值，杜绝「只跑代码无有效断言」的虚假单测覆盖；
   - **源码与算子配置区**：
     - 支持快捷载入内置经典函数示例（折扣计算、权限门禁）；
     - 支持指定文件相对路径、限定注入目标行号（Target Lines）及生成上限（`max_mutants`）；
     - 支持 5 大一阶算子自由多选与动态切换（ROR 关系运算符反转、LCR 逻辑连接符替换、AOR 算术运算符替换、RVO 返回值篡改、BVO 常数边界值偏移）；
   - **变异体生成结果看板 (4 大核心 KPI)**：
     - 已生成变异体总数、涉及源码行号数、已激活变异算子种数、当前选定变异体行号与类型；
   - **左侧变异体清单列表 + 右侧双栏行级代码对比区**：
     - 左侧滚动展示变异体序号、算子彩色 Tag、行号、原 Token 与变异 Token 替换指示箭头（如 `old → new`）；
     - 右侧行级双栏对比框（左红底 Original 原始行，右绿底 Mutated 变异行）；
     - 完整变异体代码预览与「一键复制完整变异代码」快捷交互。
3. **接口测试工作台集成 (`ApiWorkbenchView.vue`)**：
   - 顶部工具栏挂载「代码变异注入」主要操作入口；
   - 随时一键弹出 1120px 工作台弹窗进行变异注入推演与代码比对。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/CodeMutationOperatorGeneratorModal.spec.ts`：**2 passed in 63ms**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed in 1.4s**；
   - 接口工作台核心测试套件：**18 passed in 659ms**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 5.14s, 0 errors**。
