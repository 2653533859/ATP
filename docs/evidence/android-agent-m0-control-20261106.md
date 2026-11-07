# Android Agent M0：租约门禁与模型单步闭环

日期：2026-11-06。以下是工作区代码与单元测试结论；未调用真实模型，未操作设备。与之并行的 atp-71 会话负责正式执行器严格回放与 TestRun 接入，结果以其记录为准。

## 已实现

- `android_agent/control.py`：写前复核取消、控制代次和数据库租约。
- `android_agent/single_step.py`：观察 → 模型 → 上下文复核 → 单次动作 → 预期验证；预算耗尽在调用模型前停止；`finish` 只进入待审查；写入结果未知时停止，不重发。swipe 暂未支持，返回 `action_not_supported`。
- `device_adapter.py`：新增 `UiTarget`、`wait_for`、`tap`、`press_back`，精确匹配，无坐标回退。
- `device_leases.py`：修复下述两个 SQLite 问题。

## SQLite 租约实测发现的缺陷（已修复）

用真实 aiosqlite 文件库并发 8 个争抢者：

1. 已有租约时，读回的无时区时间与带时区时间比较抛 `TypeError`，不返回占用冲突。
2. 抢占过期租约时出现多个成功者。结合代码判断，原因是 SQLite 复用 id，按 id 的删除误删他人刚取得的新租约（该机制是推断，未单独隔离验证）。现改为按 id + 令牌条件删除，并把唯一约束冲突转为 `DeviceLeaseConflict`。

修复后两个并发用例连续 5 次均为 1 个成功、7 个冲突。这是单进程内并发，未覆盖多进程。

### 修复引入的提前提交（已纠正）

第一版修复用保存点包住 INSERT 与设备状态更新。本地引擎（`app/core/database.py`）只设置 WAL 和外键，沿用 pysqlite 旧式事务：只在 DML 前隐式 BEGIN。无租约路径在保存点之前只有查询，SAVEPOINT 因此成为最外层事务，RELEASE 时等同 COMMIT。

按应用同样配置的探测脚本 `.local-run/m0-patch/savepoint_probe.py`，acquire 后由调用方 rollback：

| 版本 / 路径 | 回滚后的租约 | 设备状态 |
| --- | --- | --- |
| HEAD / 无租约 | 无 | online |
| HEAD / 已有过期租约 | 抛 `TypeError` | — |
| 第一版修复 / 无租约 | 新租约仍在 | busy（已被提前提交） |
| 当前 / 无租约 | 无 | online |
| 当前 / 已有过期租约 | 恢复为原租约 | 保持原值 |

当前做法：在保存点之前先用 Core UPDATE 写设备状态，使 SAVEPOINT 嵌套在调用方事务里；唯一约束冲突仍只回滚保存点。测试辅助函数改为与应用一致的 WAL + 外键，并新增两项：acquire 后回滚不留下任何数据；另一连接在本会话写入前抢先提交租约时，返回 `DeviceLeaseConflict`，且调用方随后仍能提交。

## 独立对抗审查与后续修复

对租约改动做了三个角度的独立审查（SQLite 事务语义、PostgreSQL 与调用方、测试有效性），每个角度最多两条中高严重度发现再由独立复核者尝试推翻。低严重度发现只有审查者本人的复现，未经第二人复核。除下面标明的回归外，这些问题都是 HEAD 已有的。

审查确认了第一节修复后的主路径：SAVEPOINT 正确嵌套在调用方事务内；6 个进程同时争抢（无租约、过期租约各 3 轮）每轮恰好 1 个成功。这补上了上文“未覆盖多进程”的缺口。

| 问题 | 来源 | 修复 |
| --- | --- | --- |
| `release`/`reclaim` 先读再按 id 删除，SQLite 复用 id 时删掉接管者的新租约，设备显示空闲，第三方可立即占用 | 复核确认，高置信 | `release` 改为一条按令牌的 DELETE；`reclaim` 按 id + 令牌 + 已过期删除，未命中不改设备状态 |
| 接管时的 DELETE 不查过期条件，可能删掉持有者刚续期的租约 | 复核确认；窗口极窄，严重度低到中 | DELETE 加 `expires_at <= now` |
| `heartbeat` 按 id 更新：可能续到别人的租约，或抛 `StaleDataError` 而不是租约丢失 | 审查者复现（人为拉开窗口） | 条件 UPDATE，未命中抛 `DeviceLeaseConflict` |
| 过期租约已被回收时误报占用 | 审查者发现，第一版修复引入 | 未命中时重查，无租约就继续 |
| 所有 `IntegrityError` 都报占用（如 `owner_id` 外键错误） | 审查者发现，第一版修复引入 | 仅设备确有租约时转为冲突，否则原样抛出 |
| 获取途中设备被置为离线会被覆盖回 busy；设备被删除时报占用 | 审查者复现 | UPDATE 排除 offline，未命中时区分 `LookupError` 与冲突 |

新增的 SQLite 测试用真实文件库，并用第二个连接在指定语句之前抢先提交。无时区时间的读回、心跳和有效租约判断此前没有测试，这次一并补上。

变异验证（`.local-run/m0-patch/mutate.py`，在内存中逐条撤销修复，不改仓库文件）：13 个变异 12 个被测试抓住。未被抓住的是“接管的 DELETE 去掉令牌条件”：过期条件已排除对方的有效租约，只有对方租约也已过期时才有差别，这时删除并不破坏互斥，所以没有为它加测试。

最终回归（包含上述全部修复）：`pytest backend/tests --ignore=backend/tests/integration` 为 4259 passed、3 skipped，pytest 退出码 0；`mypy` 222 个源文件无问题；`ruff check` 通过。没有重跑前端测试，这轮未改前端文件。集成测试未运行，其中也没有设备租约用例。

## 未验证

- 真实模型的单步闭环，当前进程没有授权的模型密钥。
- 严格回放的真机 TestRun、模拟器（SDK 无 system-images）、第二个可重置 App、断线恢复、5 个 POC 任务。
- PostgreSQL：本地没有启动数据库，锁等待、DELETE 重新求值等行为都是读代码推断的，CI 的 `test-integration` 也没有针对这些竞态的用例。
- `acquire_available_device_from_pool` 在真实冲突后的行为没有测试；应用代码目前也没有调用它。
- `ios_device_leases.py` 仍是旧写法，审查者推断有同类问题，未运行验证，本轮未改。
- 本地模式下租约 API 返回的 `expires_at` 不带时区（HEAD 已有）。前端解析是否受影响未验证，本轮未改。

M0 保持进行中，未冻结 v1。
