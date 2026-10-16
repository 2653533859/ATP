# UI3.2 针对复杂业务边界条件的生产级测试合成数据生成卡片验收 (2026-10-17)

## 概述与结论

UI3.2（针对复杂业务边界条件的生产级测试合成数据生成卡片）已完成全量交付与验证，持续推进 **ATP v4.3.0 Phase 3（基于大模型 LLM 的测试用例智能生成、自主探索测试与合成数据控制台）**：
1. **核心组件实现 (`frontend/src/views/workbench/components/SyntheticTestDataGeneratorCard.vue`)**：
   - **头部机制说明 Banner**：
     - 解析三模态测试数据自动合成原理（正向合法、极限极值、反向违规），取代随机盲测与高危明文生产数据依赖；
   - **业务数据模型预设与生成行数控制 (Config Section)**：
     - 内置 3 组真实测试数据模型预设（电商交易下单结算载荷、用户实名认证 KYC 数据集、促销券营销资产测试集）；
     - 支持调节生成数据行数（4 ~ 50 行）；
   - **4 大核心 KPI 统计卡片**：
     - 合成测试数据总行数；
     - 正向合法数据量（70% 比例）；
     - 极限边界值数据量（15% 比例）；
     - 负向异常违规数据量（15% 比例）；
   - **合成测试数据全景明细表格 (Synthetic Data Table)**：
     - 展示行号、合成模态徽章（`POSITIVE_VALID` 绿色、`BOUNDARY_EDGE` 橙色、`NEGATIVE_ANOMALY` 红色）；
     - 预期校验断言标签（`VALID` 预期通过 / `INVALID` 预期阻断）；
     - 数据字段 Payload 格式化预览；
     - 负向异常注入详细说明（违规字段与原因描述）；
   - **多格式导出工具栏 (Export Actions)**：
     - 提供**一键复制测试数据集 JSON** 快捷操作。
2. **工作台集成 (`frontend/src/views/workbench/ApiWorkbenchView.vue`)**：
   - 工具栏挂载「业务测试数据」(`<DatabaseOutlined />`) 快捷入口；
   - 挂载 1120px 宽幅控制台抽屉。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/SyntheticTestDataGeneratorCard.spec.ts`：**1 passed in 35ms**；
   - `src/views/workbench/components/LLMSpecToE2ECaseSynthesizerDrawer.spec.ts`：**1 passed**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed**。
2. **TypeScript 严格类型检查**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean PASS**。
3. **生产环境完整构建**：
   - `npm run build` (`vite build`)：**✓ built in 3.49s, 0 errors**。
