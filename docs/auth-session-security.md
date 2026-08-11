# 浏览器会话与认证边界

## 浏览器登录

前端登录成功后，后端通过 `atp_access_token` 和 `atp_refresh_token` 两个
`HttpOnly` Cookie 建立会话，不再把 JWT 写入 `localStorage`，也不在 WebSocket
URL 查询参数中携带 access token。浏览器刷新页面时由 `/api/v1/auth/me` 恢复会话。

Cookie 行为由以下配置控制：

- `APP_AUTH_COOKIE_SECURE`：公网 HTTPS 必须设为 `true`；本机 HTTP 开发默认 `false`。
- `APP_AUTH_COOKIE_SAMESITE`：同源部署使用 `lax`；只有明确的跨站部署场景才调整为
  `none`，并同时开启 `APP_AUTH_COOKIE_SECURE`。

前端 Axios 使用 `withCredentials` 和 `X-Requested-With: XMLHttpRequest`。后者用于
满足后端 CSRF 中间件的状态变更请求检查。若前后端跨域，必须把前端完整 origin 加入
`APP_CORS_ORIGINS`，不能使用 `*`。

## API 客户端

Bearer `Authorization` 仍然被后端支持，便于 CLI、CI/CD 和外部 API 客户端调用。浏览器
不应自行读取或持久化该类令牌。第一方浏览器请求带有 `X-Requested-With: XMLHttpRequest` 时，
`/auth/login`、`/auth/refresh` 只返回认证状态，令牌通过 HttpOnly Cookie 下发；未携带该请求头的
API 客户端会继续收到 `access_token`/`refresh_token` JSON 响应，同时也会设置 Cookie，便于逐步迁移。
API 客户端应使用受控的服务端凭据管理层保存 Bearer 令牌，而不是把令牌写入日志、URL 或构建产物。

## WebSocket

同源浏览器 WebSocket 会自动携带 access Cookie，服务端优先读取 Cookie。为兼容旧的非浏览器
集成，服务端暂时保留 `?token=` 查询参数回退；新客户端禁止使用该方式，因为 URL 可能进入
浏览器历史、反向代理访问日志和监控链路。

## 套件队列边界

纯 Android/iOS 套件会进入对应专用队列。混合套件进入 `default` 队列，默认 Worker 只负责
编排；其中的 Android/iOS 子用例会单独投递到 `android`/`ios` 队列并等待结果。请确保默认
Worker 与对应专用 Worker 都在线，并在 `CELERY_QUEUES` 中监听正确队列；子任务等待上限由
`SUITE_CHILD_TASK_TIMEOUT_SECONDS` 控制。
