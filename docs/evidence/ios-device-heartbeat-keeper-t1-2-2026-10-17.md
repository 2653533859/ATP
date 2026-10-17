# T1.2 iOS 设备心跳保活与状态巡检探针验收 (2026-10-17)

## 概述与结论

T1.2（iOS 设备心跳保活与状态巡检探针 `ios_device_heartbeat_keeper`）已全量交付并完成验证，**为 ATP v5.0.0 iOS 移动真机中台构建起秒级故障侦测与自愈巡检防线**：
1. **核心服务实现 (`backend/app/services/ios_device_heartbeat_keeper.py`)**：
   - **秒级心跳上报与状态沉淀 (`record_ios_heartbeat`)**：
     - 实时接收 macOS Agent 物理真机上报指标：电量百分比、是否正在充电、设备温度（摄氏度）与 WDA 探针存活标记；
     - 自动判定当前状态：`ONLINE`（健康存活）、`WDA_UNHEALTHY`（WDA 服务异常）；
   - **失联超时巡检扫描 (`sweep_ios_heartbeats`)**：
     - 周期性扫描全部已注册真机时戳，默认超时（15 秒）未收到心跳的设备自动转换为 `OFFLINE`，并标记 `wda_alive = False`；
   - **WDA 异常主动自愈恢复 (`trigger_wda_self_healing`)**：
     - 当捕获到 WDA 崩溃时，支持下发拉起重连指令，自动恢复设备至 `ONLINE` 健康态。

## 质量与测试门禁验证

1. **服务单元测试**：
   - `backend/tests/services/test_ios_device_heartbeat_keeper.py`：3 passed；
   - `backend/tests/services/test_ios_tunnel_bridge.py`：2 passed；
   - 总体通过率：**5 passed (0.32s, 100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：2/2 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed!**；
   - `ruff format --check`：**All files already formatted.**；
   - `mypy`：**Success: no issues found in 1 source file.**。
