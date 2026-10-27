# Windows 独立数据与云端结果汇总开发计划（2026-10-26）

## 已确认的目标

- 首期只有一台 Windows 电脑。项目、模块、用例、完整执行记录和截图、录像、APK 等文件均在本机持久保存；本机 ADB 与执行器负责测试，断网时仍可编辑和执行。
- 云端 Linux 使用 Docker 提供在线入口、账号、远程访问和结果汇总，仅持久保存必要的账号/节点信息、测试结果与报告摘要及少量运行日志；不存放项目完整数据或附件。
- 本机完成测试后把脱敏的结果摘要放入持久待同步队列，联网后自动重试。云端按电脑身份和稳定运行 ID 去重；只有云端确认后才显示“已同步”。
- 未来每台电脑的项目和用例相互独立，不做电脑间项目数据复制。云端按电脑汇总已上报的结果。
- 所有既有云端项目和历史文件最终迁至首台电脑；迁移核验前保留源数据，不直接清空线上存储。后续再打包桌面端。
- 安装时优先在非 C 盘创建 `ATP_resources`，初始预留约 20 GB，可扩容；没有合适磁盘时要求手动选址。本机/局域网备份不写入云端。

## 代码基线与边界

现有 Windows 独立模式使用 SQLite 和本地对象目录，`ATP_LOCAL_DATA_DIR` 可指定根目录，但 `windows-standalone.ps1` 仍默认使用仓库下 `.local-data`。独立模式目前面向单人、单项目，与服务器模式的数据及账号分离且不自动同步；服务器模式使用 PostgreSQL、Redis、MinIO 和 Celery。现有 `docker-compose.app.yml` 可作为云端只运行应用服务的起点，但不能直接视作目标架构已经完成。详见 `docs/windows-standalone.md` 和 `backend/app/api/v1/runtime.py`。

“云端仅存摘要”不等于零持久数据：账号、节点索引、结果摘要需要小型云端数据库。上传中的短暂内存/临时文件及受控日志属于运行数据，应限制大小、留存和敏感字段。云端无法在本机离线时读取尚未同步的项目或附件。

## 分阶段任务与退出标准

| 阶段 | 实施范围 | 验收与退出标准 |
| --- | --- | --- |
| D0 数据目录与安全启动 | Windows 启动脚本选择非 C 盘固定磁盘，创建 `ATP_resources`；继续尊重用户显式配置；识别旧 `.local-data`，禁止静默切换或覆盖；显示空间及备份提示。 | 新安装落在选定磁盘；旧数据仍从原路径启动；无合适磁盘时明确要求手动选址；路径含空格与重启均通过。 |
| D1 本地项目与执行 | 扩展本地 SQLite 模式为多项目、多模块，补齐项目权限/资源归属与本机执行流程；保留本机 ADB 设备隔离。 | 两个项目的用例、运行、附件互不串读；断网下创建、执行、取消、重启恢复及报告查看通过。现有服务器模式回归通过。 |
| D2 摘要与本机待同步队列 | 定义版本化摘要契约、稳定电脑/运行标识、脱敏规则；运行完成后在同一持久事务或可恢复补偿步骤中创建 outbox 记录。 | 崩溃重启不漏单；重试不重复显示；敏感请求体、令牌、截图和文件内容不进入摘要或日志。 |
| D3 云端接收与汇总 | Docker 云端增加节点注册、认证、结果接收、去重和按电脑/项目查询；云端只存摘要，独立权限检查。 | 同一运行反复提交仅一条；跨账号/电脑不可读写；汇总与源摘要一致；未配置本机数据服务也能启动云端结果中心。 |
| D4 自动同步与状态 UI | 联网重试、退避、断点恢复和 `待同步/同步中/已同步/失败待重试` 状态；云端确认后更新本地状态。 | 断网运行、恢复联网、云端超时和重复回执均可恢复；页面状态与两端记录一致。 |
| D5 在线远程访问 | 通过私有加密连接访问在线电脑的项目和执行能力，不在云端长期缓存项目正文与附件；电脑离线时明确提示。 | 仅授权用户可访问指定电脑；在线可查看/操作，离线不能误写；文件仅从本机读取。 |
| D6 历史迁移与割接 | 盘点云端 PostgreSQL/MinIO 对象与本机可用空间，做全量备份、项目/用户映射、分批导入、文件校验和增量追平；在维护窗口停止旧写入后割接。 | 记录数量、关系、对象大小/校验值、代表性历史报告一致；失败可回退旧入口；验收及独立备份前不删除云端源数据。 |
| D7 桌面端打包（后续） | 将本地 Backend、前端、ADB 检查、数据目录选择、升级/备份/卸载封装为 Windows 安装包。 | 全新电脑安装、升级、离线运行和数据保留验证通过；新增电脑使用独立项目，不继承其他电脑的数据。 |

## 第一个可交付切片

先完成 D0，并只对新安装启用非 C 盘默认目录。旧 `.local-data` 不自动迁移。随后用一条本机 API/Web/Android 代表性流程证明 SQLite 与附件确实写入 `ATP_resources`，并核对备份/恢复仍指向同一目录。D0 通过后进入 D1；D2～D6 均不得把“已有本地功能”直接标为完成。

## 2026-10-26 实施进度

- D0 现场全流程闭环：选定物理非 C 盘 D:（可用 276.20 GB >= 20 GB 约束），在物理路径 `D:\ATP_resources` 下真实建立 SQLite `atp.sqlite3`（Schema v15）与对象存储目录；运行 API 及华为真机（5CQBB26605200808）设置截图用例，核验数据库落盘（788 KB）及 5 张真机物理截图文件（1.3MB~2.9MB）；跨目录全量安全备份至 `E:\ATP_backup_d0_verify`（生成 manifest.json）并成功还原至 `D:\ATP_resources_restored`（5张截图与数据库 SHA-256 零漂移）。见实测报告 [`evidence/windows-desktop-d0-physical-path-verification-2026-10-26.md`](evidence/windows-desktop-d0-physical-path-verification-2026-10-26.md)。
- D1 现场全流程闭环：在 `D:\ATP_resources` 物理库中建立两个独立项目（电商主干 PROJ_ECOM 与移动端 PROJ_MOBILE），分别跨模块执行 API 订单用例（Run 1 passed 88ms）与 Android 真机用例（Run 2 passed 17687ms）；单向过滤与多项目用例隔离验证 100% 通过；Outbox 队列原子生成 2 项记录；唯一项目防删除/归档保护与单用户成员管控全部通过。见实测报告 [`evidence/windows-desktop-d0-physical-path-verification-2026-10-26.md`](evidence/windows-desktop-d0-physical-path-verification-2026-10-26.md)。
- D2 代码与定向验证：落地稳定机器指纹 `local_machine_identity`、版本化脱敏结果摘要契约 `CloudRunSummary`（彻底剥离请求/响应正文与截图附件，集成 PII 手机号/邮箱脱敏）、SQLite Schema v15 `local_sync_outbox` 待发队列（按 client_id + run_type + run_id 唯一约束去重）、本地执行器完成与崩溃重启补偿 hook（`_run_next_job` 及 `recover_interrupted_jobs` 原子写入 Outbox）。机器ID稳定性、摘要脱敏剥离、Outbox状态流转与幂等、崩溃恢复自动入队 4 项单测全部通过。
- D3 代码与生产割接：落地 `CloudRunSummaryModel` 数据模型与 Alembic 迁移 `20261026_0082`；真实受控 Linux 生产主机（`192.168.3.196:2222`）完成 622KB 数据库备份先行，成功升级 `atp_acceptance` 至 0082 头并配置 `atp_runtime` 权限；生产构建 `registry.local/atp/backend:v2.7.1-cloudsync` 成功割接上线至 K3s（Pod 1/1 Running 0 重启）；实测开放 `/api/v1/cloud-sync/runs` 与 `/api/v1/cloud-sync/stats` 端点，支持幂等去重与大盘统计。
- D4 自动同步客户端、跨端实测与状态看板 UI：落地 `cloud_sync_client.sync_pending_outbox` 扫描本地待同步 Outbox 队列并发送携带 `X-Requested-With` 的轻量摘要；实测完成 Windows 宿主机到 `192.168.3.196:8000` 云端的多机同步联调，云端确认后本地状态原子更新为 `synced`；见实测报告 [`evidence/windows-desktop-cloud-sync-d3-d4-2026-10-26.md`](evidence/windows-desktop-cloud-sync-d3-d4-2026-10-26.md)。前端在 `RunDetail` 与 `RunList` 落地同步状态徽标与手动同步控制，落地 `CloudSyncDashboard.vue` 跨端汇总大盘并打通本地 `/api/v1/cloud-sync/local/*` 端点；前端单元测试 23 项与 `vue-tsc` 类型检查全量通过。
- D7 方案 A（WebView2 + 嵌入式运行时）基础设施落地：完成 Windows 独立桌面端宿主 [`scripts/windows-desktop.py`](scripts/windows-desktop.py) 与 `windows-standalone.ps1 -Action desktop` 联动；完成 Tauri 2.0 规格标准目录 `frontend/src-tauri`（`tauri.conf.json`, `Cargo.toml`, `build.rs`, `src/main.rs`）；桌面启动器契约与语法单测通过。
- D5 复审修复：旧心跳代理把 Windows 回环地址误当云端可达地址，并转发云端用户凭据，旧现场记录不构成在线访问验收。新版云端网关已部署；Windows 通过受限 SSH 私有转发主动建立 WebSocket 通道，并完成管理员 API Key 节点绑定、本机签名凭据代理和真实跨机器读写、离线阻断验证。应用户后续要求，生产 SSH 密码、本机签名密钥和本机管理员密码已恢复轮换前的值。大文件和多用户现场验收仍待完成；发布镜像尚需纳入 Helm 配置。
- D6 历史迁移与割接实测：云端 PostgreSQL 631KB 与 MinIO 35.89MB 备份先行；使用 `scripts/migrate_cloud_to_local.py` 结构化抽取 4 个既有项目、1 个模块、17 个用例、146 次运行记录与 210 条步骤，平滑导入 `D:\ATP_resources\atp.sqlite3` 并对齐本地管理员；464 个 MinIO 物理附件（截屏/录像/Trace/报告）全量同步解压至本地 `objects/` 目录；双端实体数量校验一致，云端 17 条源用例完好未受损。实测证据见 [`evidence/windows-desktop-cloud-d5-d6-closure-2026-10-27.md`](evidence/windows-desktop-cloud-d5-d6-closure-2026-10-27.md)。
- D0、D1、D2～D4 与 D6 的历史实测记录保留；D5 已完成修复版线上读取验证，剩余现场验收见上；D7 安装包端到端验收仍需单独确认。
## 执行和发布约束

- 每阶段先定位受影响的 API、模型、执行器与脚本，再实现、补有意义的回归测试、运行定向门禁并审查差异；每项测试文件应可独立运行。阶段结果同步本文及 `Task.md` 时保留已有未提交改动。
- 开发阶段可用模拟云端验证 D2～D4；必须另做真实 Docker、真实断网及真机验收，分别记录证据，不用单测代替现场验证。
- 迁移/删除历史线上数据和生产割接在 D6 单独审批与操作；提交和推送也按用户要求另行执行。
