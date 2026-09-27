# C3.4 Worker 运行结果指标发布预检（2026-09-27）

## 目标与工件

仓库提交 `b1828220` 在 Worker 指标端点启动前初始化 15 条零值运行结果序列，避免首次事件因无前一个零样本而漏出 Prometheus `increase`。当前线上 Helm revision 56 的五个 Worker 镜像工作负载均使用 `registry.local/atp/worker:6755ed9f` 且 `imagePullPolicy=Never`；该提交尚未部署。

在目标机从 `b1828220` 导出的 Backend 源码归档 SHA-256 为 `553c1d8d28f4ac7666575e52f39ee8b2c10e2a5eaebf24550d5bd9f2cb7cedbb`，指标文件 SHA-256 为 `cd56055262e3a92bd7aec6f10c250e54dccb5f291a7b0dc5321b5431adcbcf0b`。完整 Worker Dockerfile 构建因主机缺少 buildx 而先改用经典 builder；经典构建停在上游 k6 源码克隆并已终止，没有产出完整提交镜像。随后仅将上述指标文件叠加到线上同款基础镜像（本地 image ID `sha256:e9530ed14a9df4060e848f50f15c7ee8267ba62740994edcf646d5a4d44f0110`），生成 `registry.local/atp/worker:6755ed9f-runmetrics-b1828220`，镜像 ID `sha256:f51bfa22182eafaccf9a3cfe8eb400c1297b12b22731c218fdb9c6f721bd0419`。镜像标签同时标明基础镜像与补丁 SHA；它是**单文件热修复镜像**，不能宣称包含提交 `b1828220` 的全部 Backend 源码。

镜像内隔离容器启动指标 HTTP 端点后，`case/suite/plan` × 五种终态的 15 条序列均为 0，`/metrics` 可读取。镜像已导入目标 K3s containerd；使用 `imagePullPolicy=Never` 创建的临时 Pod 也验证 15 条零值序列，退出码 0，随后已删除。该验证不包含正式 Worker 的任务执行或发布 Prometheus 抓取。

## Chart 与 release 差异

仓库 Chart 新增 `worker.imageTag`：空值继承共享的 `image.worker.tag`；非空时仅普通 Worker Deployment 使用覆盖 tag。Helm 模板定向回归确认，使用单节点示例 values 时，设置 `worker.imageTag=b1828220` 只改变普通 Worker 的 manifest 镜像字段。`helm lint` 通过。

目标机另将本次 Chart（随后提交为 `54f99a46`）与预检脚本暂存于 `/opt/atp-release-preflight-20260927`，归档 SHA-256 为 `d7da9547a76bc9b675934b155fcd09cac601b6250db2ff2637e402ba9f094441`。用当前 release 用户 values 与仅含 `worker.imageTag: 6755ed9f-runmetrics-b1828220` 的非敏感覆盖文件执行只读预检，Chart 22 文件指纹一致、Flower 边界与迁移 Hook 不变，但仍返回退出码 1：

| Deployment | 相对 revision 56 的变化 |
| --- | --- |
| Backend | 更新策略、配置校验注解 |
| Beat | 配置校验注解 |
| Flower | `Recreate` 改为无 surge 的 `RollingUpdate`、配置校验注解 |
| Performance Worker | 更新策略、注解、命令、Pod 身份环境变量 |
| Web Recorder | 更新策略、注解、启动命令与 display 抢占逻辑 |
| 普通 Worker | 更新策略、注解、命令、Pod 身份环境变量，以及唯一改变的镜像 tag |

这些变化会导致 6 个 Pod template 更新；`image.worker.tag` 共享值若直接覆盖，还会让另外四个 Worker 镜像工作负载换用新镜像。本次仅做镜像构建、隔离验证与只读 release 预检；**没有执行 Helm upgrade、数据库迁移或业务 Pod 更新**。不得通过旧 Chart、`kubectl set image` 或无审核的 `--allow-change` 绕过发布门禁。

使用同一暂存 Chart 和覆盖文件运行 `helm upgrade ... --reuse-values --no-hooks --dry-run=server` 返回 0，渲染 manifest 仅在进程内检查，未保存或输出其中的 values/Secret。服务端 dry-run 证明候选可由集群解析，不会改变预检对六个待审资源的拒绝结论。

## 后续发布判据

若选择完整 Chart 对齐发布，需要逐项审查上述六处运行行为、确认固定镜像与迁移 Hook、使用相同 values 做 Helm 服务端 dry-run，并在维护窗口按预检放行范围升级、逐 Pod 验证与保留 revision 56 回滚路径。若目标是严格只更新普通 Worker，需要先让候选 Chart 在保留其余线上资源 manifest 的条件下通过预检；当前 `worker.imageTag` 单独不能完成这一点。发布后还须验证正式 Worker 的零值序列先于首个任务事件、Prometheus 抓取和受控两次运行增量，再开始新的代表性 SLO 窗口。C3.4/C3.5 仍开放。
