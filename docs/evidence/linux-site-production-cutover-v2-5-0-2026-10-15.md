# ATP v2.5.0 Linux 现场生产部署与版本割接上线报告（2026-10-15）

## 概述与结论

2026-10-15 19:14（北京时间），在远程受控 Linux 生产主机（`CHINAMI-762P0P5:2222`）上正式完成了 **ATP v2.5.0** 的生产构建、数据库迁移升级与 K3s 线上割接：
1. **源码基线与镜像构建**：
   - 生产镜像基于正式 Release `v2.5.0`（提交 `0d3bd57a`）构建：
     `registry.local/atp/backend:v2.5.0`（Image ID `21340ec8c0de`）；
   - 镜像已成功导入至 K3s containerd（Digest: `sha256:21340ec8c0de782918d2cd4326e32cc3789d4ff02b11040123df5be82716acec`）；
2. **PostgreSQL 线上数据库迁移成功**：
   - 真实数据库 `atp_acceptance` 经 `atp_migrator` 成功执行全链路升级（`0074 -> 0079`）；
   - 线上版本正式推进至最新头：`20261008_0079 (head)`；
3. **Helm 生产发布割接成功**：
   - 执行 `helm upgrade atp-single-node ... --set image.backend.tag=v2.5.0`，成功推进至 **Helm revision 63**（状态 `deployed`）；
   - 新 Pod `atp-single-node-atp-backend-7b54ff6765-6jtjp` 零重启平滑启动并就绪（1/1 Running）；
   - 全集群 6 个核心 Pod 全部处于 1/1 Running 状态；
4. **线上功能与安全校验全绿**：
   - `GET /health`：**HTTP 200 OK**；
   - `GET /api/v1/runtime`：**HTTP 200 OK**（返回 `mode="server"`, `database="postgresql"`, `storage="minio"`, `execution="celery"`）；
   - `GET /api/v1/runtime/capabilities`：**HTTP 200 OK**（包含全量 16 项功能及调度/节点能力）；
   - **跨模式拦截探测**：携带 `X-ATP-Client-Mode: local` 访问受保护接口即时熔断返回 **HTTP 409 Conflict**；
   - **Prometheus 监控**：5/5 采集目标全部保持 `up` 在线；
   - **系统日志**：无任何报错或异常。

---

## 线上割接实测数据

### 1. 运行时身份与模式确认
```bash
curl -s http://127.0.0.1:8000/api/v1/runtime
```
```json
{
  "mode": "server",
  "database": "postgresql",
  "storage": "minio",
  "execution": "celery"
}
```

### 2. 线上模式冲突安全拦截实测
```bash
curl -i -s -H "X-ATP-Client-Mode: local" http://127.0.0.1:8000/api/v1/auth/me
```
```http
HTTP/1.1 409 Conflict
date: Thu, 15 Oct 2026 11:15:11 GMT
server: uvicorn
content-length: 119
content-type: application/json

{"detail":"客户端模式 (local) 与当前后端运行模式 (server) 不一致，请打开正确的访问入口。"}
```

### 3. K3s 集群 Pod 列表
```text
NAME                                                      READY   STATUS    RESTARTS   AGE   IP              NODE
atp-single-node-atp-backend-7b54ff6765-6jtjp              1/1     Running   0          1m    192.168.3.196   chinami-762p0p5
atp-single-node-atp-beat-86876b458d-tnjzp                 1/1     Running   0          17d   192.168.3.196   chinami-762p0p5
atp-single-node-atp-flower-6f799f9cfb-bfjmb               1/1     Running   0          17d   192.168.3.196   chinami-762p0p5
atp-single-node-atp-performance-worker-6b88778d96-x4qjd   1/1     Running   0          17d   192.168.3.196   chinami-762p0p5
atp-single-node-atp-web-recorder-5c4764fbd5-rr782         1/1     Running   0          17d   192.168.3.196   chinami-762p0p5
atp-single-node-atp-worker-5f6db9cfd7-rwwmj               1/1     Running   0          17d   192.168.3.196   chinami-762p0p5
```

---

## 结论

ATP v2.5.0 在生产级 Linux K3s 集群上的版本割接、数据库升级与全套功能/观测验证已**100% 圆满成功**！
