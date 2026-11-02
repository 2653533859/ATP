# 单节点 5e2173dd 发布与云端前端切换（2026-11-02）

## 背景与范围

2026-11-02 的第二次单节点发布：在当天 cef6d59b（Linux 账号保存修复）发布基础上，上线 D5 远程节点授权迁移 `20261102_0084`、后端安全依赖钉版（PyJWT 2.15.1、Pillow 13.0.0、OpenTelemetry 1.45.2）与前端审计修复（vue 3.5.44、vitest 4.1.12、brace-expansion override 5.0.12）。提交链：`3ca87068`（录制测试平台修复）→ `405140c0`（前端依赖修复）→ 本文档提交（values 回写与证据落档）。

## 代码和验证

- 前端：`npm audit --audit-level=high` 退出码 0（高危清零；残留 4 项 moderate 均为 js-beautify / editorconfig 链经 glob/minimatch 的开发期依赖）；`vue-tsc` 类型检查、生产构建、Vitest 86 文件 432 用例全绿（vue 3.5.44 / vitest 4.1.12 实测）。
- 后端：CI 运行 41476949313（提交 `3ca87068`）5 个 job 全部 success：Backend lint、Backend pytest（含 `--cov-fail-under=82` 覆盖率门禁与 standalone sweep）、Backend pytest (Windows)、Empty database migration、Frontend type-check + build。
- 合并 Dependabot #7（GitHub Actions 组 6 项升级：checkout v4→v7、setup-python v5→v7、upload-artifact v4→v7 等）；新版本动作由合并后的最终 CI 认证运行实际执行。

## 迁移演练与备份（发布前）

- 升级前私有备份：`/root/atp-release-backups/atp-20261102-d5-grants-before-upgrade.dump`，409435 字节，SHA-256 `df969facd8f646a569b82d45dae1bbb2a2084048404d9f383f15c3ad138dc592`（`pg_restore --list` 956 行可读）。
- 隔离库演练：前态 `20261102_0083` → 后态 `20261102_0084`（`remote_node_grants` 表就位，rows=0）；全程日志 `/opt/atp-release-5e2173dd-20261102/isolated-migration.log`，结论 `MIGRATION-DRILL-OK`（exit 0）。

## 发布过程及现场结果

- 目标 Linux `192.168.3.196` 的 `atp-single-node`。四个镜像基于既有 cef6d59b-site 运行镜像离线 overlay（vendored wheels 安装安全钉版依赖 + 覆盖提交源码），save/import 进 k3s（含 digest 核对，`k3s ctr -n k8s.io images ls` 在列）；镜像内 PyJWT 2.15.1 / Pillow 13.0.0 / OTel 1.45.2 核对一致，`pip check` 无破损，迁移文件 `20261102_0084_add_remote_node_grants.py` 在镜像内。
- Helm 升级为 **revision 69 / deployed**（`helm upgrade --force-conflicts`，处理历史 kubectl-set 字段所有权冲突；rev66/67 曾因此失败）。values 快照存档 `/root/atp-release-backups/helm-values-rev69-5e2173dd.yaml`。
- 六个 Pod 全部 1/1 Running：backend=`backend:5e2173dd-site`；beat/flower/web-recorder=`worker:5e2173dd-site`；worker=`worker:5e2173dd-site-runmetrics`；performance-worker=`worker:5e2173dd-site-heartbeat`。
- 发布后核验：`/health` 200；`/api/v1/runtime` 返回 `{"mode":"server","database":"postgresql","storage":"minio","execution":"celery"}`；数据库 `alembic_version=20261102_0084` 且 `remote_node_grants` 表存在；两个 Celery Worker（worker + performance）ping 均 pong。
- 云端前端切换：镜像 `registry.local/atp/frontend:405140c0`（本地 dist 打包上传，SHA-256 前缀 `f16cd98a`，服务器端重建字节一致），Compose 项目名保持 `atp-cloud-web-20261027`，env 沿用 `/opt/atp-cloud-web-20261027/.env`，切换入口 `/opt/atp-release-5e2173dd-20261102/cloud-web/compose.yaml`（容器 label `config_files` 已更新）。核验：容器 Running（health 转 healthy）、`http://192.168.3.196:8080/` 200 且入口资源为本次构建 `assets/index-2mRL5CgK.js`、`/api/v1/runtime` 经反代 200。回退路径：以 `/opt/atp-release-cef6d59b-20261102/cloud-web/` 原样 `up -d`，或把镜像标签改回 `frontend:cef6d59b`。
- 仓库 `deploy/helm/atp/values.yaml` 已把四个生效镜像标签回写为 rev69 实际值；`image.frontend.tag` 未回写（chart 不部署前端工作负载，前端由外部平台提供，rev69 中该键为惰性值 af71bd4d）。

## 已知残留（仅报告）

- Trivy worker 镜像 16 项 HIGH/CRITICAL 全部来自基础镜像内嵌工具：Apache JMeter 5.6.3 `lib/` 下 7 个 jar（jackson-core ×2、jackson-databind ×3、freemarker ×1 CRITICAL、jsoup ×1）与 k6 v2.2.0（Go 1.26.6 构建）9 项；backend 镜像本轮实扫为 0 项。修复路径：升级 JMeter 到集成修复版 jackson/freemarker/jsoup 的版本、k6 到以修复后 Go 工具链构建的版本，并完整重建 worker 镜像 + 性能执行器回归 + 重发 worker；服务器网络受限，本轮离线 overlay 发布链不重建，后续单独立项。
- 本 chart 的 frontend 镜像标签为惰性元数据，站点前端实际由 cloud-web 容器承载（见上）。
- D5 现场验收、D7 MSI 升级/新机验收为外部阻塞项，不在本发布范围。

上述现场结果只覆盖当次单节点短时检查与云端切换核验，不代表长期稳定、多节点或全部业务验收。
