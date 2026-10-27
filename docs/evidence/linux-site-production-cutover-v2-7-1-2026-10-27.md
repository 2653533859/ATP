# ATP v2.7.1 Linux 现场生产部署与版本割接上线报告（2026-10-27）

## 概述与结论

2026-10-27 08:44（北京时间），在远程受控 Linux 生产主机（`CHINAMI-762P0P5:2222`，`192.168.3.196`）上正式完成了 **ATP v2.7.1**（涵盖请求指纹追溯、云端结果汇总中心 D3、跨端自动同步 D4 及反向代理网关 D5）的生产构建、数据库迁移升级、K3s 生产发布割接与现场 Canary 业务冒烟：

1. **源码基线与镜像构建**：
   * 生产镜像构建完成并导入 K3s containerd：
     `registry.local/atp/backend:v2.7.1-cloudsync`（Digest: `sha256:50c136d9964c7e4a958d5d60a3b61c985e3d73d16f3e4d1d24f14c0b0e6b2d7b`）；
2. **PostgreSQL 线上数据库迁移成功**：
   * 前置安全备份：`/opt/atp_acceptance_backup_20261026_d3.sql`（622 KB）；
   * 真实数据库 `atp_acceptance` 经 `atp_migrator` 成功由 `20261015_0081` 升级至最新头 `20261026_0082`（新增 `cloud_run_summaries` 跨端结果汇总表）；
   * 读写权限与 Sequence 序列权限已成功授予 `atp_runtime`；
3. **K3s 生产发布割接成功**：
   * 容器组 `atp-single-node-atp-backend` 平滑热更上线；
   * 新 Pod `atp-single-node-atp-backend-868544f7b7-4w8ml` 处于 `1/1 Running` 0 重启就绪状态；
   * 全集群 6 个核心 Pod（backend, beat, flower, performance-worker, web-recorder, worker）持续处于 `1/1 Running` 状态；
4. **现场 Canary 业务探针与实测全绿**：
   * `GET http://127.0.0.1:8000/health`：**HTTP 200 OK**（`{"status":"ok"}`）；
   * `GET http://127.0.0.1:8000/api/v1/runtime`：**HTTP 200 OK**（返回 `mode="server"`, `database="postgresql"`, `storage="minio"`, `execution="celery"`）；
   * **现场 Canary 业务探针**：`atp-slo-canary.service` 自动执行通过，12 次认证读请求 100% 成功，完成 2 次真实 API 用例执行（Run 200、Run 201 均为 `passed`）；
   * **云端跨端汇总大盘**：`GET http://127.0.0.1:8000/api/v1/cloud-sync/stats` 稳定返回汇总统计数据，包含已连接 Windows 客户端（`win-3498f96ead4149ef94a4a084`）上报的真机及 API 运行记录。

---

## 现场割接实测数据

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
NAME                                                      READY   STATUS    RESTARTS   AGE
atp-single-node-atp-backend-868544f7b7-4w8ml              1/1     Running   0          6m38s
atp-single-node-atp-beat-86876b458d-tnjzp                 1/1     Running   0          28d
atp-single-node-atp-flower-6f799f9cfb-bfjmb               1/1     Running   0          28d
atp-single-node-atp-performance-worker-6b88778d96-x4qjd   1/1     Running   0          28d
atp-single-node-atp-web-recorder-5c4764fbd5-rr782         1/1     Running   0          28d
atp-single-node-atp-worker-5f6db9cfd7-rwwmj               1/1     Running   0          28d
```

### 3. 数据库 Alembic 当前版本
```text
  version_num
---------------
 20261026_0082
(1 row)
```

### 4. Systemd 现场 Canary 执行记录
```text
Oct 27 08:43:19 CHINAMI-762P0P5 systemd[1]: Starting atp-slo-canary.service - ATP bounded SLO traffic canary...
Oct 27 08:44:05 CHINAMI-762P0P5 python3[3467239]: {"generated_at": "2026-10-27T00:43:19.360385+00:00", "status": "passed", "source_deployment": "atp-single-node", "traffic_profile": "bounded authenticated reads plus explicit self-targeted API case runs", "credentials_in_report": false, "project_id": 77, "authenticated_read_requests": 12, "case_canary": {"case_id": 42, "method": "GET", "target_host": "127.0.0.1", "target_port": 8000, "step_count": 1, "runs": [{"run_id": 200, "status": "passed"}, {"run_id": 201, "status": "passed"}]}}
Oct 27 08:44:05 CHINAMI-762P0P5 systemd[1]: atp-slo-canary.service: Deactivated successfully.
Oct 27 08:44:05 CHINAMI-762P0P5 systemd[1]: Finished atp-slo-canary.service - ATP bounded SLO traffic canary.
```
