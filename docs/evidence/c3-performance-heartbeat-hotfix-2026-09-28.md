# C3.4 Performance Worker 心跳链去重与单部署热修复（2026-09-28）

## 问题与范围

目标单节点 Helm revision 57 上，两个 Celery Worker 都以 `celery@CHINAMI-762P0P5` 应答。直接获取两份原始 control broadcast 回复，确认普通 Worker 的 active/reserved/scheduled 均为 0，而 Performance Worker 的 active/reserved 为 0、scheduled 有 **45 条**，全部是 `heartbeat_performance_node`。Flower 在修复前五分钟窗口观察到约 426 次该任务的 received/succeeded 事件，远高于 30 秒心跳间隔对应的约 10 次。现有代码在每次 Worker ready 时播种新任务，而每条链又在结束时自续；旧 ETA 消息在 Worker 替换后继续存在，这与链数累积相符。这里的根因是代码与运行现象的推断，不把它记为经过故障注入的证明。

本次修复在 Redis 控制库为同一性能节点申请短租约。获得租约的心跳刷新数据库并安排下一次心跳；重复投递不再续链。租约比 30 秒心跳间隔短 1 秒；Worker ready 同时投递一次即时任务和一次租约过期后的兜底任务，覆盖旧进程获得租约后未播种继任者便退出的窗口。控制 Redis 失败时继续刷新心跳并重试后续去重。Performance Worker 的 Celery 节点名改为基于 Pod namespace/name 的唯一值，便于正确检查两个 Worker 的 control 回复。

## 镜像与发布预检

目标镜像 `registry.local/atp/worker:6755ed9f-heartbeat-c1fefcca` 以现场 Performance Worker 镜像 `6755ed9f`（Docker image ID `sha256:e9530ed14a9df4060e848f50f15c7ee8267ba62740994edcf646d5a4d44f0110`）为基础，只覆盖 `tasks_performance.py` 与 `celery_app.py`。覆盖前这两个文件与仓库原文件 SHA-256 一致；新文件 SHA-256 分别为 `c1fefcca10d4f05a440442c62595c37469fc1c7da8eec87a742f81400cdc5f78` 和 `4668f46cc6c6bb830cdcd844942d0afe0a11b5bcf54a27ccee6600155b2a6c4d`。Docker image ID 为 `sha256:565f36dcf32cd2be8e8c47f5b341ebd13e37660a4b06292726033dca4c2e67a7`。镜像中 `py_compile` 与 Python 导入检查通过，已导入目标 K3s containerd。它是**双文件补丁镜像**，不是当前 `main` 的完整源码构建。

针对 revision 57 的 22 文件一次性 Chart 快照位于 [`deploy/helm/atp-rev57-heartbeat-hotfix`](../../deploy/helm/atp-rev57-heartbeat-hotfix)。旧 rev56 快照在现网不加覆盖时与 revision 57 的 10 个普通资源和 1 个 Hook 完全匹配。新快照的无镜像候选仅改 Performance Worker 的启动命令与 Pod env；加上 `performanceWorker.imageTag` 覆盖后，只改 `Deployment/atp-single-node-atp-performance-worker` 的 `command[2]`、`env`、`image`。Chart 指纹、Flower 约束和服务端 Helm dry-run 均通过。升级前两份 Worker 原始 control 回复均无 active/reserved，数据库未完成性能运行数为 0；Performance Worker 的 45 条 scheduled 全部是心跳。原 Deployment 的 `Recreate` 策略保留。

本地受影响回归 **34 passed**，后端非集成全量在补齐独立扫描夹具后 **2693 passed / 2 skipped**，mypy 167 个源文件无问题，Ruff lint/format、Chart lint 与 `git diff --check` 通过。去重测试覆盖租约赢家、重复投递败者、控制 Redis 故障继续续链，以及 Worker ready 兜底播种。三个受影响测试文件已分别独立运行通过。首次全量运行发现新路由测试受其他测试残留的 `sys.modules` 假模块影响，出现 1 个测试隔离失败；改为从目标源码独立提取函数后，全量重跑通过。跳过项不算通过。

覆盖率命令按 `make test-backend-coverage` 的参数执行，测试仍为 **2693 passed / 2 skipped**，但总覆盖率 **80.54%**，低于仓库 82% 门槛，退出码 1。没有降低阈值，也没有把这项写成通过；覆盖率缺口需单独补测并重新执行门禁。

逐文件扫描还暴露旧 API 测试把共享数据库模块替换为窄 stub 后，审计服务首次导入缺 `AsyncSessionLocal`；根 conftest 现于完整默认 stub 可用时预加载审计模块。Windows 并发扫描器为每个测试文件分配唯一 `--basetemp`，并增加了命令构造回归；代表性 API 文件已单独重跑通过。8 并发试跑仍有两个使用 `tmp_path` 的文件遇到临时路径丢失，单独重跑均通过；按仓库标准 **4 并发** 完整扫描最终 **334 个文件通过、0 失败**。

## 现网观察

2026-09-28 09:27:31 北京时间，Helm **revision 58** 达到 `deployed`，命令使用同一候选 Chart/覆盖文件及 `--reuse-values --no-hooks --wait --atomic`。对比 revision 57 与 58 的 Helm manifest，唯一变更资源和字段与预检一致，普通资源数均为 10；没有新增迁移 Hook。Performance Worker Pod UID 更新为 `8707a230-4fa8-4737-9f4f-338e573a2d39`，其余五个 Pod 保持原 UID；6/6 Ready、零重启。两个 control 回复现在分别以 `performance@atp-single-node.atp-single-node-atp-performance-worker-684d75799b-dtrt4` 和 `celery@CHINAMI-762P0P5` 返回。首次发布后检查时两者 active/reserved 为 0，Performance Worker 的 scheduled 心跳从 45 条收敛到 **1 条**；性能节点数据库为 `online`、`enabled=true`，心跳年龄 29 秒，未完成性能运行仍为 0。Prometheus 5/5 target `up`、6 条规则均健康。发布后一分钟窗口 Flower 对新节点的心跳 received/succeeded 外推各约 2.67 次，旧同名节点为 0；这是短窗口计数外推，不当作长期稳定结论。

约五分钟后再次检查，Performance Worker 的 scheduled 仍为 1、节点在线且心跳年龄 21 秒，未完成性能运行仍为 0。Flower 五分钟 received 外推约 9.69 次，RSS 为 161,755,136 字节；这些也只属于短窗口观察。

## 后续边界

继续观察至少一个完整 UTC 日的心跳任务量、Flower RSS/重启和 Backend/Worker 抓取，再生成当日 SLO 报告。必要时可用 `helm rollback atp-single-node 57 -n atp-single-node --wait` 恢复；本次没有执行回滚。后续完整 Chart 升级前必须核对现存六个 Deployment 的模板漂移，并明确清空 `worker.imageTag` 与 `performanceWorker.imageTag` 覆盖。当前证据只覆盖单节点、低量任务与短窗口；代表性 7/14 日 SLO、Flower 长期稳定性及 P4/P9 发布门禁仍开放。
