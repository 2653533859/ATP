# C3.4 Backend 知识摘要脱敏热修复（2026-09-28）

## 变更与镜像

覆盖率补测发现 `redact_knowledge_value` 会把运行结果等结构化摘要先序列化成 JSON，导致嵌套 `token`、`Authorization` 等字段绕过自由文本正则。修复递归遮盖字典敏感键及列表/元组中的子项，再运行原有文本和 URL 脱敏。变更提交为 `4d451431`，本次无 Alembic 模型或迁移文件变更。

线上 Backend 基础镜像为 `registry.local/atp/backend:a49d0734`。新镜像 `registry.local/atp/backend:4d451431-knowledge-redact-79b9ccf4` 只覆盖 `app/services/knowledge.py`；该文件 SHA-256 为 `79b9ccf4754c5c088db165730225594c261e37b5feb78071a476e385f72582fe`。镜像在隔离网络构建，`py_compile` 成功；容器内导入服务并对嵌套敏感字段执行脱敏断言通过。镜像已导入目标 K3s containerd，未推送外部镜像仓库。

## Chart 预检与部署

当前主 Chart 的无覆盖渲染与 revision 58 的六个 Deployment 均有差异，并会改变迁移 Hook 镜像，因此拒绝直接发布主 Chart。改用仓库内针对 revision 57 固化、且实测无覆盖时与 revision 58 完全一致的 22 文件快照 `deploy/helm/atp-rev57-heartbeat-hotfix`。以该 Chart 和 Backend 新镜像运行仓库预检，基线资源和 Hook 一致；候选仅改变 `Deployment/atp-single-node-atp-backend` 的容器镜像字段。迁移 Hook 只因镜像 tag 不同而出现候选差异，正式命令使用 `--no-hooks` 跳过；本次无数据库迁移需要执行。`helm upgrade --dry-run=server --hide-secret` 退出码为 0。

2026-09-28 15:16（北京时间），执行 `helm upgrade atp-single-node deploy/helm/atp-rev57-heartbeat-hotfix -n atp-single-node --reuse-values --no-hooks --rollback-on-failure --wait --timeout 5m --set-string image.backend.tag=4d451431-knowledge-redact-79b9ccf4`，Helm **revision 59** 达到 `deployed`。

## 发布后验证

- 6/6 Pod Ready、零重启；只有 Backend Pod 被替换，五个 Worker、Beat、Flower 和 Recorder Pod 保持原名称及镜像。
- Backend 健康端点 HTTP 200，新 Pod 使用目标镜像；运行中容器内再次执行嵌套字段脱敏断言通过，测试值未写入输出。
- 发布后用同一 Chart 执行 `--require-baseline-match`，无变更且基线、10 个常规资源及 1 个 Hook 全部匹配 revision 59。
- 完整后端测试及 82% 覆盖率门禁、337 个逐文件独立测试、Ruff 和 mypy 的结果记录在 [`c3-coverage-closure-2026-09-28.md`](c3-coverage-closure-2026-09-28.md)。

## 边界

此为单节点 Backend 单文件热修复，不是 `4d451431` 完整 Backend/Chart 发布，也不代表完整源码 Chart 漂移已解决。主 Chart 六个 Deployment 的模板漂移仍需单独审查和收口；C3.4 代表性 7/14 日 SLO、完整发布后 UTC 日以及 Flower 长期稳定性仍开放。
