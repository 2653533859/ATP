# ATP 外部基础设施启动说明

适用场景：PostgreSQL、Redis、MinIO 已由外部环境提供，ATP 只启动应用服务。

## 外部基础设施配置

本文档不固化任何公网地址、用户名或密码。请复制 `.env.example` 为 `.env`，或使用启动配置页面/启动档案填写目标环境的实际值：

```env
POSTGRES_HOST=<server-host>
POSTGRES_PORT=5432
POSTGRES_DB=atp
POSTGRES_USER=<database-user>
POSTGRES_PASSWORD=<database-password>
REDIS_HOST=<server-host>
REDIS_PORT=6379
REDIS_PASSWORD=<redis-password-if-enabled>
MINIO_HOST=<server-host>
MINIO_PORT=9000
MINIO_ROOT_USER=<minio-user>
MINIO_ROOT_PASSWORD=<minio-password>
MINIO_BUCKET=atp
```

数据库、MinIO bucket 和初始管理员应由部署环境按实际凭据创建；不要将真实 `.env`、管理员密码或对象存储密钥写入仓库或文档。启动前先执行 `scripts/windows-local.ps1 -Action doctor -EnvFile .env`（Windows）或对应的 Compose/Helm 预检。

## 启动方式

在仓库根目录执行：

```bash
docker compose -f docker-compose.app.yml up --build -d
```

查看状态：

```bash
docker compose -f docker-compose.app.yml ps
```

查看日志：

```bash
docker compose -f docker-compose.app.yml logs -f backend
docker compose -f docker-compose.app.yml logs -f worker
docker compose -f docker-compose.app.yml logs -f beat
```

停止服务：

```bash
docker compose -f docker-compose.app.yml down
```

## 访问入口

- 前端: `http://localhost`
- 后端健康检查: `http://localhost:8000/health`
- Flower: `http://localhost:5555`

## 初始管理员

初始管理员由 `FIRST_ADMIN_USERNAME`、`FIRST_ADMIN_PASSWORD` 和 `FIRST_ADMIN_EMAIL` 配置。生产环境必须使用部署时生成的强密码，并在首次登录后轮换；本文档不记录具体账号或密码。

## 注意事项

- `backend` 启动命令中已包含 `alembic upgrade head`，首次启动会自动迁移数据库。
- 应用启动时会先做一次 Alembic head 校验：若 DB revision 与 head 不一致或 `alembic_version` 表缺失，会在日志输出 WARNING。生产环境部署前请确保已 `alembic upgrade head`。
- 应用启动时现在会自动确保 MinIO bucket 存在。
- 如果只验证 API 和前端，这套配置已经足够。
- 如果要执行 Web 用例，依赖容器内的 Playwright/Chromium 镜像构建成功。
- 如果要执行 Android 用例，还需要让 `worker` 容器能访问 ADB 设备；当前仓库能力已具备，但真机联调仍需要单独处理。诊断脚本：`bash scripts/android-network-doctor.sh <device-ip>:5555`。
