# N2.2 / N2.5 真机 Scrcpy 实时流、接口场景编排与 APP 自动化工作台闭环（2026-10-15）

## 概述与结论

本次交付涵盖 **真机 Scrcpy 60FPS 硬解实时流与控制**、**接口自动化多步场景编排** 以及 **APP 自动化工作台用例就地创建/编辑闭环**，并经受 4 节点并发 Code Review 针对安全漏洞、资源竞争与死锁缺陷的专项加固。

### 核心能力落地

1. **真机 Scrcpy 硬件直解 60FPS 实时流与零延迟触控**：
   - 后端基于 `scrcpy-server` 与 WebCodecs H.264 Annex-B 裸流切片，建立双向全双工 WebSocket (`/ws/scrcpy/{serial}`)；
   - WebSocket 增加基于 HttpOnly Cookie (`settings.ACCESS_COOKIE_NAME`) 与 Query Token 的双重身份认证，拒绝未授权访问（WS 1008 Policy Violation）；
   - 备用 REST 触控与重连接口 (`POST /devices/{serial}/touch`、`POST /devices/{serial}/reconnect`) 集中挂载在 `/api/v1/`，并通过 `Depends(get_current_user)` 实施严格鉴权；
   - 增加 `_sanitize_adb_input_text` 安全转义机制，防范 ADB Fallback 下的 Shell 元字符注入风险并将空格转为 `%s`；
   - 增加 `_cleanup_device` 与终态资源回收机制，在读取线程断开时彻底回收 27183~27283 端口池并清理 ADB forward 规则，根治端口耗尽隐患；
   - 增加 `ClientStream` 结构体，消除客户端断开时由于线程池阻塞导致 `generator.close()` 触发 `ValueError` 的并发竞争；关键帧入队前进行去重，避免重复连续推入两次关键帧；
   - 前端画布过滤鼠标非主按键（`e.button !== 0`），杜绝原生右键菜单吞掉 `mouseup` 导致的触控死锁与 WebSocket 报文泛洪；
   - 移除模态框 60ms 延时硬编码竞态，改用 `nextTick` 结合异步轮询等待 Canvas DOM 挂载就绪；
   - `DeviceList.vue` 彻底移除内联投屏模态框与触控逻辑，直接复用 `<DeviceMirrorModal>`，消除近 400 行重复代码与技术债务。

2. **接口自动化多步骤场景编排 (ApiScenarioOrchestrator)**：
   - 支持将多个单接口调试/用例一键批量编排为自动化场景，自动建立步骤依赖链（`depends_on: [i - 1]`）；
   - 支持单步调试、响应提取与断言测试，提供保存为场景或独立用例能力；
   - `resolveJsonPathValue` 扩展支持 `^[(\d+)]$` 根级数组字段解析（如 `$[0].id`）；
   - 修复场景编排器 `handleMoreMenu` 菜单分支，补充「清空调试结果」（`clear_debug`）独立实现并修正「新建空白场景」文案；
   - 后端 `api_scenarios.py` 改用临时文件 + `replace` 原子写入保护，并在异常时自动备份 `.corrupted`，杜绝文件损坏导致的场景数据丢失；
   - 增加针对目标项目的严格权限校验（`assert_project_access`），杜绝跨项目越权访问与修改。

3. **APP 自动化工作台用例创建/编辑闭环 (AppWorkbenchView)**：
   - 工作台就地集成移动端用例抽屉 `AndroidCaseDrawer.vue`，支持配置设备矩阵、录屏开关、APK 资产、低代码步骤与 UiAutomator2 脚本；
   - 顶部工具栏增加高亮 `[+ 新建 Android 用例]`，启动台增加创建与就地编辑按钮；
   - 针对 0 用例项目提供设计系统规范的虚线冷启动引导卡片（Empty State CTA）；
   - 工作台数据加载时同步拉取项目模块列表，解析出合法的 `defaultModuleId` 传入抽屉；并在抽屉内补充模块自动回退机制，彻底根治后端 `TestCaseCreate` 因 `module_id=null` 抛出 HTTP 422 的校验缺陷；
   - 补充 `canModify` 权限校验防止未授权编辑穿透；
   - 补充完善中英文 i18n 语言词条。

---

## 变更文件清单

| 文件 | 变更说明 |
|---|---|
| `backend/app/device_stream/manager.py` | 增加文本注入转义、ClientStream 优雅退出、端口终态回收与关键帧去重 |
| `backend/app/device_stream/router.py` | 增加 WebSocket Cookie/Token 鉴权保护与 ClientStream 优雅关闭 |
| `backend/app/api/v1/router.py` | 统一包含 `scrcpy_rest_router` 与 `api_scenarios.router`，收归 `/api/v1/` 统一前缀 |
| `backend/app/main.py` | 优化路由挂载与 Scrcpy manager 进程清理，保留 WebSocket 视频流通道 |
| `backend/app/api/v1/api_scenarios.py` | 接口场景 CRUD 原子保存与项目访问权限校验 |
| `backend/tests/services/test_scrcpy_stream.py` | 补充安全转义、ClientStream 退出与端口回收测试，全量 7 项测试通过 |
| `backend/tests/services/test_api_scenario.py` | 补充原子保存与损坏文件备份恢复测试，全量 8 项测试通过 |
| `frontend/src/views/workbench/AppWorkbenchView.vue` | 挂载 `AndroidCaseDrawer`，新增新建/编辑按钮、空状态引导卡片、模块绑定与鉴权守卫 |
| `frontend/src/views/workbench/AppWorkbenchView.spec.ts` | 补充创建、编辑、保存闭环、模块加载及空状态卡片单测覆盖 |
| `frontend/src/views/workbench/ApiWorkbenchView.vue` | 场景编排集成、下拉菜单、保存状态就地增量合并、项目切换重置及权限守卫 |
| `frontend/src/views/workbench/ApiWorkbenchView.spec.ts` | 补充场景保存状态保留、项目切换清理及菜单操作单测覆盖 |
| `frontend/src/views/workbench/components/ApiScenarioOrchestrator.vue` | 修复菜单分支与清空调试逻辑，增强 JSONPath 根数组解析语法 |
| `frontend/src/views/case/AndroidCaseDrawer.vue` | 补充 `projectApi.getModules` 根模块自动回退机制 |
| `frontend/src/views/device/DeviceList.vue` | 移除约 400 行重复投屏模态框与控制代码，直接复用 `DeviceMirrorModal` |
| `frontend/src/views/device/components/DeviceMirrorModal.vue` | 补充鼠标主按键 `e.button !== 0` 过滤，统一防范触控死锁 |
| `frontend/src/locales/zh-CN.ts` & `en-US.ts` | 同步补充 APP 工作台与 API 场景编排的中英文语言词条 |

---

## 质量门禁与验证

1. **后端验证**：
   - `pytest backend/tests/services/test_scrcpy_stream.py`：**7 passed in 0.68s**；
   - `pytest backend/tests/services/test_api_scenario.py`：**8 passed in 0.58s**；
   - `ruff check` 检查后端路由、main、device_stream、api_scenarios：**All checks passed**。
2. **前端类型检查**：
   - `vue-tsc --noEmit -p frontend/tsconfig.json`：**0 error**，全类型推导完全一致。
3. **前端单元测试矩阵**：
   - `AppWorkbenchView.spec.ts`：**8 passed**；
   - `ApiWorkbenchView.spec.ts`：**12 passed**；
   - `DeviceList.spec.ts`：**7 passed**；
   - `DeviceMirrorModal.spec.ts`：**4 passed**；
   - 全量前端 Vitest 套件：**83 个测试套件，398 项测试 100% 全部通过**（耗时 23.47s）。
