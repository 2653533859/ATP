# N5.1 Linux 现场基线与发布范围核实（2026-10-15）

## 概述与结论

2026-10-15 通过 SSH（`root@192.168.3.196:2222`）成功接入受控 Linux 现场主机 `CHINAMI-762P0P5`，完成现场环境基线、K3s 集群、容器、数据库迁移及观测指标的完整核验，为后续 N5.2 SLO 观察与 N5.3 线上升级提供带日期的真实环境证据。

---

## 现场实测基线数据

### 1. 操作系统与 Kubernetes 集群
- **内核与主机**：`Linux CHINAMI-762P0P5 6.18.33.2-microsoft-standard-WSL2 x86_64`
- **K3s 节点状态**：`chinami-762p0p5`，状态 **Ready**，运行时间 41 天，版本 `v1.36.3+k3s1`

### 2. Helm Release 与 Pod 状态
- **Release**：`atp-single-node`（命名空间 `atp-single-node`），当前处于 **revision 62**（状态 `deployed`，发布时间 2026-09-28 17:10:26 CST）
- **Pod 运行状态**（已持续稳定运行 17 天，**全部 0 重启**）：
  - `atp-single-node-atp-backend-f8675c6df-w2wjp`：1/1 Running, 0 restarts
  - `atp-single-node-atp-beat-86876b458d-tnjzp`：1/1 Running, 0 restarts
  - `atp-single-node-atp-flower-6f799f9cfb-bfjmb`：1/1 Running, 0 restarts
  - `atp-single-node-atp-performance-worker-6b88778d96-x4qjd`：1/1 Running, 0 restarts
  - `atp-single-node-atp-web-recorder-5c4764fbd5-rr782`：1/1 Running, 0 restarts
  - `atp-single-node-atp-worker-5f6db9cfd7-rwwmj`：1/1 Running, 0 restarts

### 3. 数据层与数据库迁移状态
- **PostgreSQL 容器**：`atp-q19-acceptance-20260824-postgres-1`（端口 `25432`，库名 `atp_acceptance`）
- **当前线上迁移版本**：`20260914_0074`
- **仓库最新迁移头**：`20261008_0079 (head)`
- **待执行迁移链路**：`0075`（Hermes持久命令）、`0076`（套件资源身份）、`0077`（套件同事务投递）、`0078`（首次接受凭据与租约）、`0079`（计划UUID与协作取消）

### 4. 观测系统（Prometheus & Flower）
- **Prometheus**：监听 `http://127.0.0.1:39090`，状态 `Prometheus Server is Ready.`
- **采集目标健康度**：**5/5 targets up**（`atp-backend`、`atp-flower`、`atp-performance-worker`、`atp-worker`、`prometheus` 均在线）
- **Flower 状态**：监听 `http://127.0.0.1:5555/metrics` 正常响应，GC 未回收对象为 0
- **Celery Beat**：定时任务（`check-cron-plans`, `check-performance-schedules`, `scan-adb-devices` 等）持续健康调度中

### 5. API 连通性与兼容性
- `GET http://127.0.0.1:8000/health` 返回 `{"status":"ok"}`
- `GET http://127.0.0.1:8000/api/v1/runtime` 返回 `404 Not Found`（证明线上版本为 2026-09-28 发布版本，严格符合 N3.4 中对旧版服务器无 runtime 接口时的 legacy fallback 预期）

---

## 结论与下一步

现场连接稳定，基线各项指标完全健康（6 Pod 0 重启、5/5 监控目标在线、PostgreSQL 与 MinIO 正常）。
- **N5.1 现场基线核验正式闭环**；
- 下一步可推进 **N5.2 长期 SLO 趋势核对** 与 **N5.3 候选镜像构建发布升级（从 0074 升级至 0079）**。
