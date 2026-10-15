# C1.3 节点失联与心跳超时自动化任务故障转移与断点重试验收（2026-10-16）

## 概述与结论

C1.3（节点失联与心跳超时自动化任务故障转移与断点重试）已完成全量交付与验证，至此 **v3.2.0 Phase 1（跨节点 Worker 集群自适应负载与动态弹性调度）实现 100% 全量大闭环**：
1. **失联超时与僵死节点自动收割器 (`detect_dead_workers`)**：
   - 动态扫描全集群 Worker 节点心跳时间戳；
   - 超过时效阈值（默认 30s）未上报心跳的节点自动判定失联，原子标记为 `offline` 并清零活跃并发数，防止新任务继续错误派发。
2. **孤儿任务原子抢救与故障转移重试 (`failover_worker_tasks`)**：
   - 精准剥离悬挂在失联 Worker 节点上的 `running` 孤儿任务；
   - 针对未超重试次数的任务递增 `retry_count`，记录 `last_failed_worker_id`，将任务重新置入等待队列并尝试即时分发至其他健康的在线节点；
   - 针对超过最大重试限制（`max_retries`，默认 3 次）的死锁任务，安全标记为 `aborted` 终止态并记录告警。
3. **全网巡检与故障审计历史记录 (`scan_and_recover_dead_workers` & `_FAILOVER_HISTORY`)**：
   - 支持全集群一键巡检收割（Sweep Scan）；
   - 审计记录包含故障转移单号（`report_id`）、失联节点 ID、救援任务计数、永久失败任务计数与诊断描述。
4. **REST API 统一扩展 (`api/v1/cluster_workers.py`)**：
   - `POST /api/v1/cluster/workers/failover/scan`：触发全集群僵死节点扫描与孤儿任务自动故障转移重试；
   - `POST /api/v1/cluster/workers/failover/worker/{worker_id}`：针对指定异常节点强制触发故障转移；
   - `GET /api/v1/cluster/workers/failover/history`：查询集群故障转移审计事件历史。

---

## 质量门禁与验证

1. **专项自动化测试**：
   - `backend/tests/services/test_worker_failover_recovery.py`：**4 passed in 0.27s**（覆盖心跳超时僵死节点检测、孤儿任务抢救并重调度到备用节点、超过重试上限安全标记终止、全网扫描与历史审计记录）；
   - Phase 1 联合回归测试（`test_cluster_load_balancer.py` + `test_adaptive_queue_preemptor.py` + `test_worker_failover_recovery.py`）：**12 passed in 0.30s**；
   - `scripts/pytest-standalone-sweep.py`：**1 passed, 0 failed standalone**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 233 source files**。
