# ATP 后续开发计划（2026-09-08）

> 状态：执行中。本文承接 `development-plan-2026-08-25.md` 的既有交付记录，作为 2026-09-08 起新增开发、真实环境验收和发布收口的当前执行入口。

## 1. 当前基线

- 基线提交：`a7df8e11`。
- 产品主线已经覆盖工作台、接口测试、APP 自动化、UI 自动化、性能测试、AI 智能测试、测试资产、智能中枢和系统治理。
- 当前问题已经从“缺少主线模块”转为“大型模块耦合、执行状态分散、真实场景证据和发布口径未完全收口”。
- Windows 保留前端源码和 Vite 开发服务，Linux 承载 Backend、Worker、PostgreSQL、Redis、MinIO 和单节点 K3s 运行环境。
- 当前正式部署目标为单节点 K3s；多节点高可用、跨节点调度和跨主机 MinIO 灾备调整为后续增强，不阻塞当前版本。

## 2. 状态口径

| 状态 | 含义 |
| --- | --- |
| `[x]` | 实现、测试、审查修复、文档同步和当前范围验收全部完成 |
| `[E]` | 实现与自动化回归完成，仍需真实账号、设备、协议目标或部署环境验收 |
| `[~]` | 正在实施，存在未完成代码或验证项 |
| `[ ]` | 尚未开始 |
| `[-]` | 外部条件缺失且无法继续 |
| `[OUT]` | 不纳入当前正式支持范围，保留代码或技术预览 |

页面可打开、原型数据、mock、一次健康检查或单个 Worker 心跳都不能代替业务闭环。

## 3. 架构收口阶段

### A1：前端 API 领域拆分 `[x]`

目标：降低 `frontend/src/api/index.ts` 的单文件规模，让测试能力、Hermes、系统治理等领域可以独立演进。

首批范围：

1. 把 Hermes 请求类型、响应类型和 API 方法迁移到 `frontend/src/api/hermes.ts`。
2. `frontend/src/api/index.ts` 保留兼容导出，现有页面不需要修改导入路径。
3. 增加 API 契约测试，覆盖查询、编排、会话、草稿确认、反馈和治理端点。

验收出口：TypeScript、定向 Vitest、前端全量测试和生产构建通过；现有 Hermes 页面导入保持兼容。

### A2：大型前端页面组件化 `[x]`

按风险从低到高拆分：

1. `HermesAssistantView.vue`：会话、消息、工具证据、草稿确认、治理指标和组合式状态。
2. `PerformanceCenterView.vue`：测试配置、节点、调度、运行监控、指标、基线和报告。
3. `DeviceList.vue`：设备筛选、设备卡片、详情抽屉、租约和运行操作。

当前拆分游标：

- [x] `A2.1` 抽离 Hermes 治理指标和会话上下文筛选组件，迁移对应 scoped 样式并增加独立组件测试。
- [x] `A2.2` 抽离消息/快捷提示、质量/失败证据和诊断结果组件，保留父页面请求序列和业务编排所有权。
- [x] `A2.3` 抽离计划草稿组件及草稿差异、交接载荷组合式逻辑，保存与确认写操作继续由父页面控制。
- [x] `A2.4` 拆分性能中心和设备管理页面，并执行对应页面回归。
  - [x] `A2.4.1` 抽离性能节点状态面板；节点加载、注册、编辑、删除及运行节点选择仍由父页面编排。
  - [x] `A2.4.2` 抽离设备卡片矩阵；筛选、设备加载、镜像租约和写操作继续由父页面控制。

验收出口：页面公开行为不变；每个子组件单一职责；迟到请求、项目切换和权限状态有回归测试。

### A3：统一执行状态机 `[~]`

目标：让 Case、Suite、Plan、Android 和 Performance 使用一致的状态转换、幂等和审计约束。

建议状态：

```text
pending -> queued -> running -> passed | failed | error
                         |-> cancelling -> cancelled
                         |-> recovering -> running | error
```

实施内容：

- 把重试、停止、取消、超时和 Worker 丢失规则从 API/Celery 大函数提取到执行领域服务。
- 定义允许的状态转换及拒绝原因，统一工作台操作响应。
- 所有命令带幂等键或等价去重约束；状态变化写审计和时间线事件。
- 新增并发停止、重复重试、过期确认和 Worker 中断恢复测试。

验收出口：五类任务的状态转换契约一致，非法转换不会产生新任务或污染最终结果。

当前实施游标：

- [x] `A3.1` 建立现状兼容的共享状态/动作策略，工作台可操作性与重试守卫统一消费策略，并增加五类模型枚举同步测试。
- [x] `A3.2` 提取领域状态转换决策，统一 Android/Performance 终止守卫和稳定拒绝响应；Android 停止读取增加行锁并拒绝重复取消。
- [x] `A3.3` 为工作台五类重试和已支持的终止命令增加持久化命令账本、成功响应重放、失败记录及统一审计时间线。
- [x] `A3.4.1` 增加跨用户/跨命令并发去重、重放前权限校验、未知异常与过期命令保守恢复，并复核终止行锁和终态保护。
- [x] `A3.4.2` 建立五类运行的统一 Worker 心跳/租约与失联恢复，以不可复用的 fencing token 拒绝重复消息，并取消五类长任务的固定 Celery 时限。

详细契约见 [`docs/execution-state-contract.md`](execution-state-contract.md)。

## 4. 真实能力闭环阶段

### B1：工作台与角色矩阵 `[x]`

- [x] `B1.1` 工作台任务能力声明叠加全局角色、项目角色和项目归档状态；Viewer 不再收到无效的重试/停止标记，Android/Performance 操作继续要求全局管理员或工程师。
- [x] `B1.2` 提供三角色真实环境探针，验证项目成员关系、概览、五域筛选和相邻页、失败诊断、跨项目 403，以及可选 Viewer 写拒绝；凭据仅从环境变量读取，报告脱敏。
- [x] `B1.3` 使用受控管理员、工程师、Viewer 账号和五域真实任务执行 Linux Backend 验收，并在 Windows 本地前端验证项目切换、刷新、深链、侧栏折叠和窄屏。
- [x] `B1.4` 验证五类任务轮询、重试、停止、批量操作、过期确认和执行后状态收敛，绑定同一提交 SHA 保存证据。

执行说明见 [`docs/b1-workbench-role-matrix.md`](b1-workbench-role-matrix.md)。B1.3 的三角色、五域数据、跨项目拒绝与浏览器矩阵，以及 B1.4 的动作、幂等、过期确认与状态收敛均已通过；B1 已关闭。

B1.3/B1.4 自动化与实测已覆盖任务中心从 URL 恢复项目、状态、任务类型与有界页码，Viewer 操作标记不渲染重试/停止，以及只执行服务端明确授权的操作。受控账号与数据暂时保留给后续复核，清理不属于本次步骤。

### B2：UI 自动化失败链路 `[E]`

- [x] `B2.1` 在当前单节点 K3s 发布上启用隔离的 Web Recorder，完成 Chromium、Firefox、WebKit 录制、截图、停止、Trace/HAR/报告和目标不可达后的资源恢复验证。
- [x] `B2.2` 在当前发布版本完成三浏览器 Web 用例回放，并串联元素库、页面对象和视觉基线。
- [x] `B2.3` 验证浏览器进程崩溃、登录失效、执行取消后的临时资源与会话路由清理。
- 串联元素库、页面对象、视觉基线、Trace、HAR、Console、截图和录像。

### B3：接口与对象生命周期 `[E]`

- [x] `B3.1` 为 API、GraphQL、WebSocket、gRPC 增加部署级协议队列隔离，并在当前 K3s 发布上复核 HTTP、GraphQL、WebSocket 及 gRPC Unary/Server/Client/Bidi Streaming；覆盖变量提取、跨步骤依赖和 TLS。
- [x] `B3.2` 在当前 K3s 发布复核认证/会话复用、OpenAPI/Postman 导入预览、落库、回读、执行与清理；运行时凭据不落用例配置，执行证据脱敏，项目删除同步清理加密 Redis 会话。
- [x] `B3.3` 串联运行详情及 HTML/JUnit/PDF 导出，验证 HTML 缓存命中、MinIO 运行证据引用保护，以及报告、录像和 Trace 随运行记录清理。

B3.1～B3.3 证据见 [`docs/evidence/b3-protocol-isolation-2026-09-09.json`](evidence/b3-protocol-isolation-2026-09-09.json)、[`docs/evidence/b3-api-lifecycle-2026-09-09.json`](evidence/b3-api-lifecycle-2026-09-09.json) 和 [`docs/evidence/b3-report-storage-lifecycle-2026-09-09.json`](evidence/b3-report-storage-lifecycle-2026-09-09.json)。受控真实网络目标不替代生产 Provider 兼容性或跨主机 MinIO 灾备验收。

### B4：Android 单机与可选多设备 `[x]`

- [x] `B4.1` 完成 K3s Backend 与 Windows Android Worker 配对、双真机发现、控制队列隔离和 Worker 离线不积压验证；清理共享 Redis 中遗留 q19 Beat 造成的历史队列，并停止冲突的旧 Beat/Worker 计算容器，基础设施容器继续复用。
- [x] `B4.2` 选择一台在线设备完成 Android 低代码用例持续运行，验证截图、录像、logcat、步骤轨迹和报告闭环。
- [x] `B4.3` 在活动运行中验证设备离线、Worker 重启后的状态收敛和恢复边界，并完成有界稳定性观察。
- 多设备租约冲突和兼容性矩阵在设备资源可用时执行，不阻塞单节点版本发布。
- iOS/Appium 继续保持 `[OUT]` 技术预览。

## 5. Hermes H9 智能化阶段 `[ ]`

H9 在 H1～H8 的只读安全边界上增加模型辅助规划，不开放未经确认的业务写操作。

实施内容：

1. 模型生成候选工具计划，服务端继续执行固定工具白名单、参数 Schema、项目权限和最多两步限制。
2. 返回工具选择理由、证据来源和规则校验结果，允许回退确定性编排。
3. 记录 token usage、模型调用次数、延迟、成本估算和回退原因。
4. 扩展评测集，统计工具选择准确率、引用相关性、答案完整度和拒答正确率。
5. 从失败任务生成回归范围和套件映射建议，经人工确认后只创建禁用草稿。
6. 验证多副本下会话、挂起意图、取消和治理统计的一致性。

验收出口：模型不可用时原有 H6～H8 仍正常；错误工具或越权参数在执行前被拒绝；成本和引用质量可观察。

## 6. 单节点部署与发布收口

### C1：单节点性能与可观测性 `[x]`

- [x] `C1.1` 单节点 K3s 上稳定运行 Backend、Worker、Beat、Flower、Web Recorder 和 Performance Worker；提供可重复运行的有界采样器，覆盖节点/Pod 资源、Ready/重启/Pressure 与 Backend、普通 Worker、Performance Worker Prometheus 指标，并对缺失样本或端点失败收口。
- [x] `C1.2` 完成短压、取消、Threshold、基线比较、告警、报告和对象清理；修复上传 k6 脚本未应用平台 options 的执行缺口，并完成真实单节点复验与现场恢复。
- [x] `C1.3` 验证 PostgreSQL、Redis 和 MinIO 的连接、权限、备份与恢复边界，并将最小权限、独立对象备份和 Redis 恢复点缺口整理为 C3 发布收口输入。
- 发布级 Prometheus/Operator 与长期 SLO 历史仍是 P4/C3 独立门禁；C1.1 的单节点有界采样不能替代该结论。

### C2：当前范围外能力 `[OUT]`

- Kubernetes 多节点高可用与跨节点调度。
- 跨主机 MinIO source/target 灾备演练。
- iOS/Appium、SMTP、企业微信、钉钉、Jira、禅道、GitHub Issues 和 GitLab Issues 的正式供应商验收。

### C3：发布关闭 `[~]`

- [x] `C3.1` 建立最小权限凭据通道：分离 PostgreSQL 运行/迁移连接，支持 Redis ACL 用户名和 MinIO bucket 级应用凭据；Helm 使用独立迁移 Secret，仅向 Alembic hook Job 注入 DDL 凭据，启动配置页和示例配置同步支持且不持久化新增密码。
- [x] `C3.2` 在目标 Linux 创建受限 PostgreSQL、Redis、MinIO 身份，切换 K3s Secret 并完成迁移、业务读写、任务队列、对象读写和备份回归；保留可验证回退路径。
- 执行数据库空库迁移、升级、备份恢复和回滚演练。
- 收集 SLO、告警、服务重启和持续稳定性证据。
- 绑定同一最终提交 SHA，更新能力矩阵、运行手册、证据索引和发布结论。

## 7. 推荐执行顺序

1. `A1` Hermes API 领域拆分。
2. `A2` Hermes 页面组件化。
3. `A3` 统一执行状态机。
4. `B1` 工作台和角色矩阵真实 E2E。
5. `B2/B3/B4` 按浏览器、协议目标和 Android 设备资源并行。
6. `H9` Hermes 模型辅助规划与成本治理。
7. `C1` 单节点性能与可观测性。
8. `C3` 发布关闭。

## 8. 每个模块的完成流程

每个模块按以下顺序完成：

1. 明确范围、风险和最小验收出口。
2. 实现代码并补充回归测试。
3. 运行定向测试和受影响的全量质量门禁。
4. 审查未提交差异，修复问题后重新验证。
5. 更新本计划、`Task.md` 和相关设计/运行文档。
6. 经用户要求后使用 Conventional Commit 提交并推送。

## 9. 执行记录

- 2026-09-12：完成 C3.2 目标单节点最小权限切换。PostgreSQL 保留不挂载到工作负载的 bootstrap operator，业务库及 65 张 public 表、63 个序列由非 superuser 的 `atp_migrator` 持有，`atp_runtime` 仅获业务 DML/序列权限且 DDL 探针按预期拒绝；Redis `atp-runtime` 移除 admin/dangerous 命令并仅开放 ATP 与实测 Celery queue/reply/pidbox/event key/channel 模式，真实 Redis 重启后双 Worker ping、维护队列备份和 ACL 日志复核通过；MinIO bucket 级身份完成对象读写删除，建 bucket 被拒绝。运行、迁移和 operator Secret 分离，迁移与 operator Secret 均未挂载到长期 Deployment。升级前发现旧 release 使用 `--reuse-values` 缺少 `migrationSecret` map 会导致 Hook 模板空指针，已改为 nil-safe 嵌套判断并补回归；revision 43 最终为 6/6 Pod Ready、零重启、Backend 健康、迁移头 `20260909_0072`，真实 daily 备份 `pg-backups/daily/atp-20260911-181920.sql.gz`（65,259 字节）上传成功，40 秒 5 次采样 0 告警。定向回归 `8 passed`，完整非集成后端 `2573 passed / 1 skipped`，Helm lint、旧 values 的 null render、Ruff、格式、mypy、前端 Vitest、敏感信息和差异检查均通过；独立差异审查修正了证据版本字段歧义后无剩余可操作问题。脱敏证据见 [`evidence/c3-least-privilege-2026-09-12.json`](evidence/c3-least-privilege-2026-09-12.json) 与 [`evidence/c3-least-privilege-stability-2026-09-12.json`](evidence/c3-least-privilege-stability-2026-09-12.json)。C3 仍未关闭：下一步执行空库迁移/升级/回滚演练，随后补发布级 Prometheus/SLO、独立 MinIO 与最终 SHA/证据索引。

- 2026-09-10：完成 C3.1 最小权限凭据代码通道。后端运行连接继续使用 `POSTGRES_USER/PASSWORD`，Alembic 可单独使用成对的 `POSTGRES_MIGRATION_USER/PASSWORD`；Redis URL 统一支持 ACL 用户名并对凭据编码，MinIO 客户端优先使用成对的 `MINIO_ACCESS_KEY/SECRET_KEY`，留空则兼容旧字段。Helm 将迁移身份放入独立 `migrationSecret.existingName`，只挂载到 pre-install/pre-upgrade Job，长期运行 Deployment 不接收 DDL 凭据。启动配置页同步新增 5 项字段、成对校验与敏感草稿清理。定向后端契约 `12 passed`，完整非集成后端在工作区独立临时目录下 `2573 passed / 1 skipped`，前端全量 `76 files / 363 tests passed`；Ruff、mypy、TypeScript、生产构建、Helm lint、提交钩子和差异检查通过，审查无剩余可操作问题。该切片只完成安全切换能力，不声称目标环境已收紧；下一步 C3.2 在 Linux 创建受限身份、更新 Secret、滚动部署并验证回退。

- 2026-09-10：完成 C1.3 单节点数据服务边界验收。Helm revision 41 持久启用 `DB_BACKUP_ENABLED=true`，真实 `maintenance` 队列任务通过 Worker 内 `pg_dump` 和 MinIO SDK 生成 `pg-backups/daily/` 备份；65,254 字节对象经 SHA-256 校验并恢复到隔离临时数据库，源/恢复库均为 65 张 public 表、4 个项目、4 个用户和迁移头 `20260909_0072`，临时数据库为 0。Redis 使用 BGSAVE 生成 RDB，在隔离 Redis 容器中恢复探针成功；随后源 key 删除并重做干净快照，临时容器和 34,165,810 字节快照均删除。MinIO 同端点 source/restore 对象哈希一致且临时前缀归零。权限审计未粉饰为通过：PostgreSQL 运行角色当前为 superuser 且有 CREATEDB/CREATEROLE，Redis `default` 用户拥有 `+@all`、`~*`、`&*`，MinIO 使用 root 命名凭据且 bucket 无 policy、versioning 或独立备份端点；Redis 仅有 RDB、AOF 关闭。这些项连同发布级 Prometheus/长期 SLO 一并进入 C3 阻断清单。收尾 release 为 revision 41 deployed，6/6 Pod Ready、零重启，Backend 健康，四队列为 0；30 秒 4 次采样保持三指标端点覆盖且 0 告警。脱敏证据见 [`evidence/c1-data-services-recovery-2026-09-10.json`](evidence/c1-data-services-recovery-2026-09-10.json)。C1 单节点范围关闭，开发游标进入 C3 发布关闭。

- 2026-09-10：完成 C1.2。真实短压预检先验证节点出口 allowlist 会在发流量前拒绝未授权目标；随后 run 37 复现普通上传 k6 脚本只收到 `ATP_K6_OPTIONS`、未实际启用 Threshold 的缺陷。初版 CLI 参数映射在 run 38 被目标 k6 以不支持 `--threshold` 明确拒绝，审查后改为生成临时原生 options JSON 并通过 `k6 run --config` 加载，同时保留环境变量兼容生成脚本。提交 `76115f34` 部署至 Helm revision 40 后，run 39 完成 974 次迭代、错误率 0、P95 2.637 ms，2/2 Threshold 和门禁通过，与基线比较 4 项指标、0 回归；JSON/CSV/raw summary、17 项 k6 指标和 Performance Worker 资源样本均已核对。run 40 在 2 秒后取消并收敛为 `cancelled`，无 k6 进程、临时目录、对象或队列残留。5 条验收运行及 3 个对象已精确删除，原测试 options、baseline 和节点 allowlist 已恢复。完整非集成后端回归 `2565 passed / 1 skipped`，相关回归 `22 passed`，Ruff、格式、mypy、提交钩子通过；收尾 30 秒 4 次采样均为 1 节点 Ready、6/6 Pod Ready、零重启、三指标端点持续覆盖且 0 告警。脱敏证据见 [`evidence/c1-performance-lifecycle-2026-09-10.json`](evidence/c1-performance-lifecycle-2026-09-10.json)。开发游标进入 C1.3；单节点、无 Prometheus Operator/长期 SLO 和非独立 MinIO 使 P4 继续阻塞。

- 2026-09-10：完成 C1.1。新增 `scripts/k3s-observability-sampler.py`，仅通过 `kubectl` 和 Kubernetes API proxy 采集节点及 Pod 资源、Ready/重启/Pressure、Backend `:8000`、普通 Worker `:9091` 和 Performance Worker `:9092` 的 Prometheus 指标摘要；指标原文不落盘，报告不接受凭据参数，任一必需组件、Metrics API 条目或指标端点缺失都会记录告警并返回非零。自审修复 CPU `m` 单位被取整为 0、`kubectl` 超时未收口和资源样本不完整未报警的问题。相关脚本回归 `46 passed`，完整后端非集成回归 `2564 passed / 1 skipped`，Ruff、格式、mypy、提交钩子和差异检查通过。以精确提交 `67ef34f4` 在 `atp-single-node` 运行 40 秒、间隔 10 秒，共 5 个采样点；每次均为 1 节点 Ready、6/6 Pod Ready、零重启/Pressure，三个指标组件持续覆盖且 0 告警。该结果关闭 C1.1 单节点有界观测入口，不关闭发布级 Prometheus/P4；开发游标进入 C1.2 短压与生命周期闭环。

- 2026-09-10：完成 B4.3 并收口 B4 单设备范围。run 107 在首步通过后将 `172.16.102.15:5555` 断开 22.4 秒，后续设备读取明确失败，重连和 Worker 扫描恢复；首次 Worker 中断 run 108 在执行租约过期后正确收敛为 `error`，但发现设备租约 `case-run:108` 仍使设备保持 `busy` 约 15 分钟。提交 `ff14383c` 在失联恢复时按运行 owner label 精确查找并释放 Android 设备租约，保持 Device → DeviceLease 锁顺序，并在 `result_summary.execution_recovery` 记录恢复结果。修复部署到 Helm revision 35 后，run 109 在首步完成时强制停止 Worker，新 Worker 9.6 秒恢复，运行在最后心跳后 142 秒由 Maintenance 收敛为 `error`，设备同步恢复 `online` 且租约数为 0；run 110 随即复用同一设备并完成 4/4 步骤、4 张截图、device-info、logcat 和录像。受影响回归 `82 passed`，完整后端在隔离 TEMP 下 `2560 passed / 1 skipped`，Ruff、格式、mypy、提交钩子和差异检查通过；默认 TEMP 首次完整回归的 54 个 setup error 均为既有 Windows `WinError 5`，隔离目录复跑无测试失败。50 秒六次采样均为 Worker 存活、6/6 Pod Ready、零重启，`android`、`mobile_special`、`maintenance` 队列均为 0。开发游标进入 C1 单节点性能与可观测性；H9 可按产品优先级并行启动。

- 2026-09-10：完成 B4.2。通过当前 K3s Backend `http://192.168.3.196:8000` 触发保留用例 `76`，在 `172.16.102.15:5555` 连续完成 run 103～105；三轮均为 `passed`，每轮 8/8 步骤、8 张截图，截图、device-info、logcat 和 MP4 录像的受保护 URL 均返回 200 且媒体类型正确。run 105 的 HTML 报告返回 200、包含视频播放器，PDF 报告返回 200；收尾时 6/6 K3s Pod Ready、零重启、Android Worker 注册数为 1，`android`、`mobile_special`、`maintenance` 队列均为 0。审查发现最初验收状态文件仍指向遗留 q19 Docker Backend `:29080`，已改用 K3s `:8000` 完整重跑，旧入口结果未计入 B4.2 关闭证据。未修改生产代码，因此本切片不重复执行与源码无关的全量回归；证据 JSON 结构、Markdown 差异和无敏感值检查通过。开发游标进入 B4.3 活动运行故障恢复与有界稳定性观察。

- 2026-09-08：完成现状分析，建立本执行计划；开发游标进入 A1 Hermes API 领域拆分。
- 2026-09-08：完成 A1 首批交付。新增 `frontend/src/api/hermes.ts`，迁移 Hermes 类型和 API 方法；`frontend/src/api/index.ts` 保留兼容导出；新增契约测试。定向 Hermes API/页面 `22 passed`，前端全量 `71 files / 347 tests passed`，TypeScript 与生产构建通过；代码审查未发现可操作问题。开发游标进入 A2 Hermes 页面组件化。
- 2026-09-08：完成 A2.1。新增 `HermesGovernancePanel` 和 `HermesConversationContextPanel`，治理展示、会话筛选双向绑定及响应式 scoped 样式从父页面迁出，`HermesAssistantView.vue` 从 2727 行降至 2449 行（减少 278 行）；新增独立组件回归。定向 `3 files / 24 tests passed`，前端全量 `72 files / 349 tests passed`，TypeScript 与生产构建通过。浏览器确认本地 Vite 与鉴权跳转正常，但没有 ATP 应用登录态，因此未把登录页检查记为 Hermes 视觉验收。自审发现并修复两处非目标样式偏差，同时更正首次记录中的父页面行数，开发游标进入 A2.2。
- 2026-09-08：完成 A2.2。新增 `HermesConversationPanel`、`HermesEvidencePanel`、`HermesDiagnosisPanel` 和共享展示类型，抽离消息、工具链、来源、反馈、快捷提示、输入框、质量指标、失败列表和诊断建议，并把对应 scoped 样式及窄屏规则迁入组件；父页面继续负责项目状态、迟到请求丢弃、Hermes 编排和导航。`HermesAssistantView.vue` 从 A2.1 的 2449 行降至 1711 行（再减少 738 行）；新增 3 项组件交互回归，定向 `4 files / 27 tests passed`，前端全量 `72 files / 349 passed / 3 skipped`，TypeScript 与生产构建通过。自审确认事件边界和原视觉属性保持一致，未发现剩余可操作问题，开发游标进入 A2.3。
- 2026-09-08：完成 A2.3。新增 `HermesPlanDraftPanel` 和 `useHermesPlanDraft`，草稿编辑、范围选择、差异展示及对应 scoped 样式迁入组件；选中统计、差异计算、测试点增删和交接载荷裁剪迁入组合式逻辑，父页面仍独占草稿保存、人工确认和 API 写操作。`HermesAssistantView.vue` 从 1711 行降至 1100 行（再减少 611 行）；新增差异/载荷和组件事件回归，定向 `4 files / 29 tests passed`，前端无并发全量 `73 files / 354 tests passed`，TypeScript 与生产构建通过。并发验证时 `chartTheme.spec.ts` 曾出现一次 5 秒导入超时，单文件和无并发全量复跑均通过，判定为并发资源争用。代码审查未发现剩余可操作问题，开发游标进入 A2.4。
- 2026-09-08：完成 A2.4.1。新增 `PerformanceNodePanel`，把性能节点状态、执行器能力、容量、心跳、错误和操作入口及对应 scoped 样式迁出；父页面继续负责节点请求、表单、删除写操作、运行节点选择和轮询。`PerformanceCenterView.vue` 从 2635 行降至 2482 行（减少 153 行）；兼容数组、逗号字符串、旧版单执行器字段和默认 `k6` 的原有节点能力语义。定向 `2 files / 15 tests passed`，前端无并发全量 `74 files / 356 tests passed`，TypeScript 与生产构建通过。自审发现并修复子组件无法继承父级 scoped 标题/提示样式的问题，复查无剩余可操作问题；开发游标进入 A2.4.2 设备卡片矩阵拆分。
- 2026-09-08：完成 A2.4.2，并收口 A2。新增 `DeviceMatrixPanel`，设备型号、状态、拟真屏幕、规格占位和卡片操作及对应 scoped 样式从父页面迁出；父页面继续负责关键词/状态/品牌/版本筛选、设备与 Worker 请求、删除写操作以及镜像对象 URL、轮询和会话清理。`DeviceList.vue` 从 1537 行降至 1033 行（减少 504 行）；新增展示、空态和事件边界测试。定向 `2 files / 11 tests passed`，前端无并发全量 `75 files / 359 tests passed`，TypeScript 与生产构建通过。自审恢复离线设备点击处理中的显式状态防护，复查无剩余可操作问题；开发游标进入 A3 统一执行状态机。
- 2026-09-08：完成 A3.1。新增 `execution_state` 共享服务，以五类现有数据库枚举为边界集中定义活动/终态、失败筛选、重试和终止策略及 `unknown_status`、`unsupported_action`、`status_not_allowed` 三类稳定拒绝原因；工作台状态筛选白名单、活动/失败聚合、`can_retry`/`can_stop` 和重试守卫改为消费同一策略，未修改数据库枚举或执行器结果语义。新增枚举同步、状态分区和动作决策测试，服务/API 定向 `20 passed`，Ruff、格式和 mypy 通过；开发游标进入 A3.2 终止转换决策。
- 2026-09-08：完成 A3.2。Android 与 Performance 停止接口统一使用共享动作决策和 409 拒绝语义；Android 运行读取增加行锁，重复停止、终态停止和 Performance `cancelling` 再停止均在发送取消信号及提交前拒绝。四组受影响服务/API 定向 `127 passed`，Ruff、格式和 mypy 通过；后端非集成回归在独立可写临时目录下 `2481 passed / 1 skipped / 1 deselected`，排除项是现有 `.env.example` 已含 `VITE_ENABLE_PROTOTYPE_DATA`、但启动配置页未建模造成的独立契约失败，不属于 A3 改动。开发游标进入 A3.3 命令幂等与审计。
- 2026-09-08：完成 A3.3。新增 `execution_commands` 命令账本与 `20260908_0069` 迁移，以用户和命令 ID 唯一约束覆盖五类工作台重试及 Android/Performance 终止；单任务支持 `Idempotency-Key`，批量任务携带逐项稳定命令 ID，已成功命令原样重放，处理中、失败或跨目标复用命令被拒绝。账本结构化保存源状态、结果状态、成功响应和失败原因，并同步写入现有审计日志。自审补齐状态时间线字段；受影响服务/API/迁移/状态契约 `140 passed`，后端非集成 `2491 passed / 1 skipped / 1 deselected`（仅排除既有启动配置契约失败），前端全量 `75 files / 359 tests passed`，Ruff、mypy、TypeScript 与生产构建通过。开发游标进入 A3.4 并发与中断恢复测试。
- 2026-09-08：完成 A3.4.1。命令账本新增目标动作部分唯一索引，跨用户和不同命令 ID 也不能并发重复派发；明确失败释放目标并保留原命令结果，成功和不确定结果继续占用目标。工作台在全局结果重放前执行项目及专项角色预检；未知派发异常立即转为 `indeterminate`，Maintenance Worker 定时收口超时 `processing` 命令并写审计。自审将“改写失败命令记录”的初版修正为部分唯一索引，保留旧命令幂等语义。定向执行命令、工作台、迁移、清理任务及 Android/Performance 停止/Worker 回归 `181 passed`；后端非集成 `2498 passed / 1 skipped / 1 deselected`，Ruff、mypy、格式和迁移单 head 检查通过。五类运行本身的统一 Worker 心跳/租约进入 A3.4.2，避免用固定时长误判合法长任务。
- 2026-09-08：完成 A3.4.2，并收口 A3。新增 `execution_run_leases` 与 `20260908_0070` 迁移，Case、Suite、Plan、Android、Performance 五类 Celery 入口使用独立线程续期数据库租约；Maintenance Worker 按过期心跳恢复仍在活动状态的运行，旧 Worker 以 fencing token 在退出时阻止陈旧终态覆盖。同一任务域和运行 ID 的租约记录不可复用，重复/迟到消息不会重跑，显式重试必须创建新运行。五类长任务取消固定 25/30 分钟 Celery 时限，Android 旧清理任务只处理未领取的 `pending`。自审修复租约复用导致完成运行可能重跑、维护任务队列遗漏，并补齐启动配置页 4 个缺失字段；定向 `100 passed`、后端非集成 `2510 passed / 1 skipped`、前端 `75 files / 359 tests passed`，Ruff、mypy、TypeScript、生产构建、迁移单 head 和差异检查通过。开发游标进入 B1 工作台与角色矩阵真实验收准备。
- 2026-09-09：完成 B1.1/B1.2。工作台五类任务的 `can_retry`/`can_stop` 在状态策略之外叠加活动项目、项目 `owner/editor` 和 Android/Performance 全局工程师权限，Viewer 与归档项目不再收到必然失败的操作标记；新增三角色脱敏验收脚本及 Make/CI/pre-commit 质量门禁，覆盖独立身份与成员关系、项目隔离、五域筛选和相邻页、失败诊断、跨项目 403 与可选 Viewer 写拒绝。自审取消活跃环境中易抖动的三角色瞬时任务集合全等断言，补成逐响应项目隔离和真实相邻页检查，拒绝非法端口 URL，并跳过无可操作任务页面的权限查询。定向 `40 passed`，后端非集成 `2521 passed / 1 skipped`，Ruff、全量格式、mypy 与差异检查通过。本机未配置管理员、工程师和 Viewer 验收变量，未执行真实角色/任务/UI 验收；开发游标进入 B1.3。
- 2026-09-09：推进 B1.3 前置自动化。新增任务中心挂载测试，覆盖深链项目/筛选/页码恢复、Viewer 不展示操作按钮，以及客户端只调用服务端明确启用的动作；与项目上下文定向 `7 passed`，前端无并发全量 `76 files / 362 tests passed`，TypeScript 和生产构建通过。Windows Vite 在 `4173` 以进程级配置代理至 Linux `192.168.3.196:29080`，受保护接口返回预期 `401`，浏览器跳转登录页，证明传输链路但不证明角色。SSH 只读检查确认 K3s 五个核心 Pod 均 `Ready` 且零重启，但 Backend 仍为旧镜像 `1bccfef4`，本地 `HEAD` 为 `a7df8e11` 且 A1～B1 尚未提交；为避免脏工作树发布和版本证据失真，本轮未升级集群。B1.3 继续等待可追溯新镜像及三套受控账号。
- 2026-09-09：继续推进 B1.3 部署前置。A1～B1 前置代码以 `5c0f6908` 通过提交/推送钩子并推送到 `origin/main`；因目标机 Debian 软件源临时不可达，Backend/Worker 分别基于已验证的 `1bccfef4` 与 `init-reaper-0f553ae3e046` 镜像叠加该提交的完整 `/app` 源码，核对镜像 revision 标签、应用导入、Celery、Tini、k6 和 Alembic 单 head 后导入 K3s。Release revision 11 已升级到不可变标签 `5c0f6908`，迁移为 `20260908_0070`，五个核心 Pod 均 Ready、零重启，Backend `/health` 返回 200。实际升级暴露 Backend `hostNetwork` 单副本仍使用默认 surge、导致新 Pod 与旧 Pod 争用宿主机 8000 端口；现场改为 `maxSurge=0/maxUnavailable=100%` 后升级恢复，并将策略及回归测试固化到 Chart。部署健康不替代角色验收，B1.3 仍待受控管理员、工程师、Viewer 与真实项目数据。
- 2026-09-09：完成 B1.3 部署前置收口。Backend 单节点无 surge 修复及回归以 `74a15fa4` 推送，精确提交归档校验后在目标机执行服务端 dry-run，并以 `--rollback-on-failure --wait` 升级到 revision 12；集群策略确认为 `RollingUpdate(surge=0,unavailable=100%)`，五个核心 Pod 持续 30 秒 Ready、零重启，迁移保持 `20260908_0070 (head)`，健康检查正常。只读数据库盘点发现目标仅有管理员和一个无项目成员关系的历史 Viewer，没有工程师；两个现有项目也没有 Case、Suite、Plan、Android、Performance 运行记录。B1.3 因受控角色与真实数据前提未满足继续保持 `[E]`，需明确授权创建临时验收账号、成员关系和五域运行数据后再执行探针与三角色浏览器矩阵。
- 2026-09-09：完成 B1.3。经授权创建独立临时 Engineer/Viewer、目标项目 77、隔离项目 78，以及 Case、Suite、Plan、Android、Performance 各 2 条受控运行；脱敏探针直连 K3s Backend `192.168.3.196:8000/api/v1`，认证、成员关系、三角色工作台读取、五域分页、失败诊断、跨项目 403 和 Viewer 写拒绝 7 项全部通过。Windows 本地 Vite 改为代理 K3s 8000 端口，Admin/Engineer/Viewer 浏览器矩阵确认深链、刷新、项目切换、侧栏折叠、390 px 窄屏和角色操作边界正常。排查同时确认 `29080` 是共享数据库但代码较旧的 q19 Docker Backend，不再作为当前 K3s 验收入口。账号与数据保留给 B1.4；开发游标进入五类真实动作与状态收敛。
- 2026-09-09：完成 B1.4 并关闭 B1。项目 77 的五域批量重试、轮询、源运行不变性、精确重放、Android/Performance 批量停止与跨命令去重均通过；Android 重试在当前无 Android Worker 的单节点环境保持 `pending`，随后由受支持的停止路径收敛为 `stopped`，其自主执行仍归 B4。过期确认实测发现失败命令在数据库回滚后读取已过期 ORM 主键会触发 `MissingGreenlet` 并首次返回 500；提交 `86668152` 改为回滚前保存主键并补充失败/不确定两条回归，定向 `36 passed`、Ruff、格式和 mypy 通过。修复镜像以不可变标签部署到 Helm revision 13，五个核心 Pod Ready/零重启、健康检查正常；五域动作矩阵在同一版本完整重跑，新建 Performance Run 35 成功后，首次过期停止及同键重放均直接返回 409，错误详情一致，Backend 最近日志无新异常。证据见 [`docs/evidence/b1-workbench-actions-2026-09-09.json`](evidence/b1-workbench-actions-2026-09-09.json)；开发游标进入 B2 UI 自动化失败链路。
- 2026-09-09：完成 B2.1。单节点 overlay 启用独立 Web Recorder，并用专用 Redis 前缀隔离宿主机遗留 Compose Recorder；Helm revision 18 上仅注册 1 个当前 Worker。Chromium、Firefox、WebKit 均完成录制、2 步快照、PNG 截图、停止、Trace/HAR/运行报告和停止后查询；Chromium 对可解析但不可访问的 `https://example.com:1` 返回预期 `ERR_UNSAFE_PORT` 后，活动会话从基线 0 恢复到 0。部署实测发现 ConfigMap 更新不触发 Pod 重建、Web Recorder 更新时 X11 display 争用和 PID 1 无法回收子进程；Chart 已加入配置/生成 Secret 校验注解、单节点无 surge、Tini、Xvfb 存活/socket 门禁及从 `:99` 起最多 11 个 display 的有界回退。定向 `77 passed`，Helm lint 与服务端 dry-run 通过；开发游标进入 B2.2 三浏览器回放及资产串联。
- 2026-09-09：完成 B2.2。真实创建元素资产、页面对象、视觉基线及两条 Web 用例；提交 `d400d22b` 的不可变 Backend/Worker 镜像部署到 Helm revision 22 后，矩阵 Run 71 和 Chromium/Firefox/WebKit 子运行 72/73/74 全部通过，每个子运行均含 2 个步骤、2 张截图、Trace、录像和网络事件；视觉 Run 75 通过，`diff_ratio=0`。实测同时修复三项缺陷：0049/0050 迁移遗漏时间戳默认值导致资产插入失败且被误报为 409；Chromium 专用 `--no-sandbox` 参数误传给 WebKit；共享 Redis 上遗留 Compose Worker 会抢占当前 K3s 的 `default` 回放任务。新增 `WEB_EXECUTION_QUEUE` 并将本环境路由到 `web.atp-single-node`，旧 Worker 不再消费当前 Web 用例。定向 `47 passed`、Ruff、Helm 服务端 dry-run通过，6/6 Pod Ready、零重启、迁移位于 `20260909_0071 (head)`；证据见 [`docs/evidence/b2-web-playback-2026-09-09.json`](evidence/b2-web-playback-2026-09-09.json)，开发游标进入 B2.3 异常与取消清理。
- 2026-09-09：完成 B2.3。新增 Web Run 协作式停止 API、Redis 有界取消标记和 `cancelled` 终态；运行中取消 Run 76 在完成首步后收敛为 `cancelled`，Trace/录像保留，取消标记和临时目录均清除。真实杀死 Chromium 后，初次 Run 79 暴露“等待步骤不访问页面导致崩溃假通过”，修复后 Run 81 在 0.99 秒内识别断连并失败，浏览器进程和临时目录无残留、Worker 零重启。登录失效 Run 78 以预期断言失败结束并完成 Trace、录像和临时资源清理。提交 `494d43fd` 的 Backend/Worker 镜像部署到 Helm revision 26，定向 `81 passed`、Ruff 通过；证据见 [`docs/evidence/b2-web-fault-cleanup-2026-09-09.json`](evidence/b2-web-fault-cleanup-2026-09-09.json)，B2 关闭，开发游标进入 B3 API 协议链路。
- 2026-09-09：完成 B3.1。新增 `PROTOCOL_EXECUTION_QUEUE`，API、GraphQL、WebSocket、gRPC 及纯协议套件/计划可路由到部署专用队列；提交 `96a754cf` 已部署到 Helm revision 27，当前 Worker 独占 `protocol.atp-single-node`，旧 Compose Worker 不监听该队列。受控 HTTP/GraphQL/WebSocket 与 gRPC TLS Unary、Server/Client/Bidi Streaming Run 86～92 全部通过，覆盖提取、跨步骤依赖、断言和 TLS 主机名校验。首次 gRPC 预检识别旧 q19 证书已于 2026-08-31 过期，改用临时新证书完整重跑；项目、目标容器、证书和私钥均已清理。定向 `53 passed`，Ruff、格式、差异检查及代码审查通过；6/6 Pod 连续 30 秒 Ready、零重启，迁移 `20260909_0072 (head)`。证据见 [`docs/evidence/b3-protocol-isolation-2026-09-09.json`](evidence/b3-protocol-isolation-2026-09-09.json)，开发游标进入 B3.2 认证/会话与导入生命周期。
- 2026-09-09：完成 B3.2。修复 JSON/Form 请求体无法递归渲染运行时变量，以及项目删除后加密 API Cookie 会话继续驻留 Redis 的问题；提交 `7a3b2c90` 已部署到 Helm revision 28。当前 K3s 真实解析 OpenAPI/Postman 各 1 个端点，导入预览 `2/2` 有效、事务落库 2 条、回读后 Run 96/97 均通过；`session_lifecycle=reuse` 的 Run 98 使用仅随触发请求传入的凭据完成登录和 `/auth/me`，密码、access/refresh token、`Set-Cookie` 均脱敏。项目删除前 Redis 会话为 888 字节 Fernet 密文，删除后键不存在；项目 82 和临时 HTTP 目标已清理。受影响回归 `151 passed`，变更测试文件独立 `74/2/6 passed`，Ruff、格式、mypy、差异检查及代码审查通过；6/6 Pod 连续 30 秒 Ready、零重启。证据见 [`docs/evidence/b3-api-lifecycle-2026-09-09.json`](evidence/b3-api-lifecycle-2026-09-09.json)，开发游标进入 B3.3 报告导出与 MinIO 对象治理。
- 2026-09-09：完成 B3.3。修复通用存储清理未识别 `TestRun.result_summary` 录像/Trace 引用、运行记录清理遗漏 HTML 缓存及运行产物、`cancelled` 未纳入终态保留清理的问题，并补齐 Web/协议专用队列的启动配置界面；提交 `5134eda9` 已部署到 Helm revision 30。当前 K3s Run 99 通过，HTML 首次导出 `miss`、再次 `hit`，JUnit XML 可解析，PDF 为 167432 字节有效文档；清理前数据库识别录像/Trace 引用，MinIO 存在 HTML/录像/Trace 3 个对象，精确删除运行后数据库记录和对象均归零。完整非集成后端 `2557 passed, 1 skipped`，前端 `362 passed`、类型检查和生产构建、Ruff、格式、mypy、差异检查及代码审查通过；6/6 Pod 连续 30 秒 Ready、零重启。临时项目 83、用例 75、Run 99 均已清理。证据见 [`docs/evidence/b3-report-storage-lifecycle-2026-09-09.json`](evidence/b3-report-storage-lifecycle-2026-09-09.json)，B3 关闭，开发游标进入 B4 Android 单设备持续运行。
- 2026-09-10：完成 B4.1。Windows 通过持久 SSH 本地转发与 K3s Backend 复用 PostgreSQL、Redis、MinIO 和应用身份，配置配对与 Worker doctor 全部通过，两台无线设备 `172.16.102.15:5555`、`172.16.102.214:5555` 在线。实测发现无 Android Worker 时旧 Beat 在 `mobile_special` 累积 130778 条消息，并确认同机遗留 q19 Docker Beat/Worker 与 K3s 共用 Redis；提交 `432bead0` 将扫描、心跳和设备操作隔离到 `android`，将专项调度/清理/租约回收到 `maintenance`，Beat 仅在 TTL 注册中心存在在线 Worker 时投递带过期时间的扫描。停止 3 个冲突旧计算容器并精确清理历史周期消息后，离线期 `mobile_special/android` 均保持 0；恢复 Worker 后注册和 API 扫描完成，返回 2 台在线设备。提交已部署到 Helm revision 34，6/6 Pod Ready、零重启、迁移 `20260909_0072 (head)`；后端非集成 `2559 passed / 1 skipped`，受影响文件独立 `5/4/17 passed`，Ruff、格式、mypy、差异检查和代码审查通过。证据见 [`docs/evidence/b4-android-worker-control-plane-2026-09-10.json`](evidence/b4-android-worker-control-plane-2026-09-10.json)，开发游标进入 B4.2 单设备低代码持续运行和证据闭环。
