# 数据库迁移运行指南

ATP 的数据库结构以 Alembic 迁移为准。应用启动时默认不会再通过
`Base.metadata.create_all` 自动补表，避免 ORM 与迁移脚本长期双轨导致 schema drift。

编写新迁移时先阅读 [Alembic Migration Guidelines](./alembic-migration-guidelines.md)，并从
[`backend/alembic/templates/migration_template.py`](../backend/alembic/templates/migration_template.py)
复制 enum、索引、约束的标准写法。

## 空库首建

本地或服务器首次准备 PostgreSQL 后，先执行：

```bash
cd backend
alembic upgrade head
```

然后再启动 backend、worker、beat、flower 等应用进程。

Docker Compose 默认包含一次性 `migrate` 服务，`backend`、`worker`、`beat`、`flower`
会等待它成功完成。直接执行即可：

```bash
docker compose up --build
```

Helm Chart 默认包含 `pre-install` / `pre-upgrade` 迁移 Job：

```bash
helm upgrade --install atp deploy/helm/atp
```

如果迁移 Job 失败，Helm 会阻止发布继续推进；查看失败 Pod 日志后再重试。

## 升级流程

1. 备份 PostgreSQL。
2. 部署前执行 `alembic upgrade head`，或让 Compose/Helm 内置迁移任务执行。
3. 确认当前 revision：

```bash
cd backend
alembic current
alembic heads
```

`alembic current` 输出应与 `alembic heads` 的 head revision 一致。

## 回滚

优先通过数据库备份回滚生产数据。若只需要回退一个迁移版本，可在确认 downgrade
逻辑安全后执行：

```bash
cd backend
alembic downgrade -1
```

涉及数据删除、字段重命名或枚举变更时，不要直接在生产执行 downgrade；先在备份库验证。

## Drift 排查

启动日志如果出现 `Alembic check` 警告，说明数据库 revision 与代码 head 不一致，或
`alembic_version` 表缺失。常用排查步骤：

```bash
cd backend
alembic current
alembic heads
alembic history --verbose
```

如果是历史环境曾经通过 `create_all` 建表但没有 `alembic_version`，不要直接 stamp。
先在临时库验证 `alembic upgrade head`，确认表、索引、枚举和约束一致后，再制定一次性
修复方案。

## 本地兜底开关

`APP_AUTO_CREATE_TABLES=true` 只保留给本地临时排障。生产、测试、CI 和共享开发环境都应
保持默认值 `false`，并显式运行 Alembic。
