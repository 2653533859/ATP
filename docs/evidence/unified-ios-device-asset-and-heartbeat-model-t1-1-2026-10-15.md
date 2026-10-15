# T1.1 iOS 统一设备资产与在线心跳模型验收（2026-10-15）

## 概述与结论

T1.1（iOS 统一设备资产与在线心跳模型）已完成核心代码演进与自动化质量验证：
1. **iOS 设备统一资产管理服务 (`backend/app/services/ios_device_manager.py`)**：
   - 实现了 `register_or_heartbeat_ios_device`：支持根据 UDID 注册全新 iOS 设备或自动刷新心跳与在线状态，更新时保持执行中的 `busy` 状态防冲突；
   - 实现了 `mark_stale_ios_devices_offline`：自动扫描心跳超时（默认 120 秒）的存活设备并将其收敛为 `offline`；
   - 实现了 `probe_ios_wda_health`：支持对 Appium Server / WebDriverAgent `/status` 端点进行连通性与就绪状态探针；
   - 实现了 `format_unified_device` 与 `get_unified_device_list`：建立标准跨平台统一设备模型（`UnifiedDeviceOut`），打通 Android（`serial`）与 iOS（`udid`, `wda_local_port`, `appium_server_url`）集中资产视图。
2. **REST API 统一端点与心跳刷新 (`devices.py` / `ios.py`)**：
   - 开放 `GET /api/v1/devices/unified` 端点，支持按 `platform`（`all`, `android`, `ios`）与 `status`（`online`, `busy`, `offline`）多维过滤，供前端与调度中枢一站式拉取全端设备池；
   - 开放 `POST /api/v1/ios-devices/{device_id}/heartbeat` 端点，供 macOS Worker 或 iOS Agent 定期保持设备活跃与状态自愈。

---

## 质量门禁与验证

1. **专项自动化测试**：
   - `backend/tests/services/test_ios_device_manager.py`：**6 passed in 2.81s**（覆盖新设备注册、旧设备心跳刷新与 busy 状态保留、超时离线收敛、统一跨端格式转换、跨平台统一设备列表过滤、WDA /status 探针）；
   - 回归测试：`test_ios_routes.py` 等 6 项 iOS 路由测试全量通过；
   - `scripts/pytest-standalone-sweep.py`：**1 passed, 0 failed standalone**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 195 source files**。
