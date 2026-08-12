# 启动配置中心

ATP 的启动配置由仓库根目录 `.env` 提供，后端、Celery Worker、Beat 和前端分别在启动时读取其中的变量。配置页不会热更新正在运行的进程，修改后需要导出 `.env` 并重启相关服务。

## UI 入口

以管理员登录前端后，打开：

```text
系统管理 → 启动配置
http://127.0.0.1:5173/system/startup-config
```

页面支持：

- Docker Compose：使用 `postgres`、`redis`、`minio` 服务名
- 远端基础设施：填写实际 Linux 主机地址（例如当前环境的 `172.31.27.133`）；源码不固化环境地址
- 恢复 `.env.example` 示例值
- 在浏览器本地保存草稿
- 复制或下载完整 `.env`

草稿只保存在当前浏览器的 `localStorage`，不会上传到 ATP 后端。生产密钥仍应使用组织认可的密钥管理方式，并限制 `.env` 文件权限。

## 配置分组

Web 录制默认在后端进程内启动可见 Chromium，适合 Windows 本地联调。Windows 也可以将 `WEB_RECORDER_MODE=worker`，此时 `local-dev.cmd up` 会自动托管独立的 `python -m app.web_recording_worker` 进程；Windows 桌面模式不需要填写 `WEB_RECORDER_DISPLAY`。多副本或 Linux 部署可将 `WEB_RECORDER_MODE=worker`，再通过 Compose/Helm 启动独立 Worker；API 通过 Redis 路由会话，不依赖副本粘性。Linux Worker 必须配置可访问的 X display（例如 `WEB_RECORDER_DISPLAY=:99`）。Worker 心跳过期后，API 会拒绝新会话并返回明确的“没有可用录制 Worker”提示，不会留下无法控制的会话。

完整的 Compose、Helm 和故障排查说明见 [`docs/web-recording-worker.md`](web-recording-worker.md)。

页面与 `.env.example`、后端 `backend/app/core/config.py` 对齐，当前包含 117 个配置项：

### 基础设施

`POSTGRES_HOST`、`POSTGRES_PORT`、`POSTGRES_CONNECT_TIMEOUT_SECONDS`、`POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD`、`REDIS_HOST`、`REDIS_PORT`、`REDIS_PASSWORD`、`REDIS_CONNECT_TIMEOUT_SECONDS`、`MINIO_HOST`、`MINIO_PORT`、`MINIO_ROOT_USER`、`MINIO_ROOT_PASSWORD`、`MINIO_BUCKET`、`MINIO_CONNECT_TIMEOUT_SECONDS`

其中三个 `*_CONNECT_TIMEOUT_SECONDS` 默认值均为 `5`，取值范围为 `1-120` 秒，分别限制 PostgreSQL、Redis 和 MinIO 的连接/操作等待时间；PostgreSQL 超时还覆盖 Backend 的 Alembic 启动检查和数据库初始化。远端档案会将 `POSTGRES_HOST`、`POSTGRES_USER`、`MINIO_HOST` 和 `MINIO_ROOT_USER` 设置为占位符，必须替换为目标主机的真实连接信息后才能通过必填检查；源码不预置任何特定环境的用户名或地址。

### 应用与安全

`APP_ENV`、`APP_SECRET_KEY`、`APP_ACCESS_TOKEN_EXPIRE_MINUTES`、`APP_REFRESH_TOKEN_EXPIRE_DAYS`、`APP_CORS_ORIGINS`、`APP_AUTH_COOKIE_SECURE`、`APP_AUTH_COOKIE_SAMESITE`、`APP_AUTO_CREATE_TABLES`、`FIRST_ADMIN_USERNAME`、`FIRST_ADMIN_PASSWORD`、`FIRST_ADMIN_EMAIL`、`WEBHOOK_API_KEY`、`ENCRYPTION_KEY`

### 任务执行与设备

`CELERY_CONCURRENCY`、`CELERY_QUEUES`、`WORKER_METRICS_PORT`、`FILE_RETENTION_DAYS`、`STALE_PENDING_CLEANUP_ENABLED`、`STALE_PENDING_TIMEOUT_MINUTES`、`STALE_PENDING_CLEANUP_INTERVAL_SECONDS`、`RUN_CLEANUP_ENABLED`、`RUN_RETENTION_DAYS`、`RUN_CLEANUP_BATCH_SIZE`、`ADB_SCAN_ENABLED`、`ADB_SCAN_INTERVAL`、`ADB_SCAN_MODE`、`ANDROID_WORKER_ID`、`ANDROID_WORKER_QUEUE`、`ANDROID_WORKER_REGISTRY_PREFIX`、`ANDROID_WORKER_HEARTBEAT_SECONDS`、`ANDROID_WORKER_TTL_SECONDS`、`ADB_RECONNECT_ENABLED`、`ADB_RECONNECT_MAX_ATTEMPTS`、`ADB_RECONNECT_BACKOFF_MS`、`ADB_HEARTBEAT_ENABLED`、`ADB_HEARTBEAT_INTERVAL_SEC`、`ADB_HEARTBEAT_FAILURE_THRESHOLD`、`CASE_SNAPSHOT_MAX_PER_CASE`、`MOCK_STANDALONE_PORT`、`WEB_RECORDER_MODE`、`WEB_RECORDER_WORKER_QUEUE_PREFIX`、`WEB_RECORDER_WORKER_ID`、`WEB_RECORDER_WORKER_MAX_SESSIONS`、`WEB_RECORDER_WORKER_HEARTBEAT_SECONDS`、`WEB_RECORDER_WORKER_TTL_SECONDS`、`WEB_RECORDER_COMMAND_TIMEOUT_SECONDS`、`WEB_RECORDER_REPLY_TTL_SECONDS`、`WEB_RECORDER_SESSION_TTL_SECONDS`、`WEB_RECORDER_DISPLAY`，以及性能指标采样、性能节点和性能执行器配置。

其中 `ANDROID_WORKER_ID` 只应在 Windows Android Agent 进程中填写；留空表示不注册。`scripts/windows-android-worker.ps1 up` 会自动生成当前机器的 ID，设备页通过 Redis 心跳显示在线 Agent。

注意：`CELERY_CONCURRENCY` 只有在使用支持多进程/多线程的 Worker pool 时才代表并发槽位；Windows 本地脚本使用 `--pool=solo`，实际为单槽位，生产并发应通过 Linux Worker 的进程池或多个 Worker 副本实现。

### 通知、AI 与观测

`SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASSWORD`、`SMTP_FROM`、`SMTP_SSL`、`SMTP_TLS`、`AI_HEALING_ENABLED`、`AI_HEALING_TIMEOUT_SECONDS`、`AI_HEALING_DAILY_LIMIT`、`AI_HEALING_CACHE_TTL_SECONDS`、`AI_HEALING_FEW_SHOT_ENABLED`、`AI_HEALING_FEW_SHOT_TOP_N`、`AI_HEALING_VISION_ENABLED`、`AI_HEALING_VISION_DAILY_LIMIT`、`AI_HEALING_APPLY_ENABLED`、`PERFORMANCE_TARGET_ALLOWLIST`、`PERFORMANCE_MAX_VUS`、`PERFORMANCE_MAX_DURATION_SECONDS`、`RATE_LIMIT_LOGIN`、`RATE_LIMIT_WEBHOOK`、`LOG_LEVEL`、`SLOW_QUERY_LOG_ENABLED`、`SLOW_QUERY_THRESHOLD_MS`、`STORAGE_ALERT_SIZE_GB`、`STORAGE_ALERT_INTERVAL_SECONDS`、`STORAGE_ALERT_MAX_SCAN_OBJECTS`、`DASHBOARD_ALERT_DEFAULT_SUPPRESS_MIN`、`DB_BACKUP_ENABLED`、`DB_BACKUP_RETAIN_DAILY`、`DB_BACKUP_RETAIN_WEEKLY`、`DB_BACKUP_PREFIX`、`OTEL_EXPORTER_OTLP_ENDPOINT`、`OTEL_SERVICE_NAME`、`OTEL_TRACES_SAMPLER`、`OTEL_TRACES_SAMPLER_ARG`、`JAEGER_UI_URL`、`VITE_BACKEND_ORIGIN`

## 建议启动顺序

1. 在配置页选择预设并填写真实密码、密钥和跨域来源。
2. 下载 `.env`，替换仓库根目录的 `.env`。
3. 先确认 PostgreSQL、Redis、MinIO 可达，再执行 `alembic upgrade head`。
4. 重启 Backend、Worker、Beat 和前端；检查 `http://127.0.0.1:8000/health`。

本机 Docker 启动、Windows 连接远端基础设施以及多档案选择式启动的完整命令见 [`windows-local-run.md`](windows-local-run.md)。也可以直接执行根目录的 `startup.cmd` 进入启动方式选择。
