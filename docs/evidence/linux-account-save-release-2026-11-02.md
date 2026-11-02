# Linux 账号保存修复与发布（2026-11-02）

## 问题和修复

账号设置页监听 Ant Design Vue 表单的 `finish`，但没有提供 `model`。实际组件只在 `model` 存在时触发 `finish`，因此点击保存不会调用接口。修复为绑定表单模型；新增真实按钮操作的 Playwright 回归。修复前该回归未收到 PATCH 请求而失败，修复后通过。

发布前发现现场 Alembic 版本为 `20261029_0083`，仓库却只包含以 `20261026_0082` 为前序的 `20261102_0083`。恢复旧版本节点并将新版本连接到它：旧节点对已存在表进行保护，新节点降级时保留由旧节点管理的表。SQLite 行为测试覆盖单一 head、已有表、数据保留及降级。

## 代码和验证

- 发布的应用源码为 `cef6d59b35f2e833f01abcbbbc71e667cccd077e`，已推送 `origin/main`。
- 前端 Vitest 85 文件、428 项通过；模拟 API 的 Playwright E2E 13 项通过；`vue-tsc` 和生产构建通过。后端账号及迁移相关测试 19 项通过，Ruff 和差异检查通过。后端测试有 `Unknown config option: timeout` 警告，本次不是完整后端套件。
- Linux PostgreSQL 升级前创建私有备份 `/root/atp-release-backups/atp-20261102-account-fix-before-upgrade.dump`，大小 375347 字节，SHA-256 `d7642a4cf3dfcc11e56e7c0b68881a4d1d169b2eaee4a5e78e66d5a933816599`；`pg_restore --list` 可读取。将备份恢复到独立数据库后，从 `20261029_0083` 升级到 `20261102_0083` 成功，项目、用户和两张 remote-agent 表的行数与备份时现场一致；临时数据库已删除。备份清单可读不等同于完整灾备演练。
- 标准 Dockerfile 的依赖下载长时间停滞，最终取消；现场候选基于既有已运行的 backend、普通 Worker 和两个专用 Worker 镜像，离线安装 `aiosqlite==0.20.0` 后覆盖 Git 提交中的完整 backend 源码。四个镜像逐项核对 Python requirements，无缺失或版本不符，`pip check` 通过，383 个应用 Python 文件与提交快照 SHA-256 一致；性能 Worker 的 gRPC、k6、Locust、JMeter 命令可运行。这是基于既有运行时的源码更新，不是最新 Dockerfile 的完整重建或操作系统依赖升级。

## 发布过程及现场结果

- 目标为 Linux `192.168.3.196` 的 `atp-single-node`。预演显示 10 个资源无增删，6 个 Deployment 仅改变镜像字段，迁移 Hook 保留。
- 首次 Helm 升级因旧 `kubectl-set` 持有 backend 镜像字段而冲突，自动回滚也因同一冲突失败；迁移 Hook 已将数据库升级至新 head。检查字段所有权和策略一致性后，使用 `--force-conflicts` 接管字段并重新升级成功，release 为 **revision 68 / deployed**。本次期间有短暂单节点服务切换；私有目录中保存了 revision 65 的 values 和清单。不要直接使用 revision 65 的旧保存镜像值作为后续升级默认值。
- 实际 Backend 镜像为 `registry.local/atp/backend:cef6d59b-site`；普通 Worker、Beat、Flower 和 Web Recorder 使用 `registry.local/atp/worker:cef6d59b-site`，任务 Worker 和性能 Worker 分别使用 `cef6d59b-site-runmetrics`、`cef6d59b-site-heartbeat`。Helm 保存的 tag 与相应部署一致。
- 云端前端镜像为 `registry.local/atp/frontend:cef6d59b`，当前 Compose 配置位于 `/opt/atp-release-cef6d59b-20261102/cloud-web/compose.yaml`，仍引用 `/opt/atp-cloud-web-20261027/.env`；Compose 项目名保持 `atp-cloud-web-20261027`。不要仅用旧目录的 Compose 文件执行更新，否则可能回退前端镜像。
- 发布后六个核心 Pod 均 1/1 且重启 0，`/health`、云端页面与 runtime 返回 200；PostgreSQL、Redis、MinIO 依赖检查均正常，两个 Celery Worker 均响应 ping；数据库版本为 `20261102_0083`。Windows 本地前端仍可访问。
- 使用临时测试用户在 Linux 实际云端页面完成登录、输入旧密码与新密码、点击保存，PATCH 返回 200，密码输入框清空；新密码重新登录返回 200。临时账号已删除并确认不存在；保留正常审计记录，没有修改真实管理员密码。

上述现场结果只覆盖当时的单节点短时检查与该账号流程，不代表长期稳定、多节点、D5 用户授权或全部业务验收。
