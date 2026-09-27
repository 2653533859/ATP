# C3.4 普通 Worker 单镜像发布与计数复核（2026-09-27）

## 范围与来源

此次候选只处理普通 Worker 首次运行结果计数漏算。修复代码来自 `b1828220` 的 `backend/app/core/metrics.py`；目标镜像 `registry.local/atp/worker:6755ed9f-runmetrics-b1828220` 是以 revision 56 基础 Worker 镜像叠加该单文件的热修复镜像，**不代表 `b1828220` 的完整源码镜像**。目标 Docker image ID 为 `sha256:f51bfa22182eafaccf9a3cfe8eb400c1297b12b22731c218fdb9c6f721bd0419`，已导入 K3s 的运行时 image ID 为 `sha256:300ce4d2dc1e2f02288a400363336abbddbfb61c02afd430d6632de38bfe5f2b`。隔离容器与已清理的临时 K3s Pod 均验证 15 条零值结果序列，详见[前次预检](c3-worker-metric-release-preflight-2026-09-27.md)。

从目标机 revision 56 的有界 Flower Chart 副本取得精确基线，封存在仓库 [`deploy/helm/atp-rev56-hotfix`](../../deploy/helm/atp-rev56-hotfix)。来源归档 SHA-256 为 `608a4bcd1b6f55620d4f2675638cfaa1e703486072ec37cca5e222f030298a5d`；候选归档 SHA-256 为 `fb2673f2f8cf973bf653f951704895cfa21b28aba8e938fc3c2514ffa64090af`。22 个文件中仅修改 `values.yaml`、`values.schema.json` 和 `templates/worker-deployment.yaml`：增加空值默认的 `worker.imageTag`，仅普通 Worker Deployment 可使用专用 tag。这个 Chart 是针对 revision 56 的**一次性精确发布快照**。后续完整 Chart 升级必须先审查此前发现的六项 Deployment 漂移，并显式清理 `worker.imageTag` 覆盖。

## 发布前只读验证

目标机使用 revision 56 的当前 Helm 用户 values 渲染该快照：未设置覆盖时，10 个普通资源和 1 个 Hook 与 revision 56 manifest 全部一致。仅设置 `worker.imageTag: 6755ed9f-runmetrics-b1828220` 后，10 个普通资源中只有 `Deployment/atp-single-node-atp-worker` 变化，唯一字段是 `spec.template.spec.containers[0].image`；Hook 无变化。目标机和本地的 `helm lint` 均通过。目标机使用 `--require-baseline-match --image-only --allow-change Deployment/atp-single-node-atp-worker --skip-hooks` 执行仓库/暂存 Chart 指纹与 release 差异预检，退出码 0；同一 Chart/覆盖文件运行 `helm upgrade --reuse-values --no-hooks --dry-run=server` 返回 0，预演目标 revision 57 的 manifest 也仅改变普通 Worker 镜像字段。比较与 dry-run 的 manifest、用户 values 只在进程中处理，没有写入仓库或证据文件。

升级前普通 Worker Deployment 策略为 `Recreate`，该字段由现场 `kubectl-patch` 持有，revision 56 Helm manifest 未显式记录。以 Helm 字段管理器对只改镜像的 Deployment 执行 Kubernetes server-side dry-run，结果保留 `Recreate`。普通 Worker 只有一个副本，替换时存在短暂任务消费中断。

## 正式发布与范围核验

升级前数据库检查显示五类运行的活动任务、执行租约和 Hermes 活动项均为 0；Redis 普通 Worker 的六条队列均为 0。两个 Celery responder 的 active/reserved 均为 0，普通 Worker scheduled 为 0；Performance Worker responder 另有 45 条 scheduled。现场仍有约每分钟 4 次维护扫描流量，因此这里只确认普通 Worker 可进行有界替换，不宣称整个平台完全静默。raw broadcast 保留两个同名回复，按 `active_queues` 队列归属区分。

使用已通过预检的 Chart 与覆盖文件完成 `helm upgrade --reuse-values --no-hooks --rollback-on-failure --wait --timeout 5m`。Helm revision 57 于 **2026-09-27 18:41:47 北京时间**达到 `deployed`。升级前后 release manifest 差异只有 `Deployment/atp-single-node-atp-worker` 的镜像字段；没有新建 Alembic Job。普通 Worker Pod UID 从 `817de...` 变为 `708f6...`，其余五个业务 Pod UID 未变。普通 Worker 的 `Recreate` 策略仍在；六个业务 Pod 均 Ready、重启计数 0。正式 Worker 运行时 image ID 为 `sha256:300ce4d2dc1e2f02288a400363336abbddbfb61c02afd430d6632de38bfe5f2b`。

## 指标与受控任务复核

受控任务前，正式 Worker `/metrics` 中 `case/suite/plan` × 五种终态共 15 条结果序列均为 0；发布 Prometheus 也查询到 15 条序列。canary service 于 18:44:31 北京时间以退出码 0 完成，执行了 12 次认证读取和 2 条 `passed` 的 case run。任务后直接读取 Worker 的 `case/passed` 计数为 2；Prometheus 在新 Pod 的 UTC 样本从 10:42:25 的 0，经 10:44:05 的 1，到 10:44:25 的 2，与两次受控运行一致。发布 Prometheus 五个 target 均 `up`，六条规则健康；Backend 与 Flower 健康接口均返回 HTTP 200。

## 后续边界

如后续发现本次热修复引发异常，应急回滚路径为 `helm rollback atp-single-node 56 -n atp-single-node --wait`；本次未执行回滚。`worker.imageTag` 会被 `--reuse-values` 保留，正常下一次完整发布须显式清理该覆盖，并先审查主 Chart 相对 revision 56 的六个 Deployment 漂移。`atp-rev56-hotfix` 仅供这次精确热修复，不作为后续主 Chart。普通 Worker 与 Performance Worker 当前存在同名 Celery 节点，后续应为两者配置独立 hostname。此次只证明单节点、受控低流量下的零值序列和两次运行计数；代表性流量下连续 7/14 个完整 UTC 日 SLO、Flower 长期稳定性及 C3.5 最终 SHA 收口仍待独立完成。
