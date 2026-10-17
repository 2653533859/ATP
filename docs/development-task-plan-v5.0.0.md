# ATP v5.0.0 研发任务规划与执行计划 (2026-10-17)

## 1. 版本背景与目标 (Executive Scope)

在 ATP 完成了全链路分布式追踪中台（v4.9.0）后，自动化测试平台在服务端链路端到端排障能力已达到行业领先水平。根据平台技术演进基线规划（`docs/current-capability-baseline-2026-10-15.md`），平台下一代核心突破点聚焦于**移动测试真机集群建设**：
**ATP v5.0.0 目标打造企业级 iOS 真机池化调度与异构移动设备反向隧道协同中台 (iOS Real Device Pooling & Multi-OS Mobile Tunnel Hub)**。

借鉴成熟的 AutoDroid 反向隧道与租约行销架构，打破以往 iOS 自动化强依赖独立单机本地连线的限制，实现：
1. **反向隧道穿透 (Phase 1)**：通过 WebSocket 隧道技术将分散在 macOS Worker / 测试实验室物理机上的 iPhone WDA（WebDriverAgent 8100 端口）透明映射至 ATP 服务端动态端口；
2. **真机池化与排他租约调度 (Phase 2)**：提供秒级排他性设备租约竞拍、防死锁心跳探针与跨端统一设备调度器（Android & iOS 统一资产分配）；
3. **交互式投屏与远程中枢 (Phase 3)**：Vue 3 前端提供低延迟 iOS 屏幕镜像投屏、触控手势同步、Home 键动作触发与设备资产全景管理大盘；
4. **崩溃捕获、签名验真与发布 (Phase 4)**：提供 iOS syslog/Crash 崩溃堆栈自动抓取与 IPA 签名合规校验，最终通过全量工程门禁并完成发布。

---

## 2. 任务清单 (Phase 1 ~ Phase 4)

### Phase 1：iOS 设备反向隧道与 WDA 端口自动穿透桥接器

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T1.1 `[x]` | **WDA 反向 WebSocket 隧道与端口分配器** | `backend/app/services/ios_tunnel_bridge.py` | 实现远端 iOS 物理节点反向 WebSocket 注册、WDA 8100 端口双向数据中继与本地隧道端口动态分配；单测独立通过；见 docs/evidence/ios-tunnel-bridge-t1-1-2026-10-17.md |
| T1.2 `[x]` | **iOS 设备心跳保活与状态巡检探针** | `backend/app/services/ios_device_heartbeat_keeper.py` | 实现秒级探针健康巡检，自动识别心跳失联、WDA 崩溃并执行自动标记 OFFLINE 与自愈；单测独立通过；见 docs/evidence/ios-device-heartbeat-keeper-t1-2-2026-10-17.md |
| T1.3 `[x]` | **iOS 设备隧道连接与状态管理 REST API** | `backend/app/api/v1/ios_tunnel_api.py` | 暴露 `/ios/tunnel/register`、`/ios/tunnel/status`、`/ios/tunnel/devices` 等接口；单测独立通过；见 docs/evidence/ios-tunnel-api-t1-3-2026-10-17.md |

---

### Phase 2：iOS 真机租约调度与并发排他抢占控制

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T2.1 `[x]` | **iOS 真机排他性租约调度与自动续期管理器** | `backend/app/services/ios_lease_scheduler.py` | 实现严格防死锁排他性租约抢占（Acquire/Heartbeat/Release），支持租约超时自动回收；单测独立通过；见 docs/evidence/ios-lease-scheduler-t2-1-2026-10-17.md |
| T2.2 `[x]` | **WDA 会话代理与生命周期初始化预热器** | `backend/app/services/ios_wda_session_manager.py` | 实现 WDA `/status` 连通性预热、前置 App 清理、实时屏幕截图获取与 Session 生命周期守护；单测独立通过；见 docs/evidence/ios-wda-session-manager-t2-2-2026-10-17.md |
| T2.3 `[x]` | **跨端移动设备统一分配器** | `backend/app/services/cross_platform_device_pool_allocator.py` | 统一抽象 Android (ADB) 与 iOS (WDA) 设备池，按 OS/版本/空闲状态自动匹配调度；单测独立通过；见 docs/evidence/cross-platform-device-pool-allocator-t2-3-2026-10-17.md |

---

### Phase 3：iOS 真机交互式投屏与远程控制中枢

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| UI3.1 `[x]` | **iOS 交互式投屏与远程控制抽屉组件** | `frontend/src/views/device/components/IosScreenMirrorModal.vue` | 实现 iOS 屏幕实时画面展示、鼠标点击/拖拽滑动换算为 WDA 触控坐标并下发执行、支持 Home 键；单测独立通过；见 docs/evidence/ios-screen-mirror-modal-ui3-1-2026-10-17.md |
| UI3.2 `[x]` | **iOS 真机资产池卡片与状态监控组件** | `frontend/src/views/device/components/IosDevicePoolCard.vue` | 呈现真机设备卡片（状态角标、租约持有人、系统版本、WDA 端口与一键租用）；单测独立通过；见 docs/evidence/ios-device-pool-card-ui3-2-2026-10-17.md |
| UI3.3 `[x]` | **iOS 真机池化调度与远程管理中心页面** | `frontend/src/views/device/IosDeviceCenterView.vue` | 落地路由 `/devices/ios-center`，集成设备池监控、快速租约申领与批量巡检；单测独立通过；见 docs/evidence/ios-device-center-view-ui3-3-2026-10-17.md |

---

### Phase 4：iOS 自动化执行容灾、合规凭证与全量发布

| ID / 状态 | 任务名称与交付物 | 依赖 | 验收标准 |
|---|---|---|---|
| T4.1 `[x]` | **iOS 崩溃堆栈捕获与 Syslog 实时归档器** | `backend/app/services/ios_crash_and_syslog_collector.py` | 当执行中断或 App 闪退时自动拉取 syslog 并提取 crashlog 符号化异常；单测独立通过；见 docs/evidence/ios-crash-and-syslog-collector-t4-1-2026-10-17.md |
| T4.2 `[x]` | **IPA 签名合规与 Provisioning 描述文件验真器** | `backend/app/services/ios_ipa_signing_validator.py` | 校验 IPA 包的 TeamID、BundleID 与证书有效期，防范因证书失效导致安装失败；单测独立通过；见 docs/evidence/ios-ipa-signing-validator-t4-2-2026-10-17.md |
| T4.3 `[x]` | **v5.0.0 iOS 移动真机中台综合验收与发布说明** | 全局回归与文档 | 全套后端与前端测试 100% PASS，归档 `docs/v5.0.0-release-notes.md` 与专项交付证据；见 docs/evidence/v5-0-0-ios-real-device-pooling-summary-acceptance-2026-10-17.md |

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
