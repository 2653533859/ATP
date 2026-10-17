# T4.1 任务调度风暴熔断防雪崩看门狗服务验收 (2026-10-17)

## 概述与交付物

T4.1（任务调度风暴熔断防雪崩看门狗服务）已全量研发交付并通过各项工程门禁，**正式开启 ATP v5.4.0 Phase 4（调度风暴防范、合规存证与全量发布）关键防护里程碑**：
1. **多重防风暴雪崩防护机制 (`backend/app/services/fleet_storm_guard.py`)**：
   - **平滑令牌桶速率限制 (`Token Bucket Rate Limiter`)**：
     - 配置最大突发容量（30 个令牌）与平滑补充速率（10 个/秒），超频请求裁决为 `RATE_LIMITED`，削减瞬间任务洪峰；
   - **连续失败熔断断路器 (`Circuit Breaker`)**：
     - 状态机：`CLOSED`（畅通）➔ `OPEN`（熔断开启，快速失败阻断）➔ `HALF_OPEN`（半开试探恢复）；
     - 当连续 5 次调度失败或滑动窗口失败率突破 60% 时，立即触发熔断保护，防止真机群因雪崩级重试直接瘫痪；
     - 冷却周期结束后进入半开状态，两次连续探测成功自动复位为 `CLOSED`；
   - **全抖动指数退避算法 (`calculate_jittered_backoff`)**：
     - `Full Jitter` 随机离散化重试间隔，彻底消除微服务与物理真机重试共振；
   - **违规审计与状态监控**：记录拦截事件，支持手动复位断路器。
2. **REST API 端点拓展 (`backend/app/api/v1/fleet_scheduler_api.py`)**：
   - `POST /api/v1/scheduler/storm/evaluate`：派发前执行风暴与熔断阻断评估；
   - `GET /api/v1/scheduler/storm/status`：查看断路器与令牌桶当前状态；
   - `POST /api/v1/scheduler/storm/reset`：运维手动复位断路器。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_fleet_storm_guard.py`：4 passed（正常放行、连续失败触发 OPEN 熔断、手动复位断路器、全抖动退避计算）；
   - `backend/tests/api/test_fleet_scheduler_api.py`：6 passed；
   - **总体通过率**：**28 passed across all Phase 1 ~ 4 backend test files (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：7/7 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**4 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
