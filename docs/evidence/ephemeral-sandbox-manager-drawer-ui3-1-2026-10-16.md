# UI3.1 瞬时轻量级仿真沙箱与端口生命周期管理抽屉验收 (2026-10-16)

## 概述与结论

UI3.1（瞬时轻量级仿真沙箱与端口生命周期管理抽屉）已完成全量交付与验证，正式拉开 **Phase 3（多协议动态仿真沙箱与流量镜像控制台）** 序幕：
1. **API 客户端创建 (`frontend/src/api/sandboxes.ts`)**：
   - 封装 `provision`、`list`、`get`、`terminate`、`reapExpired` 与 `mockDispatch` 6 大核心沙箱接口；
   - 建立 `EphemeralSandboxItem`、`SandboxProtocol`（http/grpc/websocket/multi_protocol）、`SandboxStatus` 与 `MockDispatchResult` 强类型定义。
2. **交互抽屉组件 (`frontend/src/views/workbench/components/EphemeralSandboxManagerDrawer.vue`)**：
   - 支持动态设定会话名称、协议类型与生命周期 TTL 秒数；
   - 一键拉起沙箱实例（底层应用 20000~29999 端口防冲突探测分配）；
   - 一键执行全域过期自动收割（Reap Expired Sandboxes）；
   - 呈现活跃沙箱数（Active 绿）、占用端口总数（Ports Allocated 蓝）、已过期待释放数（Expired 橙）3 大 KPI；
   - 沙箱生命周期流水表格（协议彩色标签、端口与 BaseURL、状态徽标）；
   - 内联 Mock 派发测试弹窗：支持向沙箱实例直接派发 Mock 请求，实时查看返回的 Mock 响应与 JSON 数据。
3. **接口测试工作台集成 (`frontend/src/views/workbench/ApiWorkbenchView.vue`)**：
   - 顶部工具栏挂载「仿真沙箱管理」按钮，支持快捷滑出 960px 抽屉进行全景沙箱管理与调试。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/EphemeralSandboxManagerDrawer.spec.ts`：**3 passed in 83ms**；
   - `src/views/workbench/components/TargetedRegressionWizard.spec.ts`：**3 passed in 74ms**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed in 432ms**；
   - 核心工作台测试套件：**39 passed in 1.87s**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 2.57s, 0 errors**。
