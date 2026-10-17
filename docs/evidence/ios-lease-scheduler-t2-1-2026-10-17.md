# T2.1 iOS 真机排他性租约调度与自动续期管理器验收 (2026-10-17)

## 概述与结论

T2.1（iOS 真机排他性租约调度与自动续期管理器 `ios_lease_scheduler`）已全量交付并完成验证，**标志着 ATP v5.0.0 Phase 2（iOS 真机租约调度与并发排他抢占控制）正式开启并取得首个关键核心突破**：
1. **核心服务实现 (`backend/app/services/ios_lease_scheduler.py`)**：
   - 解决高并发测试与多用户协作环境下的物理 iPhone 设备资源抢占与互斥；
   - **原子性排他租约抢占 (`acquire_ios_lease`)**：
     - 基于设备 UDID 与高熵随机 Token (`ios_lease_<hex>`) 执行原子加锁；
     - 当设备被他人独占且租期未超时时，严格抛出 `IosLeaseConflictError` 并返回当前占用人信息与预计到期时间；
     - 当设备处于离线状态时抛出 `IosDeviceUnavailableError` 阻止无效申请；
     - 成功租用后自动将设备隧道状态置为 `BUSY`；
   - **动态租约心跳续约 (`heartbeat_ios_lease`)**：
     - 支持运行中任务定时续期（默认每次延长 TTL 秒），防止长测试中断；非持有者尝试续约被严格拒绝；
   - **主动释放与管理员强制接管 (`release_ios_lease`, `force_takeover`)**：
     - 执行完毕后主动释放租约，设备隧道状态自动切回 `CONNECTED`；支持管理员特权强制打破死锁；
   - **超时死锁自动扫描回收 (`sweep_expired_ios_leases`)**：
     - 周期性扫描失效僵尸租约，自动解除占用，防止执行器崩溃断网造成真机长期锁死。

## 质量与测试门禁验证

1. **服务单元测试**：
   - `backend/tests/services/test_ios_lease_scheduler.py`：3 passed；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：1/1 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed!**；
   - `ruff format --check`：**All files already formatted.**；
   - `mypy`：**Success: no issues found in 1 source file.**。
