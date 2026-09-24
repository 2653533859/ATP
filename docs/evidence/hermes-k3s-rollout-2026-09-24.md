# Hermes 单节点 K3s 发布记录（2026-09-24）

## 范围与前置检查

- 目标：Linux `192.168.3.196`，namespace 和 Helm release 均为 `atp-single-node`。这是单节点开发/联调环境，不是多节点发布验收。
- 发布前 Helm revision 46 为 `deployed`，Backend 镜像为 `registry.local/atp/backend:bdb84286`，`/health` 返回 200。六个 Deployment 均为 1/1 Ready。
- 当前仓库 Chart 与目标 `/opt/atp-build-bdb84286/deploy/helm/atp` 的 `Chart.yaml`、Backend Deployment、迁移 Job、MinIO 生命周期 Job 文件 SHA-256 一致。发布值引用运行 Secret 与独立迁移 Secret，Backend 使用 `hostNetwork`、`imagePullPolicy: Never`、`maxSurge: 0`。
- `helm upgrade --dry-run=server --reuse-values --set image.backend.tag=71b0b0b3` 通过。逐项比较 Helm revision 46/47 的用户值，唯一变化路径为 `image.backend.tag`。

## 发布与核对

- 将独立验收镜像 `registry.local/atp/hermes-evaluation-backend:20260924` 重标记为 `registry.local/atp/backend:71b0b0b3` 并导入 K3s containerd。Docker 镜像 ID 为 `sha256:c547c842f8fed2f6fd5fd6d017b3e7c266ffb55dd4a876f88ad417c241821722`，代码标签为 `71b0b0b394b6bc86c4627aaca96605a95ed025c5`；镜像是在已验证的 `bdb84286` 基础上叠加七个 Hermes 运行文件。
- 使用 `helm upgrade ... --reuse-values --set image.backend.tag=71b0b0b3 --rollback-on-failure --wait --timeout 5m` 完成 revision 47，状态 `deployed`。迁移 Hook 成功；数据库 `alembic_version` 为 `20260914_0074`。
- 升级后 Backend 镜像标签为 `71b0b0b3`，Worker 保持 `6755ed9f`。六个 Deployment 均为 1/1 Ready，Backend `/health` 返回 200；匿名读取 Hermes 评测题集返回预期的 401。OpenAPI 显示 Hermes 评测入口存在。
- 30 秒内四次采样均为六个 Pod Ready、Backend 健康 200，重启计数没有增加。新 Backend Pod 重启 0 次；其余五个 Pod 各有发布前已有的 1 次重启。Backend 最近五分钟日志未见 `ERROR`、`Traceback`、`MissingGreenlet` 或 `Exception`。
- 发布时新 Backend Pod 出现一次临时 `FailedScheduling`，原因是旧 Pod 尚占用宿主机端口；随后自动就绪，四次采样中未再出现不可用或新增重启。

## 结论与边界

本次完成已独立验收的 Hermes 七文件镜像在现有单节点 K3s Release 上的发布和有界健康核对。真实模型 10/10 题、规划挑战题、权限与反馈行为的验收证据仍以[独立环境记录](hermes-isolated-acceptance-2026-09-24.md)为准；本次没有在现有业务库重复执行认证后的 Hermes 题集，也没有验证长期运行、多节点故障域、7/14 天 SLO 校准或独立 MinIO 灾备。P4/P9 发布门禁保持原状态。

可回滚目标为 Helm revision 46；本次未执行回滚。若需要回滚，先核对当前 Secret 与 revision 46 的兼容性，再执行 `helm rollback atp-single-node 46 -n atp-single-node --wait` 并复核迁移版本、健康、工作队列和权限审计。
