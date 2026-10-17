# ATP v5.2.0 研发任务规划与执行计划 (2026-10-17)

## 1. 版本背景与目标 (Executive Scope)

在 ATP 完成了拖拽式多协议多端混合工作流编排（v5.1.0）与 iOS 真机池化调度（v5.0.0）后，平台在单端、跨端与多协议的自动化执行基建已达到全面贯通。然而，随着企业业务拓扑日趋复杂，测试人员编写和维护端到端复杂工作流的成本依然较高，且常规脚本难以覆盖未知的界面交互盲区。
根据平台技术演进基线规划（`docs/current-capability-baseline-2026-10-15.md`），**ATP v5.2.0 目标打造 AI 智能意图驱动多端测试生成与多模态 VLM 自主探索中台 (AI Intent-Driven End-to-End Test Synthesizer & Autonomous Multimodal VLM Explorer)**。

业务核心诉求：
1. **意图驱动工作流一键合成 (Phase 1)**：业务测试人员输入一段自然语言业务意图（如“生成从接口创建订单、Web 确认加购、iOS 真机支付到数据库对账的端到端测试流”），AI 引擎自动解析语义、生成完整的 DAG 拓扑、匹配节点类型并完成上下文变量（`{{node1.output.id}}`）绑定；
2. **多模态 VLM 自主界面探索与轨迹固化 (Phase 2)**：结合视觉语言大模型（VLM）对 Web 与移动端真实界面屏幕快照的语义理解，自主推导下一步探索交互（点击、输入、滑动），自动检测白屏与崩溃，并将验证通过的探索轨迹一键沉淀为自动化工作流；
3. **意图对话与探索大盘前端交互 (Phase 3)**：提供自然语言交互生成弹窗、探索状态迁移图谱、探索回放与全景工作台中枢；
4. **探索安全护栏沙箱与防篡改发布 (Phase 4)**：提供敏感破坏性动作拦截护栏与 64 位 SHA-256 证据签名存证，通过全套工程门禁并完成正式发布。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：自然语言意图驱动多端混合工作流智能合成引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **自然语言意图驱动工作流 DAG 拓扑合成器** | `backend/app/services/intent_workflow_synthesizer.py` | 解析自然语言业务意图，逆向推导多端多协议 DAG 拓扑、节点配置与跨节点变量上下文透传；单测独立通过；见 docs/evidence/intent-workflow-synthesizer-t1-1-t1-3-2026-10-17.md |
| T1.2 `[x]` | **测试领域意图语义规划与提示词编排器** | `backend/app/services/intent_semantic_prompt_planner.py` | 实现业务领域测试动词槽位提取、协议识别与结构化 Prompt 上下文组装；单测独立通过；见 docs/evidence/intent-workflow-synthesizer-t1-1-t1-3-2026-10-17.md |
| T1.3 `[x]` | **意图驱动工作流生成与优化 REST API** | `backend/app/api/v1/intent_workflow_api.py` | 暴露 `/workflow/intent/generate`, `/workflow/intent/refine` 等接口；单测独立通过；见 docs/evidence/intent-workflow-synthesizer-t1-1-t1-3-2026-10-17.md |

---

### Phase 2：基于多模态 VLM 界面理解的移动与 Web 自主探索引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **多模态 VLM 屏幕语义理解与自主动作决策器** | `backend/app/services/vlm_autonomous_explorer.py` | 接收界面屏幕快照，结合视觉大模型推导下一步操作手势（点击、滑动、输入、返回）并构建状态迁移图；单测独立通过；见 docs/evidence/vlm-autonomous-explorer-t2-1-t2-3-2026-10-17.md |
| T2.2 `[x]` | **探索过程白屏、死锁与崩溃异常侦测器** | `backend/app/services/exploration_anomaly_detector.py` | 自动识别界面全白/纯黑、长时间无响应卡死、错误弹窗及应用闪退异常；单测独立通过；见 docs/evidence/vlm-autonomous-explorer-t2-1-t2-3-2026-10-17.md |
| T2.3 `[x]` | **探索成功轨迹逆向自动化工作流转换器** | `backend/app/services/exploration_to_workflow_converter.py` | 将探索执行通过的连贯手势与请求动作自动固化为低代码混合工作流草稿；单测独立通过；见 docs/evidence/vlm-autonomous-explorer-t2-1-t2-3-2026-10-17.md |

---

### Phase 3：意图对话生成抽屉与自主探索大盘中枢

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[x]` | **自然语言对话式工作流生成弹窗组件** | `frontend/src/views/workbench/components/IntentWorkflowGenerateModal.vue` | 提供意图输入、AI 思考流展示、生成 DAG 预览与一键应用到画布；单测独立通过；见 docs/evidence/intent-workflow-generate-modal-ui3-1-2026-10-17.md |
| UI3.2 `[x]` | **VLM 自主探索控制与状态图谱抽屉组件** | `frontend/src/views/workbench/components/AutonomousExplorationDashboardDrawer.vue` | 展示状态迁移图、屏幕快照回放序列、检出异常与一键转为用例；单测独立通过；见 docs/evidence/autonomous-exploration-dashboard-drawer-ui3-2-2026-10-17.md |
| UI3.3 `[x]` | **AI 自主探索与意图生成工作台中枢页面** | `frontend/src/views/workbench/AiAutonomousExplorationView.vue` | 落地路由 `/workbench/ai-exploration`，集成 4 大 Bento KPI、大盘列表与操作；单测独立通过；见 docs/evidence/ai-autonomous-exploration-view-ui3-3-2026-10-17.md |

---

### Phase 4：探索安全沙箱、合规签名与全量发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[x]` | **自主探索高危动作防护看门狗** | `backend/app/services/autonomous_exploration_safety_guard.py` | 自动识别并阻断注销账户、重置系统、清空数据库等破坏性指令；单测独立通过；见 docs/evidence/autonomous-exploration-safety-guard-t4-1-2026-10-17.md |
| T4.2 `[x]` | **AI 生成与探索证据 64 位 SHA-256 存证器** | `backend/app/services/intent_synthesis_evidence_signer.py` | 为 AI 生成的用例工作流与探索轨迹生成不可篡改 SHA-256 存证证书；单测独立通过；见 docs/evidence/intent-synthesis-evidence-signer-t4-2-2026-10-17.md |
| T4.3 `[x]` | **v5.2.0 AI 探索与意图驱动生成中台综合验收与发布说明** | 全局回归与文档 | 全套后端与前端测试 100% PASS，归档 `docs/v5.2.0-release-notes.md` 与专项交付证据；见 docs/evidence/v5-2-0-ai-intent-exploration-platform-acceptance-2026-10-17.md |

---

## 3. 质量门禁规则

1. **后端质量门禁**：
   - `pytest` 单测 100% PASS；
   - `pytest-standalone-sweep.py` 隔离单跑 100% PASS；
   - `ruff check` 零警告；
   - `ruff format --check` 格式化完全合规；
   - `mypy` 强类型安全通过。
2. **前端质量门禁**：
   - `vue-tsc --noEmit` 严格类型零错误；
   - `vitest run` 单测 100% PASS；
   - `vite build` 生产构建成功。
3. **专项证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
