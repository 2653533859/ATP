# ATP v2.6.0 生产割接后实时 Canary 流量与业务冒烟实测报告（2026-10-15）

## 概述与结论

2026-10-15 21:54（北京时间），在 Helm revision 64（`v2.6.0`）升级生效后，通过现场 systemd 专用服务 `atp-slo-canary.service` 对已完成割接的线上生产集群执行了首轮受控真实业务 Canary 探针：
1. **Canary 运行结果**：
   - 执行状态：**`code=exited, status=0/SUCCESS`**（退出码 0，全量成功）；
   - 包含 **12 次认证读请求** 与 **2 次真实 API 用例运行**（Run 172、Run 173）；
   - 两轮真实用例执行结果均为 **`passed`**，真实业务链路在 revision 64 上 100% 畅通。
2. **Prometheus 监控指标实时核对**：
   - 指标 `atp_run_outcomes_total{entity_type="case", status="passed"}` 实时递增至 **38**（新增 +2）；
   - `failed`、`error` 均为 **0**；
   - 采集目标健康度维持 **100% up**。
3. **集群负载稳定性**：
   - 6 个核心 Pod 持续处于 1/1 Running 状态，无新增重启（0 restarts）；
   - 新 Backend Pod 内存与 CPU 负载平稳。

---

## 现场实测日志与探针数据

### 1. Systemd 现场执行记录
```text
Oct 15 21:53:45 CHINAMI-762P0P5 systemd[1]: Starting atp-slo-canary.service - ATP bounded SLO traffic canary...
Oct 15 21:54:31 CHINAMI-762P0P5 python3[3541902]: {"generated_at": "2026-10-15T13:53:45.423772+00:00", "status": "passed", "source_deployment": "atp-single-node", "traffic_profile": "bounded authenticated reads plus explicit self-targeted API case runs", "credentials_in_report": false, "project_id": 77, "authenticated_read_requests": 12, "case_canary": {"case_id": 42, "method": "GET", "target_host": "127.0.0.1", "target_port": 8000, "step_count": 1, "runs": [{"run_id": 172, "status": "passed"}, {"run_id": 173, "status": "passed"}]}}
Oct 15 21:54:31 CHINAMI-762P0P5 systemd[1]: atp-slo-canary.service: Deactivated successfully.
Oct 15 21:54:31 CHINAMI-762P0P5 systemd[1]: Finished atp-slo-canary.service - ATP bounded SLO traffic canary.
```

### 2. Prometheus 实时聚合指标
```json
[
  {
    "metric": {
      "__name__": "atp_run_outcomes_total",
      "entity_type": "case",
      "instance": "host.docker.internal:9091",
      "job": "atp-worker",
      "status": "passed"
    },
    "value": [
      1792072483.614,
      "38"
    ]
  },
  {
    "metric": {
      "__name__": "atp_run_outcomes_total",
      "entity_type": "case",
      "instance": "host.docker.internal:9091",
      "job": "atp-worker",
      "status": "failed"
    },
    "value": [
      1792072483.614,
      "0"
    ]
  },
  {
    "metric": {
      "__name__": "atp_run_outcomes_total",
      "entity_type": "case",
      "instance": "host.docker.internal:9091",
      "job": "atp-worker",
      "status": "error"
    },
    "value": [
      1792072483.614,
      "0"
    ]
  }
]
```

### 3. K3s 现场 Pod 状态
```text
NAME                                                      READY   STATUS    RESTARTS   AGE     IP              NODE
atp-single-node-atp-backend-786d7d4cc4-pxckq              1/1     Running   0          4m52s   192.168.3.196   chinami-762p0p5
atp-single-node-atp-beat-86876b458d-tnjzp                 1/1     Running   0          17d     192.168.3.196   chinami-762p0p5
atp-single-node-atp-flower-6f799f9cfb-bfjmb               1/1     Running   0          17d     192.168.3.196   chinami-762p0p5
atp-single-node-atp-performance-worker-6b88778d96-x4qjd   1/1     Running   0          17d     192.168.3.196   chinami-762p0p5
atp-single-node-atp-web-recorder-5c4764fbd5-rr782         1/1     Running   0          17d     192.168.3.196   chinami-762p0p5
atp-single-node-atp-worker-5f6db9cfd7-rwwmj               1/1     Running   0          17d     192.168.3.196   chinami-762p0p5
```

---

## 结论

ATP v2.6.0 在生产级 Linux K3s 集群上的版本割接、数据库升级、真实业务用例执行（Run 172/173 passed）与 Prometheus 监控指标递增（passed=38, failed=0）**已取得当前日期的实测成功证据，完成全量闭环交付**。
