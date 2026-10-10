# 套件持久投递意图（N1.3，2026-10-08）

本文保留 N1.3 的 SQLite 9/0077 实施记录。后续已接入 N1.4 首次接受与 N1.5 状态/取消/恢复，当前本地版本为 11，详见 [执行端记录](suite-delivery-development-2026-10-08.md)、[恢复记录](group-recovery-development-2026-10-08.md)；两侧实际异常/业务验收仍开放。

## 1. 实现范围

本批接入手动套件触发 `POST /api/v1/suites/{id}/run`。每次正常创建运行时，将 SuiteRun、可选的 HermesAction 和 ExecutionDispatch 放进同一个数据库事务。省略 command_id 的既有客户端也会保存投递意图。

重复命令仍由命令服务读取原运行，不创建新意图、不再次投递。接口提交后只唤醒后台扫描器；唤醒前进程退出时，已提交的 pending 意图仍可在服务恢复后被发现。

其他用例、计划、性能及 Worker 内部子执行入口继续使用各自现有投递流程。本批没有把所有执行入口的投递窗口一并关闭，也没有自动补投旧 pending 运行。

## 2. 两种模式的流程

| 步骤 | Windows 本地 | Linux 服务器源码 |
| --- | --- | --- |
| 接口事务 | 运行、可选命令、加密投递意图一起提交 | 同一 PostgreSQL 事务提交 |
| 后台领取 | 按当前 mode 扫描 pending，条件更新领取 | 多 API 实例用条件更新裁决领取者 |
| 资源核对 | 运行 UUID、所属套件/项目、pending 状态、任务与参数 | 相同核对规则 |
| 交付 | local_jobs 插入与 intent=submitted 在同一个 SQLite 事务提交 | publishing 状态先提交，再调用 Celery 发布 |
| 正常返回 | 已入队；实际执行仍由本地单线程 runner 负责 | 发布正常返回后记 submitted，不代表运行通过 |
| 不确定结果 | 队列与状态原子提交；事务异常按数据库结果恢复扫描 | 发布异常或 publishing 超过 5 分钟记 uncertain，不自动再发 |

后台投递器随 API 生命周期启动和停止。全部 API 停止时，未领取意图保留，恢复 API 后继续扫描；本地先停止投递器再停止执行队列。服务启动会检查投递表，缺少迁移时拒绝启动，避免健康接口正常但新任务无法投递。

Celery 保留原 `run_test_suite(run_id, extra_vars, trace_id)` 参数和队列路由。消息使用意图 ID 作为 task_id，并携带运行 UUID/意图 ID 头部，供后续 N1.4 的执行端接入身份核对。稳定 task_id 本身不构成业务去重。

## 3. 状态与查询

| 状态 | 意义 | 自动行为 |
| --- | --- | --- |
| pending | 意图已提交，尚未领取 | 扫描后进行首次领取 |
| publishing | 领取已记录，服务器消息结果待确认 | 不被第二个投递器重新领取；超时转 uncertain |
| submitted | 本地队列已提交或服务器发布正常返回 | 不再发布；等待原运行结果 |
| uncertain | 发布异常/超时，不能证明消息未被接受 | 保留核对状态，不自动重投 |
| blocked | 参数、身份、项目或队列记录无法安全确认 | 保留固定错误码，不启动新的投递 |
| skipped | 原资源已删除或运行已非 pending | 不启动新的投递 |

attempt_count 记录领取次数，不能理解成实际执行次数。发布应答迟到时，仅同一领取 token 可以将其对应 uncertain 结果更新为 submitted，不允许覆盖其他领取。

- `GET /api/v1/suite-runs/{run_id}/dispatch`：校验当前项目 viewer 权限后返回投递元数据；原资源 UUID 必须一致。旧运行没有意图时返回 null。
- Hermes 处理记录增加 dispatch_status/dispatch_error_code，界面分别显示待投递、投递中、已入队、需核对、受阻或未继续投递；仍需手动刷新。
- 查询只公开状态、队列、模式、次数和时间等字段；加密参数及领取 token 不进入响应。日志使用固定摘要，不输出数据库/消息异常中的原始输入。

## 4. 数据库与文件

- 本地：SQLite 版本 9，新建 `execution_dispatches`；迁移使用冻结结构，保留版本 7/8 的既有路径。
- 服务器：Alembic `20261008_0077`，父版本 `20261007_0076`，含表、唯一约束及 mode/status/created_at 索引。
- Alembic 元数据与两套模型加载入口补齐 ExecutionDispatch/HermesAction，避免新表遗漏。
- 运行变量按现有 Fernet 配置加密；备份恢复仍须保留解密配置。

主要代码：`models/execution_dispatch.py`、`schemas/execution_dispatch.py`、`services/execution_dispatch.py`、套件 API、应用生命周期及版本迁移。执行结果与投递状态分别维护，服务不会把已入队写成运行成功。

## 5. 检查与开放项

本批代码已通过 Ruff、mypy（178 文件）和 Python 语法检查。本地及服务器前端类型检查/构建均通过。本地升级前保存 `.local-run/pre-suite-dispatch-schema9-20261008.sqlite3`；重启后确认 SQLite 9、投递表 16 列及索引存在、12 条旧队列记录仍为 finished，健康 HTTP 200。新查询路由已在运行中的 OpenAPI 出现，公开 schema 排除加密参数和领取 token。

本次本地投递表为空，没有用实际运行数据验证原子入队或应答未知流程。检查证明升级/启动和接口契约接入，不能代替 N1.6 的异常与业务验收。源码最终快照保存于 Git 忽略目录 `.local-run/development-baselines/20261008-n1-3-suite-dispatch/`，用于恢复本批工作区。

没有添加/运行自动化测试或实际套件任务。事务中断、多进程领取、Broker 应答丢失和本地队列原子提交的真实异常验收仍待 N1.6；PostgreSQL 迁移与正式 Linux 部署未执行。

下一步：N1.4 将消息身份头部与执行端领取/租约/去重衔接；N1.5 补齐未知结果核对、取消和恢复交互。此前已开始但失联的执行不能因租约过期而自动重跑。

关联：[任务计划](development-task-plan-2026-10-07.md)、[命令与投递契约](command-dispatch-contract-2026-10-07.md)。
