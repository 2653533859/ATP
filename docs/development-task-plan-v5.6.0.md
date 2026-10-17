# ATP v5.6.0 研发任务规划：生产流量可信回放与真实场景变异演练中台 (Production Traffic Replay & Synthetic Chaos Mutation Hub)

**规划日期**：2026-10-17
**版本代号**：**Traffic Replay & Chaos Mutation Evolution**
**核心目标**：彻底解决线下自动化测试无法覆盖生产长尾边缘链路的难题，构建端到端生产流量脱敏镜像、双端响应差异比对与噪声消除、回放工作台以及只读防击穿安全围栏。实现生产真实业务场景 100% 可信回放与变异演练。

---

## 1. 架构设计与系统全景拓扑

```mermaid
flowchart TD
    subgraph Phase 1 [Phase 1: 生产流量脱敏镜像与分布式录制过滤器]
        T1_1["T1.1 敏感数据实时脱敏与隐私字段掩码器 (traffic_sanitization_masker)"]
        T1_2["T1.2 分布式流量镜像采集与流量抽样过滤器 (traffic_mirror_sampler)"]
        T1_3["T1.3 流量录制集管理与回放检索 REST API (/api/v1/traffic-replay/*)"]
        T1_1 --> T1_2 --> T1_3
    end

    subgraph Phase 2 [Phase 2: 智能响应差异比对与自适应噪声消除器]
        T2_1["T2.1 双端响应体深度结构 Diff 对比器 (traffic_response_diff_comparator)"]
        T2_2["T2.2 动态字段动态噪声自适应抑制器 (dynamic_noise_suppressor)"]
        T2_3["T2.3 回放偏离评分与 Breaking Change 裁决控制器 (replay_drift_evaluator)"]
        T2_1 --> T2_2 --> T2_3
    end

    subgraph Phase 3 [Phase 3: 流量回放中枢与变异演练工作台]
        UI3_1["UI3.1 双端响应结构差异透视对比抽屉 (TrafficDiffInspectionDrawer.vue)"]
        UI3_2["UI3.2 动态噪声过滤规则配置与模拟弹窗 (NoiseFilterRuleModal.vue)"]
        UI3_3["UI3.3 生产流量回放与变异演练工作台中枢 (/workbench/traffic-replay)"]
        UI3_1 --> UI3_2 --> UI3_3
    end

    subgraph Phase 4 [Phase 4: 外部调用防击穿安全沙箱、合规存证与全量发布]
        T4_1["T4.1 第三方服务防击穿与写操作拦截看门狗 (traffic_write_blast_guard)"]
        T4_2["T4.2 流量回放与 Diff 报告 64 位 SHA-256 存证证书器 (replay_evidence_signer)"]
        T4_3["T4.3 v5.6.0 生产流量回放中台综合验收与发布说明 (v5.6.0-release-notes)"]
        T4_1 --> T4_2 --> T4_3
    end

    Phase 1 --> Phase 2 --> Phase 3 --> Phase 4
```

---

## 2. 任务分解清单 (Phase 1 ~ Phase 4)

### Phase 1：生产流量脱敏镜像与分布式录制过滤器

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[ ]` | **敏感数据实时脱敏与隐私字段掩码器** | `backend/app/services/traffic_sanitization_masker.py` | 自动识别手机号、身份证、银行卡、密码、JWT Token与敏感 Header/Query，支持哈希/掩码/加盐置换；单测独立通过。 |
| T1.2 `[ ]` | **分布式流量镜像采集与流量抽样过滤器** | `backend/app/services/traffic_mirror_sampler.py` | 支持按 URL 模式、HTTP 方法、状态码与指定采样率（1%~100%）过滤流量，并自动剔除健康检查探针；单测独立通过。 |
| T1.3 `[ ]` | **流量录制集管理与回放检索 REST API** | `backend/app/api/v1/traffic_replay_api.py` | 挂载 `/api/v1/traffic-replay/*`，提供流量脱敏校验、录制集持久化、按条件检索与批量调度回放端点；单测独立通过。 |

---

### Phase 2：智能响应差异比对与自适应噪声消除器

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[ ]` | **双端响应体深度结构 Diff 对比器** | `backend/app/services/traffic_response_diff_comparator.py` | 深度比对基线与回放响应，精确识别键丢失、值变化、类型不匹配与状态码偏离；单测独立通过。 |
| T2.2 `[ ]` | **动态字段动态噪声自适应抑制器** | `backend/app/services/dynamic_noise_suppressor.py` | 自动识别时间戳、自增 ID、UUID、随机 Token 与 TraceID 等动态噪声字段，并支持基于正则与 JSONPath 自适应平滑忽略；单测独立通过。 |
| T2.3 `[ ]` | **回放偏离评分与 Breaking Change 裁决控制器** | `backend/app/services/replay_drift_evaluator.py` | 输出 0~100 流量回放一致性综合评分，划分 Breaking / Non-Breaking 变迁等级，支持自动裁决；单测独立通过。 |

---

### Phase 3：流量回放中枢与变异演练工作台

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[ ]` | **双端响应结构差异透视对比抽屉** | `frontend/src/views/workbench/components/TrafficDiffInspectionDrawer.vue` | 左右分栏高亮展示生产基线响应与线下回放响应，清晰标注新增、修改、丢失及噪声忽略节点；单测独立通过。 |
| UI3.2 `[ ]` | **动态噪声过滤规则配置与模拟弹窗** | `frontend/src/views/workbench/components/NoiseFilterRuleModal.vue` | 支持可视交互式配置 JSONPath/Regex 噪声规则并提供实时测试校验；单测独立通过。 |
| UI3.3 `[ ]` | **生产流量回放与变异演练工作台中枢页面** | `frontend/src/views/workbench/TrafficReplayWorkbenchView.vue` | 落地路由 `/workbench/traffic-replay`，集成 4 大 Bento KPI、大盘流水与批量回放操作；单测独立通过。 |

---

### Phase 4：外部调用防击穿安全沙箱、合规存证与全量发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[ ]` | **第三方服务防击穿与写操作拦截看门狗** | `backend/app/services/traffic_write_blast_guard.py` | 严防回放过程中对外部第三方支付、短信网关或写入端点造成真实外部调用，提供安全 Mock 旁路或强行拦截；单测独立通过。 |
| T4.2 `[ ]` | **流量回放与 Diff 报告 64 位 SHA-256 存证证书器** | `backend/app/services/replay_evidence_signer.py` | 为流量回放执行记录与响应比对报告签发不可篡改 SHA-256 + HMAC 存证证书；单测独立通过。 |
| T4.3 `[ ]` | **v5.6.0 生产流量回放中台综合验收与发布说明** | 全局回归与文档 | 全套后端与前端测试 100% PASS，归档 `docs/v5.6.0-release-notes.md` 与专项交付证据。 |

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
