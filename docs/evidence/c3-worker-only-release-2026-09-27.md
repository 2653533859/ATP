# C3.4 普通 Worker 单镜像候选与发布门槛（2026-09-27）

## 范围与来源

此次候选只处理普通 Worker 首次运行结果计数漏算。修复代码来自 `b1828220` 的 `backend/app/core/metrics.py`；目标镜像 `registry.local/atp/worker:6755ed9f-runmetrics-b1828220` 是以 revision 56 基础 Worker 镜像叠加该单文件的热修复镜像，**不代表 `b1828220` 的完整源码镜像**。目标 Docker image ID 为 `sha256:f51bfa22182eafaccf9a3cfe8eb400c1297b12b22731c218fdb9c6f721bd0419`，已导入 K3s 的运行时 image ID 为 `sha256:300ce4d2dc1e2f02288a400363336abbddbfb61c02afd430d6632de38bfe5f2b`。隔离容器与已清理的临时 K3s Pod 均验证 15 条零值结果序列，详见[前次预检](c3-worker-metric-release-preflight-2026-09-27.md)。

从目标机 revision 56 的有界 Flower Chart 副本取得精确基线，封存在仓库 [`deploy/helm/atp-rev56-hotfix`](../../deploy/helm/atp-rev56-hotfix)。来源归档 SHA-256 为 `608a4bcd1b6f55620d4f2675638cfaa1e703486072ec37cca5e222f030298a5d`；候选归档 SHA-256 为 `fb2673f2f8cf973bf653f951704895cfa21b28aba8e938fc3c2514ffa64090af`。22 个文件中仅修改 `values.yaml`、`values.schema.json` 和 `templates/worker-deployment.yaml`：增加空值默认的 `worker.imageTag`，仅普通 Worker Deployment 可使用专用 tag。这个 Chart 是针对 revision 56 的**一次性精确发布快照**。后续完整 Chart 升级必须先审查此前发现的六项 Deployment 漂移，并显式清理 `worker.imageTag` 覆盖。

## 发布前只读验证

目标机使用 revision 56 的当前 Helm 用户 values 渲染该快照：未设置覆盖时，10 个普通资源和 1 个 Hook 与 revision 56 manifest 全部一致。仅设置 `worker.imageTag: 6755ed9f-runmetrics-b1828220` 后，10 个普通资源中只有 `Deployment/atp-single-node-atp-worker` 变化，唯一字段是 `spec.template.spec.containers[0].image`；Hook 无变化。目标机和本地的 `helm lint` 均通过。目标机使用 `--require-baseline-match --image-only --allow-change Deployment/atp-single-node-atp-worker --skip-hooks` 执行仓库/暂存 Chart 指纹与 release 差异预检，退出码 0；同一 Chart/覆盖文件运行 `helm upgrade --reuse-values --no-hooks --dry-run=server` 返回 0，预演目标 revision 57 的 manifest 也仅改变普通 Worker 镜像字段。比较与 dry-run 的 manifest、用户 values 只在进程中处理，没有写入仓库或证据文件。

运行中的普通 Worker Deployment 策略为 `Recreate`，该字段由现场 `kubectl-patch` 持有，revision 56 Helm manifest 未显式记录。以 Helm 字段管理器对只改镜像的 Deployment 执行 Kubernetes server-side dry-run，结果保留 `Recreate`；正式升级后仍须重新核对策略。普通 Worker 只有一个副本，替换时存在短暂任务消费中断；发布前必须确认 Celery active、reserved、scheduled 任务及相关队列处于安全状态。

## 正式发布门槛与复核

1. 仓库快照与目标机暂存 Chart 的逐文件指纹核对、基线完全一致及仅镜像字段变化的预检已通过；正式升级时必须使用同一 Chart 和覆盖文件，放行资源仍只能是 `Deployment/atp-single-node-atp-worker`，Hook 不变。
2. 记录升级前 Helm revision、六个业务 Pod 身份与状态、普通 Worker `Recreate` 策略，以及 Celery active/reserved/scheduled 和队列状态。确认热修复镜像在 K3s 可用，普通 Worker 的 `imagePullPolicy=Never`。
3. 仅按已预检的 Chart 和覆盖文件执行 `helm upgrade --reuse-values --no-hooks --wait`；`--no-hooks` 防止这次镜像修复触发 Alembic Job。升级后核对新 Helm manifest 与预检候选一致、只替换普通 Worker Pod、其余五个业务 Pod 未重建、策略仍为 `Recreate`、六个业务 Pod Ready 且没有新增异常重启。若策略或范围漂移，按升级前 revision 回滚。
4. 在首个受控任务事件前确认正式 Worker 指标端点和发布 Prometheus 已见到 15 条零值序列；随后运行受控任务，核对实际完成数与 Prometheus 增量及 Worker/Flower/Backend 健康。清理临时验证资源，并记录最终 revision 与时间。

截至本节只读验证结束，正式 Helm 升级、迁移 Job 和业务 Pod 替换尚未执行。`worker.imageTag` 会被 `--reuse-values` 保留；下一次完整发布须显式清除覆盖并审查六项 Deployment 漂移。普通 Worker 与 Performance Worker 当前存在同名 Celery 节点，队列检查须按 raw broadcast 回复与对应 Pod 区分；后续应为两者配置独立 hostname。即使单镜像发布与受控计数通过，代表性流量下连续 7/14 个完整 UTC 日 SLO、Flower 长期稳定性及 C3.5 最终 SHA 收口仍待独立完成。
