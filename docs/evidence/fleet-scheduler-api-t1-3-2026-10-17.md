# T1.3 集群调度与容量预测 REST API 服务验收 (2026-10-17)

## 概述与交付物

T1.3（集群调度与容量预测 REST API 服务）已全量研发交付并通过各项工程门禁，**标志着 ATP v5.4.0 Phase 1（真机健康多维感知与动态权重路由）全量大闭环**：
1. **API 路由设计与挂载 (`backend/app/api/v1/fleet_scheduler_api.py`)**：
   - 挂载路由前缀 `/api/v1/scheduler/*` 至平台核心路由树；
   - `POST /api/v1/scheduler/telemetry/report`：物理真机实时上报电池温度、电量、CPU、并发水位与隧道 RTT 时延，返回综合健康分与等级；
   - `GET /api/v1/scheduler/devices/telemetry`：查询集群所有物理真机实时遥测健康列表，支持按平台（`ios` / `android`）过滤与健康度降序排列；
   - `POST /api/v1/scheduler/route/dispatch`：为待执行任务自适应挑选全局最优匹配真机，锁定并发配额租约；
   - `POST /api/v1/scheduler/route/release`：任务完结时可靠释放物理真机并发配额；
   - `GET /api/v1/scheduler/capacity/summary`：聚合集群设备总数、健康/过热/低电量/离线分类计数、总可用并发容量、当前已用并发与集群平均环境指标；
   - `GET /api/v1/scheduler/routing/history` & `/{decision_id}`：调度决策流水与详情审计查询。
2. **架构闭环**：
   - 贯通底层遥测数据采集、中央加权打分匹配、任务租约锁定与高并发容量监控。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_fleet_health_telemetry.py`：4 passed；
   - `backend/tests/services/test_fleet_concurrency_router.py`：4 passed；
   - `backend/tests/api/test_fleet_scheduler_api.py`：4 passed（遥测上报与列表查询、任务自适应派发与配额释放全流程、集群容量大盘统计计算、404 处理）；
   - **总体通过率**：**12 passed across all Phase 1 backend test files (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：3/3 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**7 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
