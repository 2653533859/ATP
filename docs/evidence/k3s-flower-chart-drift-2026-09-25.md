# Flower 旧 Chart 漂移与有界保留恢复（2026-09-25）

## 发现

Hermes Engineer/Editor 验收后追查到正式单节点 Helm revision 55 的 Flower 于 2026-09-25 05:24:52 UTC 因 `OOMKilled/137` 重启一次，内存上限为 512Mi。该 Pod 从 2026-09-24 09:41:41 UTC 运行至退出，约 19 小时 43 分。重启后验收时使用 158Mi，后续只读检查增至 271Mi；这是两个时点的观测，不能据此推算长期增长率。

仓库 Chart 已有 `maxTasks=1000`、`maxWorkers=100`、`purgeOfflineWorkers=300`，并在 9 月 7 日 revision 10 曾部署、验证。但 revision 55 使用的发布机旧 Chart 副本没有 Flower `args`；运行中 Flower 2.0.1 显示默认 `max_tasks=100000`、`max_workers=5000`、`purge_offline_workers=None`。因此可确认**发布 Chart 漂移导致有界保留配置丢失**。没有 OOM 时的堆快照，不能断定它是唯一内存来源。

## 恢复与核验

- 从 revision 55 的发布机 Chart 复制到 `/opt/atp-hermes-retrieval-98bd86ca/chart-flower-bounded-20260925`，只给 Flower 增加仓库已验证的三个参数，并把单副本 `hostNetwork` 的策略显式设为 `Recreate`，与升级前现场策略一致。
- `helm lint` 通过；用 revision 55 用户 values 渲染后，与当前 release 比较了全部 10 个非 Hook 资源：资源集合相同，只有 Flower Deployment 的 `args` 与显式策略不同，镜像、资源限制、Secret 引用和其他工作负载未变。
- `helm upgrade --reuse-values --no-hooks --atomic --wait` 成功，revision 56 为 `deployed`；升级后的 Helm manifest 与预检候选的 10 个非 Hook 资源完全一致。`--no-hooks` 是本次纯 Flower 参数恢复的范围控制，未触发迁移 Job。
- 新 Flower PID 1 参数实测为 `--max_tasks=1000 --max_workers=100 --purge_offline_workers=300`，Pod 新实例 `0` 重启，初始内存 104Mi、限制仍为 512Mi；其余五个业务 Pod 保持原实例。6/6 Pod Ready，Backend `/health` 与 Flower `/healthcheck` 均为 200。
- 用于比较的临时 values 和渲染文件已从发布机删除；没有把 Secret 或凭据写入本证据。

## 边界与后续

本次关闭发布环境的**配置漂移**，不抹去 revision 55 的 OOM 历史，也不凭启动时 104Mi 宣称长期 OOM 问题已经解决。继续观察真实事件积累下 Flower 内存和重启；若再增长，检查任务载荷及其他缓存。后续每次 Helm 发布须使用当前仓库 Chart，预检渲染结果的 Flower 参数与 `hostNetwork` 更新策略，避免旧发布副本再次覆盖。C3.4 的代表性 7/14 日 SLO 与长期稳定性门禁仍未关闭。
