# 多主机 Android Worker 并行在线改造计划（路径 2）

> **状态**：Phase 0 ~ Phase 4 代码实施、三批次审查修复与全量自动化门禁已闭环（2026-11-18）；双机物理实测待在两台 Windows Android Worker 主机上执行。
>
> **目标**：多台 Windows Android Worker 同时接入同一 ATP 服务端。用户选择设备所属节点后，扫描、远程连接、设备控制和用例执行均到正确主机，节点之间不会抢任务、覆盖设备状态或误操作。

## 一、范围与关键约束

| 能力 | 一期 | 二期 |
| :--- | :--- | :--- |
| 节点注册、设备扫描、状态同步、网络 ADB 连接与断开 | 按节点隔离 | — |
| 截图、点击、滑动、按键、文本、控件树和包名读取 | 经设备所属 Worker 执行；镜像使用截图轮询 | 可优化画面和交互性能 |
| Android 低代码 / pytest、移动端专项测试 | 按具体设备路由；套件、计划、矩阵按设备拆分并汇总 | — |
| Android Agent 草稿回放及发布后的用例执行 | 按具体设备路由，保留租约和现有执行校验 | — |
| Scrcpy H.264 WebSocket、交互式 Android Agent | 多节点模式下前后端主动禁用不具备节点身份的入口；提示原因 | 节点化并重新开放 |

- 一期镜像采用**截图轮询**。当前前端已有 Scrcpy 失败后的截图兜底，不能假定其已经使用 MJPEG；`/devices/{id}/screen` 是否支持节点路由需一并检查，但不是一期投屏的交付承诺。实际刷新率和延迟以双机测试记录为准。
- 一期不得只隐藏按钮：服务端也必须阻断无节点身份的 Scrcpy 控制与交互式 Agent 入口，防止相同 `serial` 在服务端 ADB 上误命中。保留的单节点本地能力须有明确模式和校验，不能绕过此约束。
- 浏览器选择节点只是使用偏好，不证明浏览器位于该主机，也不构成设备访问授权。服务端仍须校验用户权限、设备归属和租约。
- 本方案支持不同主机的不同设备使用同一 `serial`，例如两个 `emulator-5554`。同一台物理设备被多个 ADB 节点同时接入是另一类冲突：一期不自动合并或认定其身份。对可确定为同一物理设备的重复接入，应阻止启用或要求管理员解除重复接入；无法可靠识别的情况列为部署限制，不宣称已实现跨节点物理设备互斥。

## 二、核心设计

### 1. 设备与节点身份

- 平台内使用 `device_id` 标识设备记录；`serial` 仅作为所属 Worker 本机执行 ADB 的参数，不再作为跨节点全局身份。设备记录包含稳定的 `worker_id` 和用于展示的 `worker_hostname`。
- 数据库保证同一归属下 `serial` 唯一，允许不同归属的同名序列号。历史未认领记录不参与设备操作和自动派发；历史仅有 `serial` 的配置只有在可操作设备中唯一匹配时才能兼容解析，零条或多条均明确报错，不猜测。
- 新的运行记录、子任务和控制命令应保存 `device_id`、目标 `worker_id`、节点实例代次及必要的 `serial` 快照。发布前解析设备和归属；Worker 执行前重新验证当前身份、归属、实例代次、任务有效期及适用的设备租约。归属变化、代次不匹配或租约失效时拒绝执行并记录原因。
- 盘点并改造所有仅用 `serial` 查询、关联和恢复的代码，包括预检、低代码、pytest、设备矩阵、远程 Agent、录制、报告、包快照、Agent 回放和掉线恢复；运行记录优先按 `device_id` 关联。历史记录缺少身份时，只有唯一且可验证的匹配才可兼容，否则不跨设备自动收敛。
- `worker_id` 是持久化的节点身份，不随进程重启变化；`hostname` 只展示。每次启动另生成实例代次。限制 ID 长度和字符集，统一校验和队列命名，避免队列名歧义。默认名可由计算机名生成，但首次生成后须持久化；克隆或改名时提供显式配置方式。
- 用带过期时间的原子占用和实例令牌阻止同一 `worker_id` 同时被两个实例使用；续租和释放必须验证令牌。占用失效后的接管需使用新的实例代次，旧实例恢复时不得继续消费或执行旧代次的设备任务。注册表暂不可用时禁止新接管和新设备操作。

### 2. 归属迁移与本地模式

- 迁移前备份数据库并导出设备、租约、运行和配置中的设备引用。已有设备仅在来源可确认时绑定到指定 Worker，保留原 `device_id` 及关联；无法确认的标记为待认领，提供管理员查看、认领和处理方式。不得按首次扫描结果静默认领。
- 本地直连模式使用持久化且非空的本地归属标识，与远程 Worker 命名空间区分。待认领数据可暂用空归属，但 PostgreSQL 与 SQLite 的普通组合唯一约束均允许多个 `NULL`：需为待认领记录另建部分唯一索引，或采用经过测试的等价约束，明确避免重复未认领 `serial`。
- 将原 `serial` 唯一约束和 upsert 冲突目标一起迁移，分别处理 PostgreSQL 和 SQLite；不能仅增加列。SQLite 本地升级如需重建表，须保留数据、外键、索引及关联。
- 升级前检查当前 Alembic head，以实际 head 为父版本创建迁移；当前文档基于 `20261113_0091`，实施时重新确认。数据库产生跨节点同 `serial` 后无法直接恢复旧的全局唯一约束：降级前检测冲突并明确拒绝，先备份并按运行手册人工处理；不删除设备数据以强行降级。

### 3. 队列、存活与兼容

- 多节点模式下，Worker 只消费自己的设备执行队列 `android.<worker_id>`、`mobile_special.<worker_id>`；设备操作统一选定并记录所用专属队列。服务端从设备归属决定队列，客户端传入的节点不得覆盖设备归属。
- 共享 `android` / `mobile_special` 队列仅允许在显式单节点兼容模式使用。切换多节点前停止旧 Worker，核对并处理共享队列积压，禁止新旧路由混用；升级、回退及停机步骤见第六节。
- 心跳独立于执行长任务的 Celery 执行槽运行。当前 Windows Worker 为 `solo / concurrency=1`，仅把心跳任务改到专属队列仍会被长任务阻塞。注册信息区分进程在线、ADB 可用和执行槽忙闲，包含实例代次、队列能力和最近成功时间。
- 超过心跳阈值进入失联状态，经过约定宽限期并再次确认实例仍失联后，才按该节点收敛设备状态。使用实例代次或条件更新避免重连后的旧收敛覆盖新状态；注册表不可用时返回状态未知并停止新派发，不将全部节点直接判为离线。超时、宽限期及恢复策略通过配置定义并在验收前固定。
- 指定节点不在线、身份不明确或注册中心不可用时，不投递到其他节点；返回可识别的错误。对已入队任务设置有效期、取消和终态收敛；节点重启或设备换归属时旧任务不得执行。控制操作超时不能视为失败后自动重试：执行结果未知时明确返回并禁止自动重复点击、输入等动作。
- 同一设备仍使用现有租约约束控制与执行；补充入队等待、执行前校验、长任务续租、取消、失联与释放的行为。独立心跳不代表设备租约可省略。

### 4. 路由入口与扫描契约

| 入口 | 设备确定与路由要求 |
| :--- | :--- |
| 单用例、pytest、低代码、AI 修复重跑 | 入队前解析具体 `device_id`；未指定或历史 `serial` 有歧义时拒绝并提示选择 |
| Agent 草稿回放 / 发布用例 | 从会话或请求中解析并固定 `device_id`；校验设备、节点与租约，按该设备派发 |
| 套件、计划、Webhook、定时调度 | 协调任务不绑定任意设备节点；在每个设备子任务入队前解析身份并路由 |
| 设备矩阵 | 在协调层按具体设备拆分子任务，分别路由；汇总每台设备的终态，保留部分失败和取消信息 |
| 移动端专项测试及其调度 | 在创建每个运行时固定设备与节点，独立校验并派发 |
| 扫描、连接 / 断开 | 指定节点；全节点扫描由服务端向快照中的在线节点分别派发。连接前无 `device_id` 时使用明确选择的节点 |
| 截图、控制、控件树、包名读取 | 根据 `device_id` 查归属和权限，控制动作须校验租约；禁止凭 `serial` 跨节点路由 |

- `GET /devices` 可按 `worker_id` 过滤；`POST /devices/scan` 支持指定节点或全节点扫描。全节点扫描在创建时固定目标节点集合并生成父扫描 ID，每节点有独立子任务 ID、状态、时间和错误。
- 子任务状态至少包含 `queued/running/completed/failed/timed_out`；父任务区分全部成功、部分成功、全部失败和进行中，约定零在线节点为明确失败。定义超时、结果保留时间和过期查询响应；保留单节点旧调用的兼容方式并更新前端轮询。
- 扫描同步的 upsert、在线/离线、`busy` 租约协调全部限定当前节点；扫描失败不得当作空设备列表。相同节点的并发扫描需通过跨进程锁或单调代次实现有序提交，避免旧扫描晚到覆盖新结果。网络连接或断开后由目标节点扫描并同步，返回可关联的节点、设备及结果。

## 三、一期任务清单

### Phase 0：盘点与冻结契约

> 冻结契约详见 [multi-android-worker-contract.md](file:///e:/csh/MyProject/ATP/docs/multi-android-worker-contract.md)。

- [x] 按第二节路由表列出真实调用方和所需字段，覆盖 API、执行器、调度器、设备矩阵和远程 Agent；记录历史配置兼容方式。
- [x] 明确节点 ID、实例代次、离线阈值、任务有效期、扫描聚合响应、错误码及租约行为；定义本地模式与多节点模式的切换配置。
- [x] 先增加同 `serial` 和长任务期间心跳的回归场景，作为后续实施的关键验证（`backend/tests/services/test_multi_worker_regressions.py`）。

### Phase 1：设备身份、迁移与历史数据

- [x] 修改 `backend/app/models/device.py`、`backend/app/schemas/device.py`，增加归属及待认领语义；设置组合约束与待认领唯一性保护。
- [x] 基于实施时实际 Alembic head 创建迁移（`20261117_0092_add_device_worker_ownership.py`）；同步 `backend/app/core/local_schema.py`（v25）的 SQLite 升级。
- [x] 改造按 `serial` 单独定位设备或运行的路径：`device_resolution.py`、`android_lowcode_executor.py`、`android_precheck.py`、`device_compatibility.py` 与 Agent 回放（`replay.py`）。新执行链路传递 `device_id`；不确定的历史引用拒绝操作。
- [x] 用真实 PostgreSQL 和 SQLite 数据执行升级、约束、关联保留及允许 / 阻止降级验证（SQLite 已在 `test_device_worker_ownership_migration.py` 验证；真实 PostgreSQL 已于 `192.168.3.196` 升级至 `20261117_0092` 并保留历史设备 `4701`/`4702`）。

### Phase 2：节点注册、隔离与扫描

- [x] 修改 `android_worker_registry.py`：规范 ID、持久节点身份、实例代次、原子占用及令牌校验；注册专属队列、ADB 与执行槽状态。
- [x] 增加独立于长任务执行槽的心跳机制（`AndroidWorkerHeartbeatThread`）；修改 `celery_app.py`、`tasks_device.py` 及 Windows 启动流程，处理接管与安全退出。
- [x] 修改 `device_sync.py`：按节点和序列号 upsert；所有状态协调按节点隔离（`mark_worker_devices_offline_*` 已就绪）。
- [x] 修改设备扫描 API（`devices.py`），支持定向和聚合扫描状态、设备认领接口（`POST /devices/{id}/claim`）；服务端禁止未确认归属的设备参与多节点派发。

### Phase 3：设备操作、运行与编排

- [x] 修改 `device_mirror.py` 与 `run_android_device_operation`：按 `device_id` 查归属并精确路由；执行前校验节点代次与目标，定义超时未知结果（`operation_outcome_unknown`）。包名读取等后台任务已透传 `worker_id`。
- [x] 补齐 `connect/disconnect` 的节点化派发；worker 模式不在 API 主机执行 ADB，并处理连接后同步及失败信息。
- [x] 修改 `execution_routing.py`、`cases/runs.py`、`mobile_special.py`、`suite_orchestrator.py` 和 Agent 回放；按路由表固定设备身份并投递专属队列。
- [x] 服务端和前端阻断一期不支持的 Scrcpy 与交互式 Agent 路径（`device_stream/router.py`、`android_agent.py`、`DeviceMirrorModal.vue`）。

### Phase 4：前端与运维

- [x] `frontend/src/api/index.ts` 和 `DeviceList.vue` 支持归属、节点过滤、定向扫描及连接 / 断开。
- [x] 节点选择存入 `localStorage` 作为浏览器偏好；失效时提示重新选择，不静默切换。
- [x] 镜像页多节点/Worker 模式直接使用截图轮询，跳过旧 Scrcpy 通道。
- [x] 更新 `scripts/windows-android-worker.ps1`、`scripts/validate-android-worker-config.py` 支持持久化 `ANDROID_WORKER_ID` 与多节点专属队列。

## 四、二期规划

- [ ] **Scrcpy 节点化**：按 `device_id` 和归属 Worker 建立视频及控制通道，评估流代理或中继方案；设计鉴权、租约、背压、断线和资源回收。完成双机同序列号验证后重新开放。
- [ ] **交互式 Android Agent 节点化**：将交互会话、手动动作和 Loop 迁至所属 Worker 或经受控代理执行；保留租约、取消、代次和不确定结果处理。完成真实设备验证后重新开放。

## 五、测试与验收

### 自动化与集成

- [x] 同节点唯一、跨节点同 `serial` 共存、未认领唯一性；旧配置唯一匹配和歧义拒绝；预检、执行、恢复和报告均不跨设备（`test_device_worker_ownership_migration.py`、`test_multi_worker_regressions.py`、`test_multi_node_routing.py`、`test_android_precheck.py`、`test_android_lowcode_executor.py`）。
- [x] 两节点交叉扫描、空扫描、ADB 失败、并发扫描乱序、busy 租约协调、失联后重连竞态；注册中心不可用不误判全部离线（`test_multi_worker_regressions.py`、`test_tasks_device.py`）。
- [x] 专属队列路由、共享队列兼容模式隔离、重复 Worker ID、旧实例代次、节点离线 / 重启、任务过期和取消；长任务期间心跳持续（`test_multi_worker_regressions.py`、`test_multi_node_routing.py`、`test_tasks_device.py`）。
- [x] 用例、pytest、专项、回放、套件、计划、定时、Webhook、矩阵及 AI 修复重跑均覆盖正确路由、缺失或歧义设备、部分失败和结果汇总（`test_multi_node_routing.py`、`test_android_agent_draft_replay.py`、`test_android_lowcode_executor.py`）。
- [x] 连接 / 断开和全部设备操作正确路由；租约失效拒绝执行，超时未知结果不自动重复；多节点模式下旧 Scrcpy 与交互式 Agent 的前后端入口均被阻断（`test_multi_node_routing.py`、`test_device_mirror.py`、`DeviceMirrorModal.spec.ts`、`AndroidAgentPanel.spec.ts`）。
- [x] 全节点扫描父子状态、超时与部分成功；前端节点选择、失效处理、身份展示和截图轮询（`test_multi_node_routing.py`、`DeviceList.spec.ts`、`DeviceMatrixPanel.spec.ts`、`DeviceMirrorModal.spec.ts`）。
- [x] PostgreSQL 和 SQLite 使用含历史关联的数据实际迁移、约束及降级测试，包含新增重复 `serial` 后拒绝降级的场景。静态迁移测试不能替代真实数据库测试（SQLite v24→v25 外键子表保留与 Alembic `20261117_0092` 升级/重复 `serial` 拒绝降级/解除冲突后降级已在 `test_device_worker_ownership_migration.py` 实测通过；PostgreSQL 线上库已于 `192.168.3.196` 升级至 `20261117_0092` 并保留历史设备关联）。
- [x] 执行 `make test-backend`、`make test-backend-standalone`、`make lint`、`make mypy`、`make test-frontend-build`；需要真实 PostgreSQL / Redis 的场景执行相应集成测试并记录环境与结果（`make test-backend` 4476 passed、`make test-backend-standalone` 468 文件全过、`make lint`/`format-check`/`mypy` 0 错误、前端 `type-check` + Vitest 93 文件 528 passed + `vite build` 全部通过）。

### 双机实测

- [ ] A、B 同时上线，浏览器分别明确选择节点；定向与全节点扫描、状态和错误显示正确。使用两个不同设备但相同 `serial` 的模拟器，验证各自截图、操作、执行、租约和掉线恢复互不影响。
- [ ] A 执行超过心跳超时阈值的长任务期间，A 心跳持续且状态正确；B 的扫描、截图、操作和用例执行不受 A 任务抢占。
- [ ] 分别在入队前、入队后及操作执行中断开和重启 Worker，检查队列、任务终态、租约和结果未知提示；确认不自动重复操作，不向其他节点转发。
- [ ] 一节点扫描失败、另一节点成功；注册中心短暂中断；重连与旧扫描晚到，检查聚合结果和设备状态。
- [ ] 跨节点套件 / 计划、设备矩阵、专项测试与 Agent 回放分别落到正确节点；核对结果汇总。验证多节点模式下 Scrcpy 与交互式 Agent 确实不能误连。
- [ ] 记录两台主机、Worker 版本、设备、测试步骤、截图轮询实际帧率 / 延迟、日志与结果；未能验证的项目保持未完成，不以单机测试替代双机验收。

## 六、发布与回退

1. 暂停设备相关调度和新任务，备份数据库与配置，盘点旧 Worker、共享队列积压、历史设备归属和在途租约 / 运行。
2. 完成迁移与历史归属确认，先在隔离环境运行 PostgreSQL、SQLite 和双机测试；部署兼容服务端和新版 Worker，确认节点 ID 不冲突。
3. 停止所有旧版设备 Worker，按运行手册完成旧任务的执行、取消或收敛；启用多节点模式及专属队列，先单节点冒烟再接入第二节点。
4. 监测注册、ADB、队列积压、扫描、任务错误与租约；发现异常时停止新派发并保留日志，按实例和设备核实后恢复。
5. 回退前停止多节点写入、备份当前数据并检测重复 `serial` 和旧版本不兼容数据。若存在冲突，先按运行手册人工处理并确认关联，再恢复旧唯一约束及单节点模式；不得静默丢弃数据或让旧 Worker 直接消费残留任务。
