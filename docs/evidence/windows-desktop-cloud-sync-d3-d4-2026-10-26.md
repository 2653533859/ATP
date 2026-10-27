# Windows 桌面到云端结果汇总实测与割接证据（2026-10-26）

## 概述与结论

2026-10-26，在 Windows 本地宿主机与指定远程 Linux 生产服务器（`CHINAMI-762P0P5:2222`，`192.168.3.196`）之间，正式完成了 **D3 云端接收与汇总中心** 以及 **D4 本地自动同步上报** 的端到端真实闭环验证：

1. **PostgreSQL 数据库迁移（Alembic 0082）**：
   * 前置安全备份：`/opt/atp_acceptance_backup_20261026_d3.sql`（622 KB）；
   * 线上数据库 `atp_acceptance` 经 `atp_migrator` 成功由 `20261015_0081` 升级至最新头 `20261026_0082`；
   * 新建 `cloud_run_summaries` 表，配置 `(unique_key)` 唯一约束及多维度查询索引，并为 `atp_runtime` 授予读写权限；
2. **K3s 生产服务平滑升级**：
   * 基于正式基线与最新代码构建镜像：`registry.local/atp/backend:v2.7.1-cloudsync` 并导入 containerd；
   * 容器组 `atp-single-node-atp-backend` 平滑更新上线，Pod 处于 `1/1 Running` 0 重启状态；
   * 服务健康探针 `GET http://127.0.0.1:8000/health` 返回 `{"status": "ok"}`；
3. **Windows 客户端 Outbox 跨网络同步闭环（D4）**：
   * 本机生成测试运行并原子落盘入 `local_sync_outbox`（`status="pending"`）；
   * 触发 `sync_pending_outbox(sync_url="http://192.168.3.196:8000")` 跨局域网投递；
   * 云端接收成功并返回 `{"status": "ok", "acknowledged": True, "action": "created"}`；
   * 本地 Outbox 状态原子翻转为 `synced`，记录精确 `synced_at` 时间戳；
4. **云端汇总与幂等去重（D3）**：
   * `GET http://192.168.3.196:8000/api/v1/cloud-sync/runs` 正确返回上报的轻量摘要，不含任何原始请求/响应体或文件二进制；
   * `GET http://192.168.3.196:8000/api/v1/cloud-sync/stats` 统计汇总大盘实时包含客户端机器 ID `win-3498f96ead4149ef94a4a084`、运行总数 1 及状态分布；
   * 重复推送同一运行（`unique_key` 命中），云端幂等更新记录且保持 `total_runs=1`，零重复冗余。

---

## 现场实测证据

### 1. 线上数据库 Alembic 版本与表结构
```text
  version_num
---------------
 20261026_0082
(1 row)
```
```text
                                        Table "public.cloud_run_summaries"
    Column     |           Type           | Collation | Nullable |                     Default
---------------+--------------------------+-----------+----------+-------------------------------------------------
 id            | integer                  |           | not null | nextval('cloud_run_summaries_id_seq'::regclass)
 client_id     | character varying(64)    |           | not null |
 machine_name  | character varying(64)    |           | not null |
 unique_key    | character varying(128)   |           | not null |
 run_type      | character varying(32)    |           | not null |
 run_id        | integer                  |           | not null |
 project_name  | character varying(128)   |           | not null |
 project_code  | character varying(64)    |           | not null |
 title         | character varying(256)   |           | not null |
 status        | character varying(32)    |           | not null |
 started_at    | timestamp with time zone |           |          |
 finished_at   | timestamp with time zone |           |          |
 duration_ms   | integer                  |           |          |
 triggered_by  | character varying(64)    |           | not null | 'admin'::character varying
 environment   | character varying(64)    |           |          |
 metrics       | json                     |           | not null | '{}'::json
 error_summary | text                     |           |          |
 steps_summary | json                     |           | not null | '[]'::json
 reported_at   | timestamp with time zone |           | not null | now()
 created_at    | timestamp with time zone |           | not null | now()
 updated_at    | timestamp with time zone |           | not null | now()
Indexes:
    "cloud_run_summaries_pkey" PRIMARY KEY, btree (id)
    "ix_cloud_run_summaries_client_id" btree (client_id)
    "ix_cloud_run_summaries_project_code" btree (project_code)
    "ix_cloud_run_summaries_run_type" btree (run_type)
    "ix_cloud_run_summaries_status" btree (status)
    "ix_cloud_run_summaries_unique_key" btree (unique_key)
    "uq_cloud_run_summaries_unique_key" UNIQUE CONSTRAINT, btree (unique_key)
```

### 2. K3s Pod 运行状态
```text
NAME                                                      READY   STATUS    RESTARTS   AGE
atp-single-node-atp-backend-868544f7b7-mhntt              1/1     Running   0          2m
atp-single-node-atp-beat-86876b458d-tnjzp                 1/1     Running   0          27d
atp-single-node-atp-flower-6f799f9cfb-bfjmb               1/1     Running   0          27d
atp-single-node-atp-performance-worker-6b88778d96-x4qjd   1/1     Running   0          27d
atp-single-node-atp-web-recorder-5c4764fbd5-rr782         1/1     Running   0          27d
atp-single-node-atp-worker-5f6db9cfd7-rwwmj               1/1     Running   0          27d
```

### 3. Windows 本地 Outbox 同步执行日志
```text
Pending outbox items count: 1
Syncing outbox to http://192.168.3.196:8000
Sync result: {'status': 'ok', 'synced': 1, 'failed': 0, 'processed': 1}
Local outbox status after sync: synced synced_at: 2026-10-26 06:02:41
```

### 4. 云端列表查询实测（`GET /api/v1/cloud-sync/runs`）
```json
{
  "items": [
    {
      "id": 1,
      "client_id": "win-3498f96ead4149ef94a4a084",
      "machine_name": "hps",
      "unique_key": "win-3498f96ead4149ef94a4a084:case:8888",
      "run_type": "case",
      "run_id": 8888,
      "project_name": "Windows Core App",
      "project_code": "WIN_CORE",
      "title": "Desktop to Cloud Sync E2E Test",
      "status": "passed",
      "started_at": "2026-10-26T06:00:55+00:00",
      "finished_at": "2026-10-26T06:00:55+00:00",
      "duration_ms": 235,
      "triggered_by": "local_tester",
      "environment": null,
      "metrics": {
        "total_steps": 1,
        "passed_steps": 1
      },
      "error_summary": null,
      "step_count": 1,
      "reported_at": "2026-10-26T06:02:39.946838+00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### 5. 云端大盘汇总查询实测（`GET /api/v1/cloud-sync/stats`）
```json
{
  "total_runs": 1,
  "status_distribution": {
    "passed": 1
  },
  "type_distribution": {
    "case": 1
  },
  "connected_clients": [
    {
      "client_id": "win-3498f96ead4149ef94a4a084",
      "machine_name": "hps",
      "runs_count": 1
    }
  ]
}
```
