# T1.2 动态多目标加权并发路由引擎服务验收 (2026-10-17)

## 概述与交付物

T1.2（动态多目标加权并发路由引擎服务）已全量研发交付并通过各项质量门禁，**达成 ATP v5.4.0 Phase 1 第二个核心调度里程碑**：
1. **任务规格需求建模 (`TaskExecutionRequirement`)**：
   - 包含任务标识、目标平台（iOS / Android）、指定设备偏好、最低电量门限（默认 20%）、最高温度耐受门限（默认 42°C）及任务优先级 `TaskPriority`（CRITICAL / HIGH / NORMAL / LOW）。
2. **多目标加权适应度打分模型 (`evaluate_device_fitness`)**：
   - 四维适应度得分：
     - 设备健康度得分：权重 40%（基于 T1.1 多维健康遥测）；
     - 算力负载余量得分：权重 30%（空闲并发越多得分越高）；
     - 隧道通信 RTT 时延优势：权重 20%；
     - 亲和度奖励加分：权重 10%（匹配用户指定偏好设备时奖励 100 分）。
3. **最优派发与配额租约管理 (`route_and_lease_device` & `release_device_lease`)**：
   - 全局筛选符合准入门槛的同构真机，按综合适应度由高到低排序挑出最佳设备（`Best-Fit Device`）；
   - 成功路由后，原子性自增当前并发计数（`current_concurrency += 1`）并记录活动租约；
   - 任务完结或异常退出后，支持可靠释放配额租约（`release_device_lease`）；
   - 全集群暂无合规空闲真机时，自适应返回 `QUEUED` 排队缓冲状态；未配置该平台设备时返回 `NO_AVAILABLE_DEVICE`。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_fleet_concurrency_router.py`：4 passed（最优健康设备自动挑选与并发租约锁定/释放、全过热时自适应进入 QUEUED 缓冲、无注册设备时 NO_AVAILABLE_DEVICE 判定、调度历史检索与字典序列化）；
   - **通过率**：**4/4 passed in 0.32s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：2/2 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
