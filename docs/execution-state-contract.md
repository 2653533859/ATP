# ATP 统一执行状态契约

更新时间：2026-09-09

## 1. 目标与边界

本文定义 Case、Suite、Plan、Android 和 Performance 五类执行任务的共享动作策略与统一命令路径。A3.1～A3.3 已集中现有状态与动作规则，并为工作台重试/终止增加持久化命令账本；不修改数据库枚举，不把一种领域状态静默改写成另一种状态，也不绕过各执行 API 的权限和资源校验。

工作台是读取与分发层；领域 API、Celery Worker 和执行器仍是状态变化的事实来源。

## 2. 当前持久化状态矩阵

| 领域 | 活动状态 | 成功终态 | 失败/中断终态 | 可重试 | 可终止 |
| --- | --- | --- | --- | --- | --- |
| Case | `pending`, `running` | `passed` | `failed`, `error`, `skipped` | `failed`, `error`, `skipped` | 暂不支持 |
| Suite | `pending`, `running` | `passed` | `failed`, `error` | `failed`, `error` | 暂不支持 |
| Plan | `pending`, `running` | `passed` | `failed`, `error` | `failed`, `error` | 暂不支持 |
| Android | `pending`, `running` | `completed` | `failed`, `stopped` | `failed`, `stopped` | `pending`, `running` |
| Performance | `pending`, `running`, `cancelling` | `success` | `failed`, `cancelled` | `failed`, `cancelled` | `pending`, `running` |

这些差异是现状契约，不等于最终统一命名。任何枚举扩展都必须先增加 Alembic 迁移、旧数据兼容和独立回滚方案。

## 3. 动作决策

共享服务返回布尔可用性和稳定拒绝代码：

- `unknown_status`：状态不属于该领域的持久化枚举，调用方不得继续派发命令。
- `unsupported_action`：该领域当前没有实现该动作，例如 Case 的终止。
- `status_not_allowed`：领域支持该动作，但当前状态不允许，例如已完成 Android 任务再次终止。

工作台列表的 `can_retry`、`can_stop` 与重试动作守卫必须读取同一策略，禁止再维护页面专用状态集合。领域 API 仍须在写入前重新校验状态，不能信任列表快照或前端按钮状态。

列表能力声明还必须叠加实际授权：目标项目处于活动状态，当前用户在项目内至少为 `editor`；Android/Performance 还要求全局 `admin` 或 `engineer`。无权限用户仍可在项目可见范围内读取任务和失败诊断，但 `can_retry`、`can_stop` 必须为 `false`，避免前端展示必然失败的操作。

## 4. 并发与幂等约束

- 重试只能从允许的终态创建新运行，源运行不可被改回活动状态。
- 重复重试需要幂等键或等价唯一约束；同一确认不能创建多个新运行。
- 终止必须以数据库当前状态为准；过期确认、重复终止和终态终止不得覆盖最终结果。
- Worker 完成与终止请求并发时，只允许一个合法终态胜出，并记录拒绝或竞争结果。
- 所有状态命令最终需要记录操作者、源状态、目标状态、命令标识、时间和拒绝原因。

### 4.1 统一命令账本

- 单任务接口接受 `Idempotency-Key` 请求头；未提供时使用 `workbench:{action}:{task_type}:{run_id}` 稳定键。
- 批量接口由每个任务的 `command_id` 独立去重，单项失败不会改变其他任务的命令边界。
- `execution_commands` 以 `(user_id, command_id)` 建立唯一约束，记录任务域、源运行、项目、源状态、结果状态、成功响应或失败原因。
- `processing`、`succeeded`、`indeterminate` 状态通过 `(action, task_type, run_id)` 部分唯一索引占用目标动作，阻止不同用户或不同命令 ID 并发重复派发；明确 `failed` 的尝试保留原记录但释放目标，允许新命令 ID 重试。
- 完全相同且已成功的命令返回原响应，并以 `replayed=true` 标识；处理中命令、命令 ID 被其他目标复用和已失败命令返回稳定错误，不再次派发执行。
- 成功和失败分别写入 `execution.retry|stop.succeeded|failed` 审计日志，现有系统审计日志页面可按动作和项目检索。
- 失败或不确定结果需要回滚领域事务时，必须在回滚前保存命令主键，再重新加载命令记录；禁止在回滚后访问可能已过期的 ORM 属性。
- 进程在命令已声明但尚未完成时异常退出，会留下 `processing` 记录；其恢复与人工判定属于 A3.4，恢复前保持拒绝重放，避免不确定副作用被重复派发。

### 4.2 异常与超时恢复

- 工作台在读取或重放全局命令结果前重新校验项目 `editor` 权限，Android/Performance 仍要求管理员或工程师角色。
- 可明确判断为未成功的 HTTP 业务错误记录为 `failed`；同一命令 ID 重放原错误，新命令 ID 可在状态重新校验后再次尝试。
- 派发过程抛出未知异常时记录为 `indeterminate`，因为异常前可能已经产生任务或取消信号，不得自动重放。
- Maintenance Worker 每 10 分钟检查一次超过 15 分钟仍为 `processing` 的命令，以行锁和批量上限将其转为 `indeterminate`，并写入 `execution.*.indeterminate` 审计事件。
- 目标动作的部分唯一索引继续覆盖 `indeterminate`，必须先核对源任务和审计日志，不能通过更换命令 ID 绕过不确定结果。
- `execution_run_leases` 以 `(task_type, run_id)` 唯一约束记录五类 Worker 的领取令牌、Celery 任务、Worker、心跳和失效时间；租约记录不可复用，迟到或重复消息不会重跑同一运行，人工重试必须创建新运行 ID。
- Case、Suite、Plan、Android 和 Performance 入口均在独立线程续期租约，续期不依赖异步事件循环，因此阻塞式执行器也能保持存活证据。
- Maintenance Worker 默认每 60 秒以行锁扫描过期租约，只恢复仍处于活动状态的运行：Case/Suite/Plan 写入 `error`，Android 写入 `failed`，Performance 在 `cancelling` 时写入 `cancelled`、其他活动状态写入 `failed`。
- 五类长任务不再继承全局 25/30 分钟 Celery 软/硬时限；普通维护任务仍保留全局时限。Worker 正常退出会释放租约，失去 fencing token 的旧 Worker 即使稍后返回，也会在退出围栏中被恢复为失败，不能用旧结果覆盖失联结论。

## 5. 分阶段落地

- [x] A3.1：建立现状兼容的共享状态/动作策略，工作台展示与重试守卫接入，枚举同步测试覆盖五类任务。
- [x] A3.2：提取领域状态转换决策，统一 Android/Performance 终止守卫和拒绝响应；Android 停止读取增加行锁，重复或终态停止不会再次发送取消信号或提交状态。
- [x] A3.3：为五类工作台重试和已支持的终止命令增加持久化命令 ID、数据库唯一约束、成功响应重放、失败记录及统一审计时间线。
- [x] A3.4.1：增加跨用户/跨命令并发去重、重放前权限校验、未知异常与超时命令保守恢复，并覆盖 Android/Performance 行锁停止和终态保护回归。
- [x] A3.4.2：为五类运行增加统一 Worker 心跳/租约与失联判定，完成 Worker 中断后的运行状态恢复、重复消息隔离和旧 Worker 最终状态围栏。

## 6. 验收要求

每个阶段必须通过对应服务与 API 定向测试、Ruff、格式和 mypy；涉及模型时增加迁移验证。只有五类任务均由共享转换契约保护，且非法转换不会创建任务或污染终态后，A3 才能标记完成。
