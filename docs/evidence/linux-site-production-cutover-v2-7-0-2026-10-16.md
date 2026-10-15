# ATP v2.7.0 Linux 现场生产部署与版本割接上线报告（2026-10-16）

## 概述与结论

2026-10-16 00:00（北京时间），在远程受控 Linux 生产主机（`CHINAMI-762P0P5:2222`，`192.168.3.196`）上正式完成了 **ATP v2.7.0** 的生产构建、数据库迁移升级、K3s 生产发布割接与现场 Canary 业务冒烟：
1. **源码基线与镜像构建**：
   - 生产镜像基于正式 Release `v2.7.0`（提交 `b54a8533`）构建：
     `registry.local/atp/backend:v2.7.0`（Image ID `f1e093f65d18`）；
   - 镜像已成功导入至 K3s containerd（Digest: `sha256:f1e093f65d1860620cda755c067a7ca39a0f2f7f346cc847cfd24c3d1538d4fb`）；
2. **PostgreSQL 线上数据库迁移成功**：
   - 前置安全备份：`/opt/atp_acceptance_backup_20261015_v270.sql`（592 KB）；
   - 真实数据库 `atp_acceptance` 经 `atp_migrator` 成功执行升级（`0080 -> 0081`，新增 `api_keys` 租户与权限管控表）；
   - 线上版本正式推进至最新头：`20261015_0081 (head)`；
3. **Helm 生产发布割接成功**：
   - 执行 `helm upgrade atp-single-node ... --set-string image.backend.tag=v2.7.0`，成功推进至 **Helm revision 65**（状态 `deployed`）；
   - 新 Pod `atp-single-node-atp-backend-7f77678bc-7rfh4` 零重启平滑启动并就绪（1/1 Running）；
   - 全集群 6 个核心 Pod（backend, beat, flower, performance-worker, web-recorder, worker）全部处于 1/1 Running 状态；
4. **线上功能与 Canary 实测数据全绿**：
   - `GET http://127.0.0.1:8000/health`：**HTTP 200 OK**；
   - `GET http://127.0.0.1:8000/api/v1/runtime`：**HTTP 200 OK**（返回 `mode="server"`, `database="postgresql"`, `storage="minio"`, `execution="celery"`）；
   - **现场 Canary 业务探针**：`atp-slo-canary.service` 自动执行通过，12 次认证读请求 100% 成功，完成 2 次真实 API 用例执行（Run 174、Run 175，均为 `passed`）；
   - **Prometheus 监控**：指标 `atp_run_outcomes_total{entity_type="case", status="passed"}` 实时递增至 **40**（新增 +2），`failed=0`，`error=0`。

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

### 2. K3s 集群 Pod 列表
```text
NAME                                                      READY   STATUS    RESTARTS   AGE     IP              NODE              NOMINATED NODE   READINESS GATES
atp-single-node-atp-backend-7f77678bc-7rfh4               1/1     Running   0          2m10s   192.168.3.196   chinami-762p0p5   <none>           <none>
atp-single-node-atp-beat-86876b458d-tnjzp                 1/1     Running   0          17d     192.168.3.196   chinami-762p0p5   <none>           <none>
atp-single-node-atp-flower-6f799f9cfb-bfjmb               1/1     Running   0          17d     192.168.3.196   chinami-762p0p5   <none>           <none>
atp-single-node-atp-performance-worker-6b88778d96-x4qjd   1/1     Running   0          17d     192.168.3.196   chinami-762p0p5   <none>           <none>
atp-single-node-atp-web-recorder-5c4764fbd5-rr782         1/1     Running   0          17d     192.168.3.196   chinami-762p0p5   <none>           <none>
atp-single-node-atp-worker-5f6db9cfd7-rwwmj               1/1     Running   0          17d     192.168.3.196   chinami-762p0p5   <none>           <none>
```

### 3. 数据库 Alembic 当前版本
```text
  version_num
---------------
 20261015_0081
(1 row)
```

### 4. Helm Release 列表
```text
NAME           	NAMESPACE      	REVISION	UPDATED                                	STATUS  	CHART    	APP VERSION
atp-single-node	atp-single-node	65      	2026-10-15 23:58:43.226449427 +0800 CST	deployed	atp-0.1.0	1.0.0
```

### 5. Systemd 现场 Canary 执行记录
```text
Oct 15 23:59:47 CHINAMI-762P0P5 systemd[1]: Starting atp-slo-canary.service - ATP bounded SLO traffic canary...
Oct 16 00:00:33 CHINAMI-762P0P5 python3[3897959]: {"generated_at": "2026-10-15T15:59:47.293745+00:00", "status": "passed", "source_deployment": "atp-single-node", "traffic_profile": "bounded authenticated reads plus explicit self-targeted API case runs", "credentials_in_report": false, "project_id": 77, "authenticated_read_requests": 12, "case_canary": {"case_id": 42, "method": "GET", "target_host": "127.0.0.1", "target_port": 8000, "step_count": 1, "runs": [{"run_id": 174, "status": "passed"}, {"run_id": 175, "status": "passed"}]}}
Oct 16 00:00:33 CHINAMI-762P0P5 systemd[1]: atp-slo-canary.service: Deactivated successfully.
Oct 16 00:00:33 CHINAMI-762P0P5 systemd[1]: Finished atp-slo-canary.service - ATP bounded SLO traffic canary.
```
