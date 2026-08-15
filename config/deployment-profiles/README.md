# 部署配置档案

这里的文件只面向 Linux/Docker Compose/Helm 等 ATP 服务端部署，不是 Windows
`startup.ps1` 的启动档案。模板不包含真实密码，部署前请复制并填写实际值，并通过
机密管理系统或部署平台注入生产密钥。

## Android Worker 后端

`android-worker-backend.env.example` 用于公网 Backend、Beat 和普通 Linux Worker
共用的基础环境。它把 `ADB_SCAN_MODE` 设为 `worker`，并让普通 Worker 排除
`android,mobile_special` 队列：

```bash
cp config/deployment-profiles/android-worker-backend.env.example .env
# 填写 PostgreSQL、Redis、MinIO、APP_SECRET_KEY 和 ENCRYPTION_KEY
docker compose -f docker-compose.app.yml run --rm backend alembic upgrade head
docker compose -f docker-compose.app.yml up -d backend worker beat frontend
```

这里使用 `docker-compose.app.yml`，因为默认 `docker-compose.yml` 会同时启动本地
PostgreSQL、Redis 和 MinIO，不适合连接外部基础设施的部署方式。Helm 部署则将同名
变量注入对应的 Secret/ConfigMap，不要把该示例文件直接提交为生产 `.env`。

Windows 设备主机仍使用独立的
`config/startup-profiles/android-agent.env`，只监听 `android,mobile_special`，并在
本机通过 ADB 执行任务。两份配置必须连接同一个 ATP 数据库、Redis 和 MinIO；不要把
Windows Agent 的 `ADB_SCAN_MODE=local` 配置复制给公网 Backend。

生产部署前应确认：

- Redis、PostgreSQL 和 MinIO 只允许受信任的 Backend/Worker/Agent 网络访问；
- Linux Worker 没有监听 `android` 或 `mobile_special`；
- Beat 只有一个实例，Windows Agent 不启动 Beat；
- Windows Agent 可以出站访问服务端点，但不需要把 ADB 5037/设备 5555 暴露到公网。
