# ATP v3.1.0 研发任务规划与执行计划 (2026-10-16)

> 版本定位：**企业级交互工作台与控制台全量落地 (Enterprise Interaction Studio & Operations Center)**
> 承接基准：以 v3.0.0 交付的 12 项后端核心引擎为底座，为微服务录制、真机自愈回放、网关混沌与爆炸半径、以及 OIDC/IAM 审计安全构建现代化前端交互界面与全景控制台。

---

## 1. 阶段划分 (Phase 1 ~ Phase 4)

- **Phase 1：微服务流量录制与用例逆向生成工作台 (Traffic Ingestion & Reverse Synthesis Studio)**
  - 核心目标：提供反向代理流量录制启停控制、实时请求过滤脱敏流展示、动态参数提取与一键逆向用例/套件向导。
- **Phase 2：移动端真机回放与视频关键帧逐帧排障器 (Mobile Playback & Video Frame Inspector)**
  - 核心目标：提供 Android/iOS 真机回放动作编排执行、视觉 OCR/DOM 混合自愈打分比对与 MP4 毫秒级视频帧对齐时间线。
- **Phase 3：微服务网关混沌演练与爆炸半径控制台 (Mesh Chaos & Blast Radius Studio)**
  - 核心目标：提供四大网关故障注入与抽样配置卡片、微服务拓扑图逆向 BFS 级联影响与紧急熔断拦截、以及高可用 SLA 韧性综合看板。
- **Phase 4：企业级 OIDC/SSO 与不可篡改审计安全中心 (IAM, SSO & Tamper-Evident Audit Center)**
  - 核心目标：提供 Keycloak/Okta/ADFS 身份源配置与单点登录面板、细粒度 RBAC 策略在线模拟器、以及类区块链防篡改审计日志校验与合规证明导出。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：微服务流量录制与用例逆向生成工作台 (Traffic Ingestion & Reverse Synthesis Studio)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI1.1 `[x]` | **微服务流量录制会话管理与实时抓包面板** | traffic_recording | 落地 `TrafficRecordingDrawer.vue` 组件与 API 客户端方法；支持录制会话启停、清洗规则配置、脱敏请求流水流式展示与状态卡片；见 docs/evidence/traffic-recording-drawer-ui1-1-2026-10-16.md |
| UI1.2 `[x]` | **动态参数提取与上下文占位符规则配置抽屉** | UI1.1 | 落地 `DynamicParamExtractorDrawer.vue` 组件；支持响应体 JSONPath 递归遍历候选、占位符预览与提取器规则动态注入；见 docs/evidence/dynamic-param-extractor-drawer-ui1-2-2026-10-16.md |
| UI1.3 `[x]` | **录制流量一键逆向合成用例与套件向导弹窗** | UI1.2 | 落地 `TrafficToCaseWizard.vue` 组件；支持按状态码/SLA 自动生成断言并一键持久化保存为 TestCase / TestSuite 资产；见 docs/evidence/traffic-to-case-wizard-ui1-3-2026-10-16.md |

---

### Phase 2：移动端真机回放与视频关键帧逐帧排障器 (Mobile Playback & Video Frame Inspector)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI2.1 `[x]` | **真机回放动作编排执行抽屉与变量上下文配置** | device_playback | 落地 `DevicePlaybackDrawer.vue` 组件；支持跨平台动作序列编排、运行时变量上下文配置与回放执行状态追踪；见 docs/evidence/device-playback-drawer-ui2-1-2026-10-16.md |
| UI2.2 `[ ]` | **视觉/DOM 混合自愈与 OCR 物理边界比对器** | UI2.1 | 落地 `VisualSelfHealingInspector.vue` 组件；呈现 Tier 1~3 启发相似度评分、OCR 点击坐标补偿与自愈前后快照比对。 |
| UI2.3 `[ ]` | **MP4 录屏毫秒级时间线对齐与异常高亮播放器** | UI2.2 | 落地 `PlaybackKeyframeTimeline.vue` 组件；呈现视频时间轴与执行步骤毫秒级对齐、异常高亮与关键帧一键跳转。 |

---

### Phase 3：微服务网关混沌演练与爆炸半径控制台 (Mesh Chaos & Blast Radius Studio)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[ ]` | **微服务网关混沌故障注入规则编排卡片与抽样调节器** | mesh_chaos | 落地 `MeshChaosRuleCard.vue` 组件；支持 503/熔断/延迟/畸形报文 4 类故障动作配置与流量采样比例动态滑块。 |
| UI3.2 `[ ]` | **微服务调用依赖拓扑与爆炸半径逆向 BFS 级联阻断图** | UI3.1 | 落地 `BlastRadiusTopologyGraph.vue` 组件；基于 ECharts 力导向图呈现调用拓扑、级联波及链路与紧急熔断告警。 |
| UI3.3 `[ ]` | **全链路高可用 SLA 韧性评分与自愈 RTO 评级看板** | UI3.2 | 落地 `MeshResilienceReportView.vue` 页面；呈现微服务 SLA 达成度跌幅、RTO 恢复耗时、四维韧性评分（Grade A-F）与加固建议。 |

---

### Phase 4：企业级 OIDC/SSO 与不可篡改审计安全中心 (IAM, SSO & Tamper-Evident Audit Center)

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI4.1 `[ ]` | **企业级 OIDC / OAuth2 身份提供商接入与单点登录卡片** | oidc_sso | 落地 `OidcProviderConfigCard.vue` 组件；展示 Keycloak/Okta/ADFS 提供商列表、敏感凭据脱敏显示与一键 SSO 跳转。 |
| UI4.2 `[ ]` | **细粒度资源操作 RBAC 策略模拟器与 Anti-IDOR 诊断抽屉** | UI4.1 | 落地 `IamPolicySimulatorDrawer.vue` 组件；支持按资源与操作在线模拟 PDP 策略判定、Explicit Deny 提示与跨项目越权诊断。 |
| UI4.3 `[ ]` | **类区块链 SHA-256 审计日志哈希链完整性校验与合规证明导出** | UI4.2 | 落地 `AuditTamperEvidentChainView.vue` 页面；支持链式连续性在线自检、篡改记录高亮定位与带数字签名的合规报表一键导出。 |

---

## 3. 质量门禁规则

1. **类型零报错**：`npm run type-check` (`vue-tsc --noEmit`) 保持 100% 通过。
2. **构建零警告**：`npm run build` (`vite build`) 保持 100% 成功。
3. **单元测试与全覆盖**：所有新增 Vue 组件均配备对应的 `*.spec.ts` 单元测试，Vitest 运行 100% PASS。
4. **专项交付证据链**：每个任务交付均在 `docs/evidence/` 归档带时间戳的完整验证记录。
