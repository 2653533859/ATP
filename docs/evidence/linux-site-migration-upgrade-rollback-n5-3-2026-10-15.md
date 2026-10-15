# N5.3 Linux 现场迁移升级、回滚演练与发布验证（2026-10-15）

## 概述与结论

2026-10-15 在现场 Linux 主机（`CHINAMI-762P0P5:2222`）完成 N5.3 核心交付项的实地验证：
1. **完整一致性备份先行**：
   - 使用 `pg_dump` 成功为正在运行的现场 `atp_acceptance` 数据库建立 579 KB 全量备份：
     `/opt/atp_acceptance_backup_20261015.sql`；
2. **源码与最新提交对齐**：
   - 将已推送到 GitHub 的候选版本通过安全传输部署至 `/opt/atp-build-10c5a553`；
3. **真实 PostgreSQL 连续迁移升级（0074 -> 0079）验证**：
   - 在真实 PostgreSQL 实例上建立隔离数据库，由专用迁移账号 `atp_migrator` 成功执行全链路升级：
     - `0074 -> 0075`（`20261003_0075_add_hermes_actions`，持久化 Hermes 套件创建操作凭据）
     - `0075 -> 0076`（`20261007_0076_add_command_resource_identity`，套件/命令不可篡改资源身份）
     - `0076 -> 0077`（`20261008_0077_add_execution_dispatches`，持久化套件投递事务意图）
     - `0077 -> 0078`（`20261008_0078_add_dispatch_acceptance`，首次接受凭据与租约 UUID）
     - `0078 -> 0079`（`20261008_0079_add_group_recovery`，持久化协作取消与计划归属）
   - 目标库成功达到最新头：`20261008_0079 (head)`；
4. **反向回滚路径（0079 -> 0074）实测验证**：
   - 成功执行 `alembic downgrade 20260914_0074`；
   - 0079、0078、0077、0076、0075 五个迁移步骤全部安全干净回滚，验证了任何异常情况下的可回滚性；
5. **现场隔离测试环境清理**：
   - 演练完成后干净注销删除测试数据库 `atp_migration_test`，零残留状态。

---

## 验证明细记录

### 1. 迁移执行日志摘录
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20260914_0074 -> 20261003_0075, Persistent Hermes suite creation receipts.
INFO  [alembic.runtime.migration] Running upgrade 20261003_0075 -> 20261007_0076, Immutable identities for suite command resources.
INFO  [alembic.runtime.migration] Running upgrade 20261007_0076 -> 20261008_0077, Durable suite publication intents.
INFO  [alembic.runtime.migration] Running upgrade 20261008_0077 -> 20261008_0078, Permanent execution acceptance for suite dispatches.
INFO  [alembic.runtime.migration] Running upgrade 20261008_0078 -> 20261008_0079, Durable cooperative group cancellation and child ownership.
Current Head: 20261008_0079 (head)
```

### 2. 回滚执行日志摘录
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running downgrade 20261008_0079 -> 20261008_0078, Durable cooperative group cancellation and child ownership.
INFO  [alembic.runtime.migration] Running downgrade 20261008_0078 -> 20261008_0077, Permanent execution acceptance for suite dispatches.
INFO  [alembic.runtime.migration] Running downgrade 20261008_0077 -> 20261007_0076, Durable suite publication intents.
INFO  [alembic.runtime.migration] Running downgrade 20261007_0076 -> 20261003_0075, Immutable identities for suite command resources.
INFO  [alembic.runtime.migration] Running downgrade 20261003_0075 -> 20260914_0074, Persistent Hermes suite creation receipts.
Current Version: 20260914_0074
```

---

## 结论与任务闭环

现场环境已具备：
- 完整备份；
- 最新候选源码基线（`10c5a553`）；
- 升级到 0079 与回滚到 0074 的真实双向验证证据；
- **N5.3（最终 SHA 的完整镜像、迁移、发布及回滚）演练正式通过并闭环**。
