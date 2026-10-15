# ATP v2.6.0 Linux 现场生产部署与版本割接上线报告（2026-10-15）

## 概述与结论

2026-10-15 21:50（北京时间），在远程受控 Linux 生产主机（`CHINAMI-762P0P5:2222`，`192.168.3.196`）上正式完成了 **ATP v2.6.0** 的生产构建、数据库迁移升级与 K3s 生产发布割接：
1. **源码基线与镜像构建**：
   - 生产镜像基于正式 Release `v2.6.0`（提交 `0e95b5bb`）构建：
     `registry.local/atp/backend:v2.6.0`（Image ID `4b01cb973436`）；
   - 镜像已成功导入至 K3s containerd（Digest: `sha256:4b01cb973436c6fbecdd2a1fac551b7c6363a18a0ca43f5bfc22def654c911eb`）；
2. **PostgreSQL 线上数据库迁移成功**：
   - 前置安全备份：`/opt/atp_acceptance_backup_20261015_v260.sql`（590 KB）；
   - 真实数据库 `atp_acceptance` 经 `atp_migrator` 成功执行升级（`0079 -> 0080`，拓展 `notifychannel` 原生枚举支持飞书渠道）；
   - 线上版本正式推进至最新头：`20261015_0080 (head)`；
3. **Helm 生产发布割接成功**：
   - 执行 `helm upgrade atp-single-node ... --set-string image.backend.tag=v2.6.0`，成功推进至 **Helm revision 64**（状态 `deployed`）；
   - 新 Pod `atp-single-node-atp-backend-786d7d4cc4-pxckq` 零重启平滑启动并就绪（1/1 Running）；
   - 全集群 6 个核心 Pod（backend, beat, flower, performance-worker, web-recorder, worker）全部处于 1/1 Running 状态；
4. **线上功能与安全校验全绿**：
   - `GET http://127.0.0.1:8000/health`：**HTTP 200 OK**；
   - `GET http://127.0.0.1:8000/api/v1/runtime`：**HTTP 200 OK**（返回 `mode="server"`, `database="postgresql"`, `storage="minio"`, `execution="celery"`）；
   - **跨模式拦截探测**：携带 `X-ATP-Client-Mode: local` 访问受保护接口即时熔断返回 **HTTP 409 Conflict**；
   - **Prometheus 监控**：Prometheus Server 正常就绪。

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
date: Thu, 15 Oct 2026 13:51:02 GMT
server: uvicorn
content-length: 119
content-type: application/json

{"detail":"客户端模式 (local) 与当前后端运行模式 (server) 不一致，请打开正确的访问入口。"}
```

### 3. K3s 集群 Pod 列表
```text
NAME                                                      READY   STATUS    RESTARTS   AGE   IP              NODE              NOMINATED NODE   READINESS GATES
atp-single-node-atp-backend-786d7d4cc4-pxckq              1/1     Running   0          22s   192.168.3.196   chinami-762p0p5   <none>           <none>
atp-single-node-atp-beat-86876b458d-tnjzp                 1/1     Running   0          17d   192.168.3.196   chinami-762p0p5   <none>           <none>
atp-single-node-atp-flower-6f799f9cfb-bfjmb               1/1     Running   0          17d   192.168.3.196   chinami-762p0p5   <none>           <none>
atp-single-node-atp-performance-worker-6b88778d96-x4qjd   1/1     Running   0          17d   192.168.3.196   chinami-762p0p5   <none>           <none>
atp-single-node-atp-web-recorder-5c4764fbd5-rr782         1/1     Running   0          17d   192.168.3.196   chinami-762p0p5   <none>           <none>
atp-single-node-atp-worker-5f6db9cfd7-rwwmj               1/1     Running   0          17d   192.168.3.196   chinami-762p0p5   <none>           <none>
```

### 4. 数据库 Alembic 当前版本
```text
  version_num
---------------
 20261015_0080
(1 row)
```

### 5. Helm Release 列表
```text
NAME           	NAMESPACE      	REVISION	UPDATED                                	STATUS  	CHART    	APP VERSION
atp-single-node	atp-single-node	64      	2026-10-15 21:49:54.226449427 +0800 CST	deployed	atp-0.1.0	1.0.0
```
