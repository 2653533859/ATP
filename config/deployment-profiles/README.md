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
docker compose -f docker-compose.app.yml run --rm backend migrate
docker compose -f docker-compose.app.yml up -d backend worker beat frontend
```

这里使用 `docker-compose.app.yml`，因为默认 `docker-compose.yml` 会同时启动本地
PostgreSQL、Redis 和 MinIO，不适合连接外部基础设施的部署方式。Helm 部署则将同名
变量注入对应的 Secret/ConfigMap，不要把该示例文件直接提交为生产 `.env`。

`migrate` 会对短暂的 PostgreSQL DNS/就绪错误作有界、脱敏重试；backend 未通过
`/health` 前，依赖它的应用服务不会启动。若迁移耗尽重试，保留日志并修复外部基础
设施，不要用无限容器重启掩盖问题。

Helm 可以直接使用仓库提供的 overlay：

```bash
helm upgrade --install atp deploy/helm/atp \
  -f deploy/helm/atp/values-android-worker.example.yaml \
  --set image.repository=<registry>/atp \
  --set image.backend.tag=<release> \
  --set image.worker.tag=<release> \
  --set image.frontend.tag=<release>
```

overlay 只放非敏感的扫描模式和队列设置，并默认引用名为
`atp-runtime-secrets` 的外部 Secret；请按实际 Secret 名称覆盖 `secret.existingName`。

Windows 设备主机仍使用独立的
`config/startup-profiles/android-agent.env`，只监听 `android,mobile_special`，并在
本机通过 ADB 执行任务。两份配置必须连接同一个 ATP 数据库、Redis 和 MinIO；不要把
Windows Agent 的 `ADB_SCAN_MODE=local` 配置复制给公网 Backend。

生产部署前应确认：

- Redis、PostgreSQL 和 MinIO 只允许受信任的 Backend/Worker/Agent 网络访问；
- Linux Worker 没有监听 `android` 或 `mobile_special`；
- Beat 只有一个实例，Windows Agent 不启动 Beat；
- Windows Agent 可以出站访问服务端点，但不需要把 ADB 5037/设备 5555 暴露到公网。
