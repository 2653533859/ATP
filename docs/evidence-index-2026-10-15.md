# ATP 发布候选交付证据与操作索引（2026-10-15）

## 1. 概述与版本信息

本索引为 ATP 2026-10-15 发布候选（Release Candidate）的统一交付索引，对应任务计划 **N6.2（交付索引、操作手册和任务状态收口）**。

- **基线分支**：`main` / `codex/windows-local-dual-mode`
- **数据库版本**：SQLite 版本 12 / PostgreSQL Alembic `20261008_0079 (head)`
- **支持架构**：Windows 单机轻量模式（SQLite + 本地文件 + 内存任务）与 Linux 服务器模式（PostgreSQL + Redis + Celery + MinIO）

---

## 2. 核心特性与专项证据索引

| 任务模块 | 交付特性与加固内容 | 专项证据文档 | 对应自动化测试与验证 |
|---|---|---|---|
| **N1 可靠执行** | 命令生命周期服务、套件同事务投递、原子领取去重、协作取消与单机恢复 | [`docs/evidence/reliable-execution-regression-2026-10-08.md`](docs/evidence/reliable-execution-regression-2026-10-08.md) | `test_group_execution_recovery.py`, `test_suite_dispatch.py` |
| **N2.1 API/Web 闭环** | Web 录制页面/浏览器异常断开安全收敛；API 用例审核状态机；失败现场截图存证 | [`docs/evidence/windows-api-web-case-lifecycle-2026-10-12.md`](docs/evidence/windows-api-web-case-lifecycle-2026-10-12.md) | `test_n2_1_case_lifecycle.py` (4 passed), `test_web_recordings.py` (30 passed) |
| **N2.2 Android 真机与工作台** | Scrcpy 60FPS WebCodecs 硬件直解与毫秒触控；APP 工作台集成 `AndroidCaseDrawer` 用例就地创建/编辑；根模块自动回退根治 422 报错 | [`docs/evidence/windows-scrcpy-stream-scenario-orchestration-app-workbench-2026-10-15.md`](docs/evidence/windows-scrcpy-stream-scenario-orchestration-app-workbench-2026-10-15.md) | `test_scrcpy_stream.py` (4 passed), `AppWorkbenchView.spec.ts` (8 passed), `DeviceList.spec.ts` (8 passed) |
| **N2.3 混合套件与计划** | 本地模式 API/Web 混合套件强制串行执行；单线程内联调度取消防死锁；结果自动聚合 | [`docs/evidence/windows-hybrid-suite-plan-orchestration-2026-10-12.md`](docs/evidence/windows-hybrid-suite-plan-orchestration-2026-10-12.md) | `test_hybrid_suite_orchestration.py` (5 passed) |
| **N2.4 资产与缺陷清理** | 环境变量安全插值；失败执行一键转缺陷与去重；经验入知识；`delete_run_artifacts` 产物精确清理 | [`docs/evidence/windows-test-assets-defect-knowledge-cleanup-2026-10-12.md`](docs/evidence/windows-test-assets-defect-knowledge-cleanup-2026-10-12.md) | `test_n2_4_assets_defect_knowledge_cleanup.py` (5 passed) |
| **N2.5 协议与场景编排** | GraphQL / WebSocket / gRPC 执行器与派发路由闭环；空步骤防御拦截；多协议流水线；API 多步场景编排与增量合并 | [`docs/evidence/windows-protocol-subitems-acceptance-2026-10-15.md`](docs/evidence/windows-protocol-subitems-acceptance-2026-10-15.md) | `test_n2_5_protocol_subitems.py` (7 passed), `test_http_family_executors.py` (74 passed), `ApiWorkbenchView.spec.ts` (12 passed) |
| **N3.1~N3.3 升级与便携交付** | SQLite 版本 12 自动迁移；`manifest.json` SHA-256 完整性校验；Windows 独立绿色便携包打包脚本 | [`docs/evidence/windows-sqlite-upgrade-backup-restore-2026-10-12.md`](docs/evidence/windows-sqlite-upgrade-backup-restore-2026-10-12.md) | `test_sqlite_upgrade_and_backup.py` (14 passed) |
| **N3.4 模式隔离与保护** | 动态 Cookie 隔离解析（`atp_local_*` vs `atp_*`）；单侧登出无影响；WebSocket 专属令牌鉴权；`X-ATP-Client-Mode` 409 拦截 | [`docs/evidence/windows-dual-mode-switching-auth-isolation-2026-10-15.md`](docs/evidence/windows-dual-mode-switching-auth-isolation-2026-10-15.md) | `test_dual_mode_isolation.py` (5 passed), `runtimeMode.spec.ts` (5 passed) |
| **N4.1~N4.5 Hermes 智能中枢** | 8 类操作面板持久草稿与会话恢复；并发版本冲突拦截；共用命令服务接入 | [`docs/evidence/windows-hermes-recoverable-operations-2026-10-12.md`](docs/evidence/windows-hermes-recoverable-operations-2026-10-12.md) | Hermes 专项回归全量 (87 passed) |
| **N6.1 发布门禁与独立审查** | 全门禁扫描：Ruff规范/格式、Mypy、Bandit SAST、vue-tsc、生产构建与 pytest-standalone 独立单测扫描 | [`docs/evidence/windows-release-candidate-quality-n6-1-2026-10-15.md`](docs/evidence/windows-release-candidate-quality-n6-1-2026-10-15.md) | Ruff 0 错误、Mypy 188 源码 0 错误、Bandit 0 告警、Build 20.72s 通过 |

---

## 3. 标准操作手册索引（Windows 运行）

### 3.1 启停与状态查看
```powershell
# 查看本地与服务器页面就绪状态
powershell -ExecutionPolicy Bypass -File .\scripts\windows-mode.ps1 -Action status

# 启动本地模式并打开浏览器（推荐静态页面模式，无需 Node 依赖）
powershell -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action up -Frontend static

# 停止本地单机服务
powershell -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action down
```

### 3.2 模式无缝切换
```powershell
# 切换至本地单机模式（不影响服务器端进程与会话）
powershell -ExecutionPolicy Bypass -File .\scripts\windows-mode.ps1 -Action local

# 切换至服务器模式（默认打开 http://127.0.0.1:5173，不影响本地单机进程）
powershell -ExecutionPolicy Bypass -File .\scripts\windows-mode.ps1 -Action server -ServerUrl 'http://127.0.0.1:5173'
```

### 3.3 数据库升级、备份与可转移恢复
```powershell
# 1. 停机创建一致性快照与 SHA-256 清单备份
powershell -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action down
powershell -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action backup -ArchiveDir 'E:\ATP-backup\snapshot-001'

# 2. 异机/新目录一致性核对与安全恢复（拒绝覆盖已存在数据，校验哈希）
powershell -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action restore -ArchiveDir 'E:\ATP-backup\snapshot-001'
powershell -ExecutionPolicy Bypass -File .\scripts\windows-standalone.ps1 -Action up -Frontend static
```

---

## 4. 显式限制与未开放边界声明

1. **Linux 现场环境（N5.1~N5.3）**：受控 Linux 节点 `172.31.27.133` 目前由于网络断开不可达；正式线上镜像构建部署与 14 日长期 SLO 门禁保持待环境恢复后闭环；
2. **多节点分布式性能压测（P4）**：单机模式已收敛 k6 / Locust / JMeter 的能力探测与安全执行；真实的生产 Kubernetes 多节点调度与 Prometheus 采集仍需具备生产集群时验收。
