# P2.1 AutoDroid 远程反向隧道 Agent 注册与设备池治理验收（2026-10-15）

## 概述与结论

P2.1（AutoDroid 远程反向隧道 Agent 注册与心跳）已完成架构加固、设备池自动同步与自动化回归验证：
1. **反向隧道 Agent 会话生命周期与心跳机制 (`backend/app/device_agents/tunnel_hub.py`)**：
   - 跨局域网 B 机上的 Android 设备通过轻量脚本 `scripts/device_agent.py`，经由反向 WebSocket (`/ws/device-agent`) 建立 TCP 隧道连接；
   - 支持动态端口分配（`28100-28199`）与设备 USB 序列号持久化绑定（`RemoteAgentDevice` 表）；
   - 心跳维持：Agent 每 20 秒发送一次 `ping`，服务端自动维护 `last_seen_at` 时间戳；超限自动触发会话优雅释放。
2. **中心设备池（`devices` 表）动态同步与状态联动**：
   - **自动入池**：在 `_persist_device_mappings` 中，当 Agent 上报新物理设备时，自动将映射的隧道端点 `127.0.0.1:<port>` 自动同步写入 ATP 核心 `devices` 表，设备状态立即标记为 `online`，使其立即可见于设备列表、APP 自动化工作台与并发测试矩阵；
   - **离线安全标记**：在 `_persist_agent_offline` 与服务启动 `startup_reset` 中，自动将失联或退出的 Agent 旗下设备在 `devices` 表中置为 `offline`；
   - **删除级联清理**：在 `delete_device_agent` 中，彻底清理离线 Agent、端口映射及关联的中央 `devices` 记录，释放端口资源。
3. **安全与管理 REST API (`backend/app/api/v1/device_agents.py`)**：
   - `GET /api/v1/device-agents/`：查询接入点列表及实时下属设备在线状态；
   - `GET /api/v1/device-agents/agent-script`：免登录限制/一键下载 `device_agent.py` 标准脚本；
   - `POST /api/v1/device-agents/{id}/link-probe`：主动探测 B→A 真实吞吐速率（bps）；
   - `DELETE /api/v1/device-agents/{id}`：离线接入点安全删除与端口回收（在线接入点返回 400 保护）。

---

## 质量门禁与验证

1. **专项自动化测试**：
   - `backend/tests/api/test_device_agents_api.py`：**7 passed in 0.81s**（覆盖接入点列表、脚本下载、带宽探测、在线删除保护、WS Token 鉴权、设备自动入池、离线状态联动）；
   - `scripts/pytest-standalone-sweep.py`：**1 passed, 0 failed standalone**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 190 source files**。
