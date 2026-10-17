# UI3.2 动态噪声过滤规则配置与模拟弹窗前端验收 (2026-10-17)

## 概述与交付物

UI3.2（动态噪声过滤规则配置与模拟弹窗）已全量研发交付并通过各项工程门禁，**达成 ATP v5.6.0 Phase 3 第二个前端交互核心里程碑**：
1. **动态噪声规则配置与模拟弹窗组件 (`frontend/src/views/workbench/components/NoiseFilterRuleModal.vue`)**：
   - **4 大典型快捷模板**：一键应用“任意时间戳（`*timestamp*`）”、“32位 TraceID（`*.trace_id`）”、“标准 UUID（`*.uuid`）”与“耗时与耗费（`*.cost_ms`）”；
   - **规则定义表单**：支持规则名、噪声类型枚举（`TIMESTAMP`、`TRACE_ID`、`UUID_RANDOM`、`LATENCY_DURATION`、`CUSTOM_RULE`）、JSONPath 通配模式与正则表达式、启用开关与业务描述；
   - **在线沙箱实时仿真演练**：提供目标 JSONPath 与基线/回放样本输入，一键调用后端即时验证规则是否能准确平滑过滤；
   - **保存与事件分发**：触发 `saved` 事件向工作台或透视抽屉同步最新降噪规则。
2. **前后端 REST API 协同**：
   - 后端 `backend/app/api/v1/traffic_replay_api.py` 挂载规则在线仿真测试端点（`/noise-rule/test`）与一站式比对裁决端点（`/diff-evaluate`）；
   - 前端 `trafficReplayApi` 补充对应封装。

## 质量与测试门禁验证

1. **前端单元测试**：
   - `frontend/src/views/workbench/components/NoiseFilterRuleModal.spec.ts`：3 passed（弹窗展开与模板渲染、在线沙箱实时仿真验证调用、规则表单保存并分发事件）；
   - **通过率**：**3 passed in 3.11s (100% PASS)**。
2. **前端工程质量**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean pass! (20.96s)**；
   - `npm run build` (`vite build`)：**4579 modules transformed, built in 3.80s, 0 errors!**。
3. **后端 API 测试回归**：
   - `backend/tests/api/test_traffic_replay_api.py`：**4 passed in 4.72s (100% PASS)**。
