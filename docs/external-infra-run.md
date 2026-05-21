# ATP 外部基础设施启动说明

适用场景：PostgreSQL、Redis、MinIO 已由外部环境提供，ATP 只启动应用服务。

## 当前已接入的外部基础设施

- PostgreSQL: `172.26.202.29:5432`
- Redis: `172.26.202.29:6379`
- MinIO API: `172.26.202.29:9000`
- MinIO Console: `172.26.202.29:9001`

当前已完成的初始化：

- PostgreSQL 数据库 `atp` 已创建
- MinIO bucket `atp` 已创建
- 根目录 `.env` 已写入上述连接信息

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

## 默认管理员

- 用户名: `aicying`
- 密码: `020514.Cy`
- 邮箱: `ruieridianzi@gmail.com`

## 注意事项

- `backend` 启动命令中已包含 `alembic upgrade head`，首次启动会自动迁移数据库。
- 应用启动时会先做一次 Alembic head 校验：若 DB revision 与 head 不一致或 `alembic_version` 表缺失，会在日志输出 WARNING。生产环境部署前请确保已 `alembic upgrade head`。
- 应用启动时现在会自动确保 MinIO bucket 存在。
- 如果只验证 API 和前端，这套配置已经足够。
- 如果要执行 Web 用例，依赖容器内的 Playwright/Chromium 镜像构建成功。
- 如果要执行 Android 用例，还需要让 `worker` 容器能访问 ADB 设备；当前仓库能力已具备，但真机联调仍需要单独处理。诊断脚本：`bash scripts/android-network-doctor.sh <device-ip>:5555`。
