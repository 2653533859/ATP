# UI3.2 Prompt 红蓝攻防渗透策略与护栏配置弹窗验收 (2026-10-19)

## 概述与交付物

UI3.2（Prompt 红蓝攻防渗透策略与护栏配置弹窗组件）已全量研发交付并通过各项前端与工程门禁，**Phase 3 达成 66.7% 交付进度**：
1. **组件落地实现 (`frontend/src/views/workbench/components/LlmRedTeamConfigModal.vue`)**：
   - **顶部配置态概览横幅**：
     - 展示被测目标模型（`target_model`）、已激活攻击算子数（`enabled_operators`）、护栏防御模式（`guardrail_strictness`）与渗透加压轮次；
   - **Tab 1: 红蓝攻防算子库策略 (Attack Vectors)**：
     - 网格化卡片选择 6 种主流红蓝对抗变异算子（DAN 11.0 道德解锁、内核特权指令覆盖、底座提示词窃取探测、Base64/ROT13 密文混淆、剧本角色扮演催眠、响应前缀强迫诱导）；
     - 支持单算子渗透变异轮次配置（1~20 轮）与违规测试意图主域选择（支付数据越权、生产删库提权、勒索病毒生成、通用合规边界）；
   - **Tab 2: 双向安全护栏看门狗设置 (Guardrails)**：
     - 提供宽松模式、标准模式（默认）、严苛模式三态审查策略；
     - 个人隐私 PII 自动脱敏掩码开关；
     - 输入 Prompt 预检与模型响应后置拦截双向开关；
     - 毫秒级阻断拦截 SLA 阈值与自定义违规敏感词黑名单编辑；
   - **Tab 3: 模型推理与采样参数 (Inference Specs)**：
     - 切换评测大模型（Qwen 2.5 72B、DeepSeek V3、DeepSeek R1、Llama 3.3 70B、GPT-4o）；
     - 细粒度滑块调节 Temperature（0.0~1.5）、Top-P（0.1~1.0）与最大生成 Token 限制；
   - **操作流控制**：
     - 一键恢复企业级默认安全策略、保存并触发红蓝对抗评测流程。

## 质量与测试门禁验证

1. **前端单元测试**：
   - `src/views/workbench/components/LlmRedTeamConfigModal.spec.ts`：**5 passed in 2.62s (100% PASS)**；
   - **Phase 3 已交付组件联合套件**：**10 passed in 2.77s (100% PASS)**。
2. **前端类型与工程门禁**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 errors, clean pass!**。
