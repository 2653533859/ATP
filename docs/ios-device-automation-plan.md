# iOS 设备自动化扩展规划

本文档用于记录 ATP iOS 真机 / 模拟器自动化能力的架构与环境验收计划。仓库已经完成 iOS 执行链路的代码主链：iOS 资产、专用 `ios` 队列、设备租约、W3C/Appium 执行器、低代码步骤、截图/录屏/syslog 产物、IPA Bundle ID/版本自动解析和脱敏验收脚本均已接入；真实 macOS/Xcode/WebDriverAgent/设备环境仍待验收。Android 能力仍基于 ADB / uiautomator2。

## 当前代码状态（2026-08-13）

- 已实现：`IosDevice`/`IosApp` 资产及项目权限隔离、iOS 专用任务路由、设备租约获取/心跳/释放、Appium W3C session、XCUITest capabilities、点击/输入/断言/等待/截图/滑动等受控步骤。
- 已实现：iOS 用例统一结果、截图/录屏/syslog 附件和大小/时长限制；`scripts/ios-appium-acceptance.py` 支持 `/status` 检查，显式 `--session-smoke` 才创建真实会话。
- 待环境验收：macOS Worker、Xcode/签名证书、Appium 2/XCUITest Driver、WebDriverAgent、真实 iPhone/Simulator、IPA 安装与完整任务回传；仓库提供 `scripts/macos-ios-worker.sh doctor/start` 固化前置检查和 `ios` 队列隔离。
- Windows/Linux 只适合运行 status-only 或代码回归，不应将其结果作为真实 iOS 执行通过证据。

## 目标

在不影响现有 Android 执行链路的前提下，为 ATP 增加 iOS 自动化能力，覆盖设备管理、IPA 管理、脚本执行、低代码步骤、报告回传与稳定性治理。

核心原则：

- Android 与 iOS 执行链路并行演进，不将 iOS 逻辑混入 ADB 模块。
- iOS 执行依赖 macOS Worker，不要求 Windows / Linux Worker 直接操控 iPhone。
- 平台侧保留统一用例、统一报告、统一调度模型，执行器侧按平台适配。

```text
ATP Backend
  ├─ Android: ADB + uiautomator2
  └─ iOS: macOS Worker + XCUITest / Appium / WebDriverAgent
```

## 方案选型

### 推荐主方案：Appium 2 + XCUITest Driver

推荐优先采用 Appium 2 + XCUITest Driver，底层通过 WebDriverAgent 调用 Apple XCUITest 能力。

适合场景：

- 平台化接入 iOS 真机、模拟器、原生 App、混合 App、Safari。
- 与现有脚本执行、低代码步骤、报告回传模型对齐。
- 后续接入云真机平台时，可以复用 Appium endpoint 模型。

主要成本：

- 必须准备 macOS Worker。
- 真机执行需要 Xcode、Apple Developer 证书、Team ID、Provisioning Profile。
- WebDriverAgent 构建、签名、端口与会话恢复需要稳定性治理。

### 备选方案

| 方案 | 适合场景 | 主要风险 |
| --- | --- | --- |
| 原生 XCUITest | iOS 团队维护 Swift 测试代码，稳定性优先 | 跨平台统一成本高，平台低代码映射成本高 |
| Appium XCUITest | ATP 平台主方案 | macOS、签名、WDA 维护不可避免 |
| Maestro | YAML 流程体验好，适合低代码 PoC | 真机复杂场景、设备池能力与生态成熟度需验证 |
| WebDriverAgent 直连 | 深度定制、减少 Appium 中间层 | 需要自维护 session、签名、WDA 构建和异常恢复 |
| IDB / libimobiledevice | 设备管理、安装、截图、录屏、辅助能力 | 不适合作为完整 UI 自动化框架 |
| 云真机平台 | 不自建 Mac / iPhone 设备池 | 成本、数据安全、内网访问和调试体验需评估 |

## 建议架构

新增独立 iOS Worker，监听专用 Celery 队列。

```mermaid
flowchart LR
  A["ATP Backend"] --> B["Celery Queue: ios"]
  B --> C["macOS Worker"]
  C --> D["Appium Server"]
  D --> E["XCUITest Driver"]
  E --> F["WebDriverAgent"]
  F --> G["iPhone / iOS Simulator"]
```

建议 Worker 启动方式：

```bash
celery -A app.worker.celery_app worker --loglevel=info -Q ios
```

## 数据模型建议

设备表建议补充平台与 iOS 标识字段：

```text
devices.platform: android | ios
devices.udid
devices.device_name
devices.os_version
devices.connection_type: usb | network
devices.worker_id
```

应用包建议统一为跨平台应用资产：

```text
apps.platform: android | ios
apps.file_type: apk | ipa
apps.bundle_id
apps.version
apps.build_number
```

如当前表结构仍以 Android 命名，可优先新增 iOS 专用表，后续再收敛为跨平台资产模型，避免一次性重构影响 Android 主链路。

## 低代码步骤映射

平台侧保留统一步骤语义：

```text
click
input
swipe
wait
screenshot
assert_visible
assert_text
launch_app
close_app
```

Android 执行器映射到 ADB / uiautomator2，iOS 执行器映射到 Appium XCUITest / WebDriverAgent。

iOS 定位器建议支持：

```text
accessibility_id
ios_predicate
ios_class_chain
xpath
text
```

注意：Android 的 `resourceId`、`uiautomator` selector 不能直接复用于 iOS，需要在前端表单中按平台展示不同定位器选项。

## 分阶段计划

### Phase 1：调研与 PoC

- 准备 macOS Worker。
- 安装 Xcode、Appium 2、XCUITest Driver。
- 跑通 WebDriverAgent 真机签名与启动。
- 手工执行一个 iOS App 点击、输入、截图用例。
- 输出可行性报告，明确真机、模拟器、无线调试、证书管理限制。

### Phase 2：设备与 Worker 接入

- 新增 `ios` Celery 队列。
- 增加 macOS Worker 注册与心跳。
- 支持 iOS 设备扫描，采集 UDID、设备名、系统版本、在线状态。
- 先支持 USB 真机和模拟器，暂不强依赖无线调试。
- 增加设备占用锁，避免同一台设备被并发任务抢占。

### Phase 3：IPA 管理与基础执行

- 支持上传 `.ipa`。
- 记录 bundle id、版本、构建号、签名信息。
- 支持安装、启动、停止、卸载 App。
- 支持脚本模式执行 Appium Python / JavaScript 用例。
- 回传截图、日志、执行状态和基础报告。

### Phase 4：低代码 iOS 执行器

- 将统一低代码步骤映射到 Appium API。
- 支持点击、输入、滑动、等待、截图、断言。
- 前端按平台展示 iOS 定位器配置。
- 报告页展示 iOS 步骤截图、失败原因和原始 Appium error。

### Phase 5：稳定性增强

- WebDriverAgent 自动重启。
- Appium session 创建失败重试。
- 设备离线检测与任务失败收敛。
- 多设备并发控制。
- 执行超时、失败清理、日志归档。
- 无线调试支持：通过 Xcode 的 Connect via network 或等价工具链接入。

### Phase 6：可选扩展

- 接入 Maestro 作为第二 iOS 执行后端。
- 接入云真机平台。
- 支持 iOS Safari Web 测试。
- 支持原生 XCUITest 测试包执行。
- 支持 iOS 性能指标采集。

## 最小可落地版本

建议最小版本只覆盖以下能力：

```text
macOS Worker
+ Appium XCUITest
+ iOS 设备扫描
+ IPA 上传
+ 单用例脚本执行
+ 截图 / 日志 / 报告回传
```

该版本可以快速验证 iOS 链路的稳定性、证书成本和平台集成成本，再决定是否继续投入低代码、无线调试和云真机扩展。

## 风险与前置条件

- 必须有可长期运行的 macOS Worker。
- 真机执行需要 Apple 开发者账号与签名配置。
- WebDriverAgent 在不同 iOS / Xcode 版本下可能存在兼容性差异。
- iOS 系统级能力受 Apple 沙箱限制，不能按 Android ADB 的能力边界设计。
- 无线调试稳定性通常低于 USB，应作为增强项而不是首版前置条件。
