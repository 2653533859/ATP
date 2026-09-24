# Hermes 独立验收栈

该 Compose 项目使用独立 PostgreSQL、Redis、MinIO、Backend 和单个 `default` 队列 Worker，不连接现有 K3s Release 或业务数据服务。Backend 仅在宿主机 `127.0.0.1:39184` 暴露。没有 Beat，因此不会自动调度备份、清理或其他周期任务。

## 准备

1. 在目标 Linux 保留目录结构 `deploy/hermes-evaluation/` 和 `backend/app/...`。`backend/` 构建上下文需要六个运行文件：`app/api/v1/hermes.py`、`app/api/deps.py`、`app/schemas/hermes.py`、`app/schemas/hermes_orchestration.py`、`app/services/hermes.py`、`app/services/audit.py`。Dockerfile 从已核对的 `registry.local/atp/backend:bdb84286` 叠加它们；构建前确认该基础镜像在目标 Docker 中存在。该基础镜像的 `/app/docker-start.sh` 已确认权限为 `0664`，会使 `migrate` 因 OCI `permission denied` 无法启动；叠加层将其修正为 `0755`。构建时将 `HERMES_EVAL_REVISION` 设为这六个文件对应的 Git 提交号，镜像标签固定为本次验收环境的 `20260924`。
2. 将 `secrets.env.example` 复制到仓库外的 `/opt/atp-hermes-eval-20260924/secrets.env`，限制权限为 `0600`，填写八个必填变量和 `HERMES_EVAL_REVISION`。每个密码与应用密钥独立生成高熵值；`HERMES_EVAL_MINIO_ROOT_USER` 使用专用用户名，管理员邮箱使用验收专用地址。不要将凭据放入命令行、提交到仓库或执行会展开凭据的 `docker compose config`。
3. 确认本机存在 `postgres:16-alpine`、`redis:7-alpine` 和 `minio/minio:RELEASE.2025-09-07T16-13-09Z`，或在受控窗口拉取；记录实际镜像摘要。

以下命令均在包含 `deploy/` 和 `backend/` 的验收目录执行；Shell 变量只保存文件路径，不保存凭据：

```bash
env_file=/opt/atp-hermes-eval-20260924/secrets.env
compose_file=deploy/hermes-evaluation/compose.yaml
docker compose --env-file "$env_file" -f "$compose_file" build backend
docker compose --env-file "$env_file" -f "$compose_file" up -d
docker compose --env-file "$env_file" -f "$compose_file" ps
curl -fsS http://127.0.0.1:39184/health
```

Compose 先等待 PostgreSQL 就绪并运行 `migrate`；只有迁移成功才启动 Backend，Backend 健康后才启动 Worker。本栈显式将迁移用户设为同一个专用数据库用户，满足 Alembic 的权限核对。`/health` 仅证明 API 进程响应；`/api/v1/hermes/governance/evaluation-set` 需要认证，须通过管理员登录或验收脚本核对题集版本 `2026-09-23.1` 和隔离夹具。请勿把本栈的 `/api/v1` 指向现有发布的 `8000` 端口。

从 Windows 访问时，用 SSH 本地转发把远端 `127.0.0.1:39184` 映射到本机 `127.0.0.1:39184`，再按 [`docs/hermes-evaluation-acceptance.md`](../../docs/hermes-evaluation-acceptance.md) 运行预检和显式 `--execute`。模型配置应在**隔离库**通过正常 API 创建并绑定隔离项目；不要复制业务库中加密的模型配置行。固定题需要编号 1 资产，应在全新库经正常业务流程创建，不改写现有业务主键。模型供应商地址必须可从 Backend 容器访问；容器内的 `127.0.0.1` 不是宿主机回环。

## 清理

先保存脱敏报告、人工复核结论与必要审计。确认不再需要隔离会话和夹具后，只针对本 Compose 项目执行：

```bash
docker compose --env-file "$env_file" -f "$compose_file" down --volumes
```

该命令删除本项目的三个专属命名卷，属于不可恢复的数据清理；执行前核对 `docker compose ... ps` 的项目名为 `atp-hermes-eval-20260924`。不要对现有 K3s namespace、Helm Release、q19 Compose 项目或业务数据库执行清理。
