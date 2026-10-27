# 云端 Web 入口（2026-10-27）

云端 ATP Web 页面现部署在 `http://192.168.3.196:8080/`。该地址绑定服务器的局域网 IP，供同一网络或私有网络中的浏览器访问。页面由独立 Docker Compose 服务 `atp-cloud-web` 提供，`/api/` 和 `/ws/` 经 Nginx 转发到同机 K3s Backend `:8000`。Windows 本地页面仍为 `http://127.0.0.1:5174/`，两者对应独立的本机与云端账号和数据。

部署文件位于 [`deploy/cloud-web/`](../deploy/cloud-web/)。构建前端时使用服务器模式：`VITE_ATP_LOCAL_MODE=false`，`VITE_BACKEND_ORIGIN` 为空；运行 `npm run build`（含 `vue-tsc`）后，将 `frontend/dist/`、`Dockerfile`、`nginx.conf`、`compose.yaml` 放在同一个部署目录。服务器当前目录为 `/opt/atp-cloud-web-20261027`，其私有 `.env` 设置 `ATP_WEB_BIND_IP=192.168.3.196` 和 `ATP_WEB_PORT=8080`。在该目录运行 `docker compose build`、`docker compose up -d`；回退可执行 `docker compose down`，不影响 K3s Backend。

上线检查：容器 `running healthy`、零重启；从 Windows 和 Linux 两端请求 `/` 返回 200、`/assets/` 构建资源返回 200、`/api/v1/runtime` 返回 200 且模式为 `server`、未登录的 `/api/v1/auth/me` 返回 401、前端深链接 `/projects` 返回 `index.html`。当前镜像为 `registry.local/atp/frontend:v2.7.1-cloud-web-20261027`。浏览器自动化验收受本机 Chrome CDP 未启动所限，未声称完成登录后的 UI 流程。

当前入口仅提供局域网 HTTP，尚未配置受信任的 HTTPS 证书或公网域名。要供公网或不可信网络访问，先配置 HTTPS 反向代理并验证登录 Cookie 与 WebSocket；不要把这个 HTTP 端口直接映射到公网。
