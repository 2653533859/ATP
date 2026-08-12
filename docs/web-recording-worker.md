# Web 录制 Worker

Web 录制有两种运行方式：

| 模式 | 适用场景 | 启动方式 | 会话状态 |
| --- | --- | --- | --- |
| `local` | Windows 日常开发、单进程联调 | 按现有方式启动后端 | 后端进程内存 |
| `worker` | Windows 隔离进程、Linux、容器、多副本 API | Windows 执行 `local-dev.cmd up`；Linux/容器启动 `python -m app.web_recording_worker` | Redis 路由元数据，浏览器对象留在 Worker |

## Windows 本地模式

保持 `.env` 中：

```dotenv
WEB_RECORDER_MODE=local
```

不需要额外启动录制 Worker。浏览器在后端进程所在的 Windows 主机打开，适合录制本机可访问的测试页面。

如果希望把浏览器会话从 API 进程中隔离，可改为：

```dotenv
WEB_RECORDER_MODE=worker
```

然后执行 `local-dev.cmd up`。Windows 启动脚本会自动托管 Web Recording Worker，并在 `local-dev.cmd status`、`local-dev.cmd logs` 和 `local-dev.cmd down` 中统一显示、查看日志和停止它；Windows 桌面模式不需要 Xvfb，也不需要填写 `WEB_RECORDER_DISPLAY`。API 与 Worker 必须使用同一个 Redis 和 `WEB_RECORDER_WORKER_QUEUE_PREFIX`。

## Docker Compose

先保证 `.env` 中的 PostgreSQL、Redis、MinIO 地址可用，然后启动可选的录制服务：

```powershell
docker compose --profile web-recorder up -d backend web-recorder
```

API 和 Worker 必须使用同一个 Redis。录制 Worker 使用 `backend/Dockerfile.worker`，启动时创建 `Xvfb :99`，并通过 `WEB_RECORDER_DISPLAY=:99` 运行可见 Chromium。若使用外部 X server，可覆盖 `WEB_RECORDER_DISPLAY` 和 Compose command。

## Kubernetes Helm

在生产 overlay 中同时开启 Worker 和 API 路由模式：

```yaml
config:
  WEB_RECORDER_MODE: worker
webRecorder:
  enabled: true
  workerId: web-recorder-1
  display: ":99"
  maxSessions: 2
```

Chart 会创建独立的 `web-recorder` Deployment，并自动把 Pod 名追加到 `workerId`，保证每个副本使用唯一 Worker ID。API 根据 Redis 心跳和活动会话数选择 Worker，不要求 Ingress 粘性会话。Worker 心跳 key 过期后不会被选择承载新会话。

## 关键配置

- `WEB_RECORDER_WORKER_QUEUE_PREFIX`：API 与 Worker 必须一致，默认 `atp:web-recording:commands`。
- `WEB_RECORDER_WORKER_MAX_SESSIONS`：单个 Worker 的浏览器并发上限，超过后返回 409，不会排队创建不可控会话。
- `WEB_RECORDER_WORKER_HEARTBEAT_SECONDS` / `WEB_RECORDER_WORKER_TTL_SECONDS`：Worker 注册和失联检测周期。
- `WEB_RECORDER_COMMAND_TIMEOUT_SECONDS`：API 等待 Worker 启动、截图和停止响应的上限。
- `WEB_RECORDER_SESSION_TTL_SECONDS`：Redis 会话路由元数据 TTL；前端轮询、截图和停止操作会刷新 TTL。
- `WEB_RECORDER_DISPLAY`：Linux/Xvfb 的 display。没有可用 display 时启动会明确失败并释放浏览器资源。

API 仍负责登录态、项目编辑权限和录制元素资产持久化；Worker 只处理 Playwright 浏览器命令。启动参数、会话快照和步骤不包含密码输入值，密码输入仍按敏感值处理。录制导航和子资源继续使用共享网络守卫，阻止本机、私网、链路本地和保留地址请求。

当多个 API 副本同时创建会话时，API 先按心跳中的活动会话数选择候选 Worker；如果候选 Worker 在最终容量检查中明确返回 `busy` 或 `not_ready`，API 会切换到下一个可用 Worker。超时或未知错误不会盲目重试，避免同一个录制命令已经被接受但响应丢失时产生重复浏览器会话。

## 故障排查

1. API 返回“没有可用的 Web 录制 Worker”：检查 Redis 连通性、`WEB_RECORDER_MODE`、队列前缀和 Worker 心跳 key。
2. API 返回“Worker 响应超时”：检查 Worker 日志、Xvfb display、Chromium 启动依赖和 `WEB_RECORDER_COMMAND_TIMEOUT_SECONDS`。
3. 录制开始后页面不动：确认 API 与 Worker 使用同一个 Redis；Helm 部署会自动生成唯一的 `WEB_RECORDER_WORKER_ID`，非 Helm 部署仍需自行保证唯一。
4. 录制结束但资产没有写入：检查 API 数据库迁移和项目编辑权限；Worker 不直接写资产，资产由 API 在停止会话后事务化保存。

真实 Linux 多副本、Xvfb、Firefox/WebKit 和跨副本 E2E 仍需在发布环境验收；Windows `local` 模式的健康检查不能替代该验收。
