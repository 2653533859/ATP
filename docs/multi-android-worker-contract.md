# 多主机 Android Worker 改造契约（Phase 0 冻结）

> 本契约作为 Phase 1 ~ Phase 4 实施的唯一准绳，冻结调用方字段、节点身份、代次、超时阈值、扫描聚合响应、错误码与模式切换配置。

---

## 一、调用方盘点与路由契约

| 调用方 / 模块 | 现行定位方式 | 一期改造后传递/解析字段 | 目标队列 / 行为 | 历史配置兼容规则 |
| :--- | :--- | :--- | :--- | :--- |
| **设备列表 / 扫描**<br>`api/v1/devices.py` | 无 `worker_id`，`POST /devices/scan` 投 `android` | `GET /devices?worker_id=`；`POST /devices/scan` 接收可选 `worker_id` | 指定则投 `android.<worker_id>`；未指定则向快照内所有在线节点分别投递并聚合 | 单节点兼容模式下保持单扫描响应，前端同时兼容单条与聚合响应 |
| **网络 ADB 连接/断开**<br>`api/v1/devices.py` | 直接在 Backend Pod 调 `async_connect_remote_device` | `POST /devices/connect` 必选 `worker_id`（`worker` 模式下）；`disconnect` 按 `device_id` 或 `(worker_id, serial)` | 投递 `run_android_device_operation("connect"/"disconnect")` 至 `mobile_special.<worker_id>` 并触发该节点扫描同步 | 仅 `ADB_SCAN_MODE=local` 时允许在本地进程直接执行 |
| **远程调试 / 镜像**<br>`api/v1/device_mirror.py` | 按 `device_id` 查 `device.serial` 后投 `ANDROID_WORKER_QUEUE` | 按 `device_id` 查 `Device` 校验 `worker_id` 非空且在线，透传 `device_id`, `worker_id`, `expected_generation`, `serial` | 投递 `mobile_special.<worker_id>`；`/devices/{id}/screen`（MJPEG）同步透传节点信息 | 未认领设备（`worker_id IS NULL`）或所属节点离线直接拒绝（409/503） |
| **Scrcpy / 交互式 Agent**<br>`device_stream/router.py`, `api/v1/android_agent.py` | Backend 内直连 `adbutils` / `uiautomator2.connect(serial)` | 检测 `ANDROID_MULTI_NODE_ENABLED=true` | **一期前后端主动阻断**，返回 `409 multi_node_feature_disabled` | 仅显式单节点/本地模式下保留直连 |
| **Android 用例（低代码 / pytest / AI 修复重跑）**<br>`api/v1/cases/runs.py`, `ai_healing_iter5.py`, `execution_routing.py` | `case.config.get("device_serial")` + 固定投 `android` | 优先读 `config.device_id`；回填并校验 `worker_id` 后写入任务上下文 | 投递至 `android.<worker_id>`；执行器优先按 `device_id` 查 `Device` 并校验租约与归属 | 历史仅有 `device_serial` 时，在可操作设备中**唯一匹配**才兼容；0 条或多条明确拒绝 |
| **Android 执行前预检**<br>`services/android_precheck.py` | `select(Device).where(Device.serial == target_serial)` | 支持 `device_id` 参数；按 `device_id` 精确查 `Device` 与租约 | 校验设备在线、归属节点在线、租约可用 | 仅有 `device_serial` 且匹配 ≥2 台设备时返回 `device_serial_ambiguous` |
| **套件 / 计划 / Webhook / 定时**<br>`suite_orchestrator.py`, `plans.py`, `webhook.py`, `tasks.py` | `resolve_suite_execution_queue` / `resolve_plan_execution_queue` 整体判 `android` | 协调任务本身不绑节点；在每个 Android 子任务入队前解析其 `device_id -> worker_id` | 按子任务目标设备的 `worker_id` 分别投递至各自 `android.<worker_id>` | 混合多节点套件在协调层拆分子任务，分别路由并汇总终态 |
| **设备矩阵**<br>`services/device_compatibility.py`, `device_leases.py` | `build_android_device_matrix` 按 `serial` 去重 | 矩阵项支持并优先携带 `device_id`；去重键升级为 `device_id`（允许跨节点同 `serial`） | 在协调层按具体 `device_id` 拆分子任务并分别路由，汇总保留部分失败与取消状态 | 仅有 `serial` 的旧矩阵项按唯一匹配解析，歧义则报错 |
| **移动端专项测试**<br>`api/v1/mobile_special.py`, `tasks_mobile_special.py` | `_enqueue_mobile_run` 固定投 `mobile_special` | 创建 `MobileSpecialRun` 时固定 `device_id`、`worker_id`、`device_serial` | 投递至 `mobile_special.<worker_id>`；执行前校验 `device_id` 归属与租约 | 无 `device_id` 且 `serial` 歧义时拒绝创建运行 |
| **Agent 草稿回放 / 发布**<br>`services/android_agent/replay.py`, `api/v1/android_agent.py` | `build_case_config(..., device_serial=...)` | 传入并固化 `device_id` 到生成用例 `config` | 随 `enqueue_case_run` 路由至 `android.<worker_id>` | 历史仅有 `serial` 的草稿回放按唯一匹配解析 |
| **设备包快照 / 掉线恢复**<br>`models/device.py`, `device_leases.py`, `execution_run_leases.py` | 部分日志/摘要按 `serial` 匹配 | 统一以 `device_id` 关联查询与恢复，不跨 `device_id` 自动收敛 | 掉线恢复、租约释放严格限定 `Device.id == device_id` | 不跨设备自动匹配 |

---

## 二、核心参数与行为契约

### 1. 节点身份与实例代次
- **`worker_id` 规范**：匹配正则 `^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$`（1~64 位，禁止空格、冒号及通配符），避免队列名歧义。
- **持久化方式**：优先读取环境变量 `ANDROID_WORKER_ID`；未显式指定时基于计算机名规范化生成默认 ID，并持久化到 `.local-run/android-worker-id`（重启复用同一 `worker_id`；克隆机器或改名需显式配置新 ID）。
- **`worker_hostname`**：仅用于界面展示，不作为路由键。
- **`instance_generation` 与 `instance_token`**：
  - Worker 每次启动生成单调递增或全局唯一代次 `instance_generation`（如时间戳毫秒 + 随机后缀 `int` 或 UUID）及随机 `instance_token`。
  - 注册表占用键：`atp:android-worker:workers:<worker_id>`，使用 Redis `SET key value NX EX <ttl>` 原子抢占；若已存在未过期且不同 `instance_token` 的在线实例，新进程拒绝启动并报错退出。
  - 续租与注销必须校验 `instance_token` 一致性（Lua 原子 compare-and-expire / compare-and-delete）；占用过期后新实例接管必须生成新的 `instance_generation`。

### 2. 模式切换配置（`backend/app/core/config.py`）
- `ADB_SCAN_MODE`: `"local"` | `"worker"`
- `ANDROID_MULTI_NODE_ENABLED`: `bool = False`（默认 `False` 兼容单节点过渡；多机在线部署设 `ADB_SCAN_MODE=worker` 且 `ANDROID_MULTI_NODE_ENABLED=true`）
- `ANDROID_LOCAL_OWNER_ID`: `str = "local"`（本地直连模式下的非空持久化归属标识，与远程 Worker 命名空间隔离）
- `ANDROID_WORKER_HEARTBEAT_SECONDS`: `int = 15`
- `ANDROID_WORKER_TTL_SECONDS`: `int = 45`
- `ANDROID_WORKER_OFFLINE_GRACE_SECONDS`: `int = 15`（TTL 过期后经过宽限期并二次确认仍失联，才收敛该节点设备为 `offline`）

### 3. 独立心跳与任务有效期
- **独立心跳**：Worker 进程内通过独立后台守护线程执行周期心跳（同步 Redis 客户端），**不经过 Celery `solo` 执行槽**，确保长任务（>45s）期间心跳不断，且在心跳载荷中上报 `busy`（执行槽占用状态）、`adb_ok`（本机 ADB 可用性）、`instance_generation` 与 `queues`。
- **任务有效期与重连保护**：
  - 实时控制操作（`tap`/`swipe`/`keyevent`/`text`/`screenshot`/`ui_target`/`ui_anchors`/`packages`/`connect`/`disconnect`）：`expires=15s`，超时返回 `operation_outcome_unknown`（明确提示结果未知，**严禁自动重试**）。
  - 扫描任务 `scan_adb_devices`：`expires=max(15, ADB_SCAN_INTERVAL)`。
  - 执行校验：Worker 执行设备任务前校验 `target_worker_id == 当前 worker_id`、`expected_generation == 当前 instance_generation` 及有效设备租约；不匹配则拒绝执行并写入原因。

### 4. 全节点扫描聚合响应契约
- `POST /api/v1/devices/scan`（不传 `worker_id` 且处于多节点模式）：
  - 若在线 Worker 数为 `0`：直接返回 `status="failed"`（或 `409 no_online_android_worker`），不静默成功。
  - 若在线 Worker 数 `>= 1`：固定当前在线快照，生成 `parent_scan_id`（UUID），向每个在线节点投递子任务并存入 Redis（TTL=300s），返回：
    ```json
    {
      "status": "queued",
      "scan_id": "<parent_scan_id>",
      "total_workers": 2,
      "completed_workers": 0,
      "failed_workers": 0,
      "items": [
        {"worker_id": "android-win-A", "scan_id": "<sub_id_a>", "status": "queued", "count": 0, "error": null}
      ],
      "devices": [...]
    }
    ```
- `GET /api/v1/devices/scan/{scan_id}`：汇总各子任务状态（`queued` / `running` / `completed` / `failed` / `timed_out`），父状态为 `queued` / `running` / `completed` / `partial_failed` / `failed`。

### 5. 统一错误码
- `worker_offline`：目标设备所属节点当前离线
- `worker_registry_unavailable`：Redis 注册中心不可用（禁止新接管与新派发，不误判全部节点离线）
- `device_unclaimed`：历史未认领设备（`worker_id IS NULL`）禁止参与操作与自动派发
- `device_serial_ambiguous`：仅传 `serial` 时匹配到多台设备
- `worker_generation_mismatch`：节点已重启或代次变更，拒绝旧代次任务
- `operation_outcome_unknown`：控制指令超时，结果未知且不重试
- `multi_node_feature_disabled`：多节点模式下禁止无节点身份的 Scrcpy / 交互式 Agent 入口
