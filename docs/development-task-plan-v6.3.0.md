# ATP v6.3.0 研发任务规划书: 企业级大模型与 RAG 智能体评测红蓝对抗中台

**版本代号**: `v6.3.0`
**核心方向**: RAG 检索质量三元组评估（相关性/忠实度/回答度）、事实一致性与幻觉率检出、Prompt 注入越狱红蓝对抗攻击渗透、敏感毒性安全护栏看门狗、Token 经济学基准与密码学存证证书中枢。
**发布周期**: 2026-10-18 ~ 2026-10-19

---

## 1. 架构总览与业务价值

随着企业大语言模型 (LLM)、知识库检索增强生成 (RAG) 与自主智能体 (Agents) 的规模化落地，AI 软件工程面临三大核心测试挑战：
1. **RAG 质量黑盒化与回答无根幻觉**：检索召回片段与用户 Query 不匹配，或大模型脱离检索事实胡编乱造虚假数据；
2. **新型 Prompt 注入与越狱对抗攻击风险**：攻击者利用角色扮演、指令覆盖、Base64 混淆绕过模型安全对齐，诱导输出敏感数据或执行危险指令；
3. **推理延迟与 Token 经济学缺乏基准**：缺少首字延迟 (TTFT)、每秒 Token 生成率 (TPS) 与单位请求成本核算标准。

ATP v6.3.0 引入 **企业级大模型与 RAG 智能体评测中台**，构建覆盖功能质检、安全对抗与性能经济学的立体化评测体系：

```mermaid
flowchart TD
    subgraph Phase 1 [Phase 1: RAG 检索三元组质量评测与幻觉消除引擎]
        T1_1["T1.1 RAG 知识检索召回与上下文相关度精算器"]
        T1_2["T1.2 大模型幻觉率统计与事实一致性校验器"]
        T1_3["T1.3 大模型评测与 RAG 质量基准 REST API"]
        T1_1 --> T1_2 --> T1_3
    end

    subgraph Phase 2 [Phase 2: Prompt 越狱注入攻防与有害内容安全护栏看门狗]
        T2_1["T2.1 Prompt 注入与越狱对抗攻击渗透变异器"]
        T2_2["T2.2 大模型有害内容与毒性安全护栏看门狗"]
        T2_3["T2.3 大模型推理延迟、Token 吞吐与成本效益推演器"]
        T2_1 --> T2_2 --> T2_3
    end

    subgraph Phase 3 [Phase 3: 大模型智能体评测全景大盘与红蓝攻防工作台]
        UI3_1["UI3.1 RAG 检索召回与上下文溯源透视抽屉"]
        UI3_2["UI3.2 Prompt 红蓝攻防渗透策略与护栏配置弹窗"]
        UI3_3["UI3.3 企业级大模型与智能体综合评测工作台中枢 (/workbench/llm-eval)"]
        UI3_1 --> UI3_2 --> UI3_3
    end

    subgraph Phase 4 [Phase 4: 生产防穿透安全沙箱、合规存证与全量发布]
        T4_1["T4.1 大模型线上接入合规审批与安全强准入看门狗"]
        T4_2["T4.2 大模型评测结论与红蓝攻防验收 64 位 SHA-256 存证证书器"]
        T4_3["T4.3 v6.3.0 大模型与 RAG 智能体评测中台全域综合验收与发布说明"]
        T4_1 --> T4_2 --> T4_3
    end

    Phase 1 --> Phase 2 --> Phase 3 --> Phase 4
```

---

## 2. 任务分解清单 (Phase 1 ~ Phase 4)

### Phase 1：RAG 检索三元组质量评测与幻觉消除引擎

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **RAG 知识检索召回与上下文相关度精算器** | `backend/app/services/llm_rag_triad_evaluator.py` | 实现 RAG 三元组评估：上下文相关度、知识忠实度、回答准确度；单测独立通过；见 docs/evidence/llm-rag-triad-evaluator-t1-1-2026-10-18.md |
| T1.2 `[x]` | **大模型幻觉率统计与事实一致性校验器** | `backend/app/services/llm_hallucination_detector.py` | 自然语言蕴含事实比对，检出无根实体与矛盾断言，计算幻觉率；单测独立通过；见 docs/evidence/llm-hallucination-detector-t1-2-2026-10-18.md |
| T1.3 `[x]` | **大模型评测与 RAG 质量基准 REST API** | `backend/app/api/v1/llm_eval_api.py` | 挂载 `/api/v1/llm-eval/`，提供 RAG 评测打分、幻觉检测与基准作业端点；单测独立通过；见 docs/evidence/llm-eval-api-t1-3-2026-10-18.md |

---

### Phase 2：Prompt 越狱注入攻防与有害内容安全护栏看门狗

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **Prompt 注入与越狱对抗攻击渗透变异器** | `backend/app/services/llm_red_teaming_attacker.py` | 支持 DAN、多语言编码、指令覆盖与角色伪装等红蓝攻防变异算子；单测独立通过；见 docs/evidence/llm-red-teaming-attacker-t2-1-2026-10-18.md |
| T2.2 `[x]` | **大模型有害内容与毒性安全护栏看门狗** | `backend/app/services/llm_safety_guardrails.py` | 实时审查敏感词、隐私 PII 与越权攻击，毫秒级触发安全阻断（Blocked）；单测独立通过；见 docs/evidence/llm-safety-guardrails-t2-2-2026-10-18.md |
| T2.3 `[x]` | **大模型推理延迟、Token 吞吐与成本效益推演器** | `backend/app/services/llm_economics_benchmarker.py` | 采集并推导 TTFT、生成速率 TPS 与 Token 消耗计费性价比；单测独立通过；见 docs/evidence/llm-economics-benchmarker-t2-3-2026-10-18.md |

---

### Phase 3：大模型智能体评测全景大盘与红蓝攻防工作台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[x]` | **RAG 检索召回与上下文溯源透视抽屉** | `frontend/src/views/workbench/components/LlmRagInspectionDrawer.vue` | 呈现 Query、知识库检索 Chunk 相关度热力图与模型回答引用溯源；单测独立通过；见 docs/evidence/llm-rag-inspection-drawer-ui3-1-2026-10-18.md |
| UI3.2 `[x]` | **Prompt 红蓝攻防渗透策略与护栏配置弹窗** | `frontend/src/views/workbench/components/LlmRedTeamConfigModal.vue` | 可视化交互配置攻防测试套件、护栏敏感度与模型调用参数；单测独立通过；见 docs/evidence/llm-red-team-config-modal-ui3-2-2026-10-19.md |
| UI3.3 `[ ]` | **企业级大模型与智能体综合评测工作台中枢页面** | `frontend/src/views/workbench/LlmEvalWorkbenchView.vue` | 落地路由 `/workbench/llm-eval`，集成 4 大 Bento KPI 与模型评测大盘；单测独立通过。 |

---

### Phase 4：生产防穿透安全沙箱、合规存证与全量发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[ ]` | **大模型线上接入合规审批与安全强准入看门狗** | `backend/app/services/llm_eval_safety_boundary_guard.py` | 生产模型上线三要素校验（安全评测审批单、模型白名单与访问鉴权令牌）；单测独立通过。 |
| T4.2 `[ ]` | **大模型评测结论与红蓝攻防验收 64 位 SHA-256 存证证书器** | `backend/app/services/llm_evidence_signer.py` | 规范化确定性 JSON，签发不可篡改的 64 位 SHA-256 指纹与 HMAC-SHA256 签名存证证书；单测独立通过。 |
| T4.3 `[ ]` | **v6.3.0 大模型与 RAG 智能体评测中台全域综合验收与发布说明** | 全局回归与文档 | 全套后端与前端测试 100% PASS，归档 `docs/v6.3.0-release-notes.md` 与专项交付证据。 |

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
   - `vite build` 生产打包成功；
   - 全面遵循 ATP 设计系统主规范（零硬编码色值，严格 Token 化）。
3. **专项证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
