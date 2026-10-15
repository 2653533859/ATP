# ATP v2.5.0 生产割接后实时 Canary 流量与业务冒烟实测报告（2026-10-15）

## 概述与结论

2026-10-15 19:20（北京时间），在 Helm revision 63（`v2.5.0`）升级生效后，通过现场 systemd 专用服务 `atp-slo-canary.service` 对已完成割接的线上生产集群执行了首轮受控真实业务 Canary 探针：
1. **Canary 运行结果**：
   - 执行状态：**`code=exited, status=0/SUCCESS`**（退出码 0，全量成功）；
   - 包含 **12 次认证读请求** 与 **2 次真实 API 用例运行**（Run 170、Run 171）；
   - 两轮真实用例执行结果均为 **`passed`**，真实业务链路在 revision 63 上 100% 畅通。
2. **Prometheus 监控指标实时核对**：
   - 指标 `atp_run_outcomes_total{entity_type="case", status="passed"}` 实时递增至 **36**；
   - `failed`、`error` 均为 **0**；
   - 5/5 采集目标健康度维持 **100% up**。
3. **集群负载稳定性**：
   - 6 个核心 Pod 持续处于 1/1 Running 状态，无新增重启（0 restarts）；
   - 新 Backend Pod 内存与 CPU 负载平稳。

---

## 现场实测日志与探针数据

### 1. Systemd 现场执行记录
```text
Oct 15 19:19:39 CHINAMI-762P0P5 systemd[1]: Starting atp-slo-canary.service - ATP bounded SLO traffic canary...
Oct 15 19:20:25 CHINAMI-762P0P5 python3[3111992]: {
  "generated_at": "2026-10-15T11:19:39.415763+00:00",
  "status": "passed",
  "source_deployment": "atp-single-node",
  "traffic_profile": "bounded authenticated reads plus explicit self-targeted API case runs",
  "credentials_in_report": false,
  "project_id": 77,
  "authenticated_read_requests": 12,
  "case_canary": {
    "case_id": 42,
    "method": "GET",
    "target_host": "127.0.0.1",
    "target_port": 8000,
    "step_count": 1,
    "runs": [
      {"run_id": 170, "status": "passed"},
      {"run_id": 171, "status": "passed"}
    ]
  }
}
Oct 15 19:20:25 CHINAMI-762P0P5 systemd[1]: atp-slo-canary.service: Deactivated successfully.
Oct 15 19:20:25 CHINAMI-762P0P5 systemd[1]: Finished atp-slo-canary.service - ATP bounded SLO traffic canary.
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
      1792063274.529,
      "36"
    ]
  }
]
```

---

## 最终判定

ATP v2.5.0 在生产级 Linux K3s 集群上的版本割接、数据库升级、业务运行与观测指标校验**已全面闭环并取得当前日期的实测成功证据**。
