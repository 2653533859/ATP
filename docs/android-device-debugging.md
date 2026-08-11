# Android 真机联调说明

如果 Android 真机连接在 Windows、需要由 Windows 本地 ADB 执行并回传结果，请先阅读 [`android-windows-worker.md`](android-windows-worker.md)。本文下面的 Docker/ADB Server 方案适用于设备与 Worker 位于同一网络的部署。

本文档说明 ATP 在 Docker Worker / Windows 本地环境下，如何通过 ADB over TCP 连接宿主机 Android 真机，并完成最小可复现联调。

## 目标

完成以下闭环：

1. 宿主机能识别 Android 真机
2. ATP 能扫描到设备
3. Android 用例能选择该设备执行
4. Worker 能在执行前明确判断设备是否可达
5. 常见失败能快速定位是授权、离线、网络还是 adb 问题

---

## 一、推荐连接方式

推荐使用 **ADB over TCP**，而不是把 USB 直通交给容器。

原因：

- Docker 容器里做 USB 直通不稳定，跨平台差异大
- ADB over TCP 更容易复现
- 更适合 Worker 在容器内执行

推荐流程：

```bash
adb devices
adb tcpip 5555
adb connect <device-ip>:5555
adb devices
```

成功后设备 serial 通常会变成：

```text
192.168.x.x:5555
```

---

## 二、宿主机准备

### 1. 打开手机开发者选项

确认以下项已开启：

- USB 调试
- 保持唤醒（可选，便于联调）
- 无线调试（如果系统支持）

### 2. 首次 USB 授权

第一次建议先通过 USB 完成授权：

```bash
adb devices
```

如果设备显示 `unauthorized`：

- 查看手机弹窗
- 点击允许 USB 调试
- 再次执行 `adb devices`

### 3. 切换到 TCP 模式

```bash
adb tcpip 5555
adb connect <device-ip>:5555
adb devices
```

确认设备出现在列表中，状态为 `device`。

---

## 三、Docker Worker 联调建议

`docker-compose.yml` 中 worker 已安装 `adb`，并保留了 host 网络模式说明。

推荐顺序（容器直连模式）：

1. 宿主机通过 USB 授权并执行 `adb tcpip 5555`
2. Worker 容器独立执行 `adb connect <device-ip>:5555`
3. 通过 ATP 的设备扫描接口刷新设备列表

宿主机的 ADB 连接不会自动被容器复用。需要复用 USB/TCP 设备列表时，显式配置 `ADB_SERVER_SOCKET=tcp:host.docker.internal:5037`，并确保宿主 ADB server 仅对 Docker 网关安全可达。完整演练见 `docs/android-worker-connectivity-rehearsal.md`。

---

## 四、平台内验证步骤

### 1. 手动扫描设备

调用：

```text
POST /api/v1/devices/scan
```

或在前端设备页执行扫描。

### 2. 检查设备状态

期望结果：

- 设备出现在列表中
- 状态为 `online`
- serial 为 TCP 地址，如 `192.168.x.x:5555`

### 3. 创建 Android 用例

确保用例配置中已选择：

- `device_serial`
- 可选的 `apk_object_name`
- 脚本文件 `script_path`

### 4. 执行 Android 用例

当前执行器在真正运行前会先做设备可达性检查：

- `device`：继续执行
- `offline`：直接失败并给出提示
- `unauthorized`：直接失败并提示重新授权
- `adb` 不存在：直接提示环境问题

---

## 五、常见问题排查

### 1. 设备扫描不到

先在宿主机检查：

```bash
adb devices -l
```

如果宿主机都看不到，先解决宿主机 adb 问题，再看 ATP。

### 2. 显示 unauthorized

重新插 USB 或重新授权：

```bash
adb kill-server
adb start-server
adb devices
```

然后在手机上确认授权弹窗。

### 3. 显示 offline

通常是 TCP 连接断开或设备休眠：

```bash
adb disconnect <device-ip>:5555
adb connect <device-ip>:5555
adb devices
```

### 4. Worker 报设备不可达

先检查：

- 宿主机是否已 `adb connect`
- 设备 IP 是否变化
- Docker 容器网络是否可访问该 IP
- 是否需要 host 网络模式

### 5. 截图 / 镜像失败

说明 adb 链路不稳定，优先先保证：

- `adb -s <serial> get-state` 返回 `device`
- `adb -s <serial> exec-out screencap -p` 能返回图片数据

---

## 六、当前结论

目前 ATP Android 方向已具备：

- 设备扫描
- Android pytest 执行器
- APK 安装
- 屏幕截图 / MJPEG 镜像
- 执行前设备可达性校验
- 面向 ADB over TCP 的联调说明

当前最推荐的落地方式是：

**优先让 Worker 直接连接设备 IP；需要复用宿主设备列表时，显式使用 ADB_SERVER_SOCKET。**

---

## 七、宿主网络与 Docker 环境差异

### 1. Docker Desktop vs Linux 宿主

| 平台 | host 网络支持 | 推荐方案 |
|------|---------------|---------|
| Linux | 完整但会改变 Compose DNS/端口语义 | 优先设备 IP 直连；共享 server 需 host-gateway + 安全监听 |
| Docker Desktop (Win/Mac) | 受限 | 设备 IP 直连，或 `ADB_SERVER_SOCKET=tcp:host.docker.internal:5037` |

Docker Desktop 存在 VM 网络层，设备 IP 是否可达取决于 Wi-Fi/VPN/防火墙。`host.docker.internal:5037` 是宿主 ADB server；设备 adbd 则使用真实 `<device-ip>:5555`。当前 Compose 的宿主 5555 端口属于 Flower，不能当作 ADB 地址。

### 2. 设备 IP 漂移

设备在不同 Wi-Fi 网络或重启后 IP 可能变化。建议：

- 路由器侧为设备 DHCP 绑定，固定 IP
- 在 ATP 设备表中尽量记录"设备名 + 当前 IP" 双字段，便于运维识别

### 3. 端口防火墙

`adb tcpip 5555` 后，确认 5555 在防火墙放通：

```bash
# Linux
sudo ufw allow 5555/tcp
```

```powershell
# Windows
New-NetFirewallRule -DisplayName "ADB TCP" -Direction Inbound -LocalPort 5555 -Protocol TCP -Action Allow
```

### 4. 一键诊断脚本

复杂网络环境下，使用仓库自带的诊断脚本快速定位：

```bash
bash scripts/android-network-doctor.sh 192.168.1.100:5555
```

脚本顺序检查：adb 可执行 → 重启 adb server → connect → devices 列表 → shell 探活。每步输出 `[OK]/[FAIL]`，失败时打印针对性提示（重新 USB 授权 / 检查防火墙 / 切 host 网络等）。退出码 0 通过、1 任一失败。

### 5. 经验排查清单

| 现象 | 优先检查 |
|------|---------|
| 容器内 `adb connect` 一直 `cannot connect` | 防火墙、设备 IP 是否漂移、Docker Desktop 网络限制 |
| `device` 在列表但 `shell` 失败 | USB 线缆抖动、设备 USB 调试被关、TCP 链路超时 |
| 跨重启失联 | 设备没保持唤醒；建议执行时显式 `screen on` |
| 多设备 serial 串号 | 始终用 `adb -s <serial>` 指明目标设备 |

---

## 八、执行器自愈机制

为缓解真机网络抖动，ATP 在执行器内置了"重连 + 心跳 + 重试"自愈层
（`backend/app/services/adb_resilience.py`）。所有 Android 用例 / 移动专项执行器
（android / perf / stability / fluency）统一复用，无需用户介入。

### 1. 自动重连（execution-time reconnect）

执行开始前的可达性校验 `ensure_reachable(serial)` 行为：

1. `adb -s <serial> get-state`
2. 若返回 `offline` 且 serial 形如 `ip:port`：
   - `adb disconnect <serial>` + `adb connect <serial>`
   - 按 `ADB_RECONNECT_BACKOFF_MS` 退避（默认 200ms / 800ms / 2s）
3. 重复至成功或达到 `ADB_RECONNECT_MAX_ATTEMPTS`（默认 3 次）
4. 若返回 `unauthorized` 或 adb 不存在，立即终止，不重试

### 2. 心跳监控（in-flight heartbeat）

长任务（性能采样 / 稳定性 monkey / 流畅度 stage / pytest 脚本）执行期间，
后台 task 每 `ADB_HEARTBEAT_INTERVAL_SEC`（默认 15s）探测一次 `get-state`。
连续 `ADB_HEARTBEAT_FAILURE_THRESHOLD`（默认 2 次）失败后判定设备失联：

- **perf / fluency**：采样循环退出，summary 加 `device_lost: true` 与 `device_lost_at_sec`
- **stability**：终止 monkey 进程并退出 logcat 监听，summary 同上标记
- **android pytest**：terminate pytest 子进程，run 直接 error，错误信息明确"执行中途设备失联"

心跳层只通知，不强行 kill 调用方进程——回收策略由各执行器自行决定，避免越权。

### 3. 命令级重试

`safe_run_adb(serial, args, retries=1)` 包装所有 adb 调用：
非零退出或 `TimeoutExpired` 时自动 `ensure_reachable` 后再试一次。
mobile_special 的 `run_adb_shell` 已透明接入；android_executor 的 `_install_apk` / `_start_app` 同样受益。

### 4. 配置一览

| 配置项 | 默认值 | 作用 |
|--------|--------|------|
| `ADB_RECONNECT_ENABLED` | `True` | 总开关；设 false 时所有自动 disconnect/connect 关闭 |
| `ADB_RECONNECT_MAX_ATTEMPTS` | `3` | ensure_reachable 总尝试次数（含首次） |
| `ADB_RECONNECT_BACKOFF_MS` | `200,800,2000` | 每次重试前退避（逗号分隔毫秒） |
| `ADB_HEARTBEAT_ENABLED` | `True` | 心跳监控总开关 |
| `ADB_HEARTBEAT_INTERVAL_SEC` | `15` | 心跳探测间隔 |
| `ADB_HEARTBEAT_FAILURE_THRESHOLD` | `2` | 连续失败几次判定掉线 |

### 5. 关闭建议

- 真机链路稳定（有线 USB、企业内网）时，可保持默认即可
- 设备处于 doze 频繁的低频测试环境，可调大 `ADB_HEARTBEAT_INTERVAL_SEC=30` 减少噪声
- 用例本身验证"断开恢复"行为时，临时 `ADB_HEARTBEAT_ENABLED=false`

### 6. 如何观察自愈指标（Q7 A.3）

Worker 进程在 `WORKER_METRICS_PORT`（默认 9091）暴露 Prometheus `/metrics`，
通过 Compose `observability` profile 启动 Prometheus + Grafana 即可观察：

```bash
docker compose --profile observability up -d prometheus grafana
```

打开 `ATP Overview` 仪表盘（http://localhost:3000），关注三个面板：

| Panel | 指标 | 健康基线 |
|-------|------|---------|
| ADB reconnect outcomes | `atp_adb_reconnect_total{result=...}` | success 占比 > 95% 为健康 |
| ADB heartbeat lost events | `atp_adb_heartbeat_lost_total{executor=...}` | 1h 内 < 1 次 |
| ensure_reachable latency | `atp_adb_ensure_reachable_duration_seconds` | P95 < 1s 为健康 |

异常告警自动触发（`deploy/grafana/alerts/atp-alerts.yaml`）：
- `atp-adb-reconnect-failure-high`：5min 内 failure 比例 > 30% 且总尝试 > 5
- `atp-adb-heartbeat-lost-burst`：1h 内任一 executor 心跳触发 > 3 次

收到告警后排障流程：

1. 运行 `bash scripts/android-network-doctor.sh <device-ip>:5555` 一键诊断
2. 检查 Grafana ADB latency 面板 P99 是否飙升 → 通常是宿主网络拥塞
3. 检查 reconnect outcomes 中 `adb_not_found` 计数 → worker 镜像 adb 二进制问题
4. 若 heartbeat lost 集中在某一 executor → 排查该执行器的脚本是否有阻塞设备的操作
5. 必要时临时设置 `ADB_HEARTBEAT_ENABLED=false` + `ADB_RECONNECT_ENABLED=false` 切换到原始模式，做对照
# Windows Android Worker

需要让 Android 真机连接 Windows、由本地 ADB 执行并回传结果时，参阅 [`android-windows-worker.md`](android-windows-worker.md)。本文下面的 Docker/ADB Server 方案仍适用于设备与 Worker 位于同一网络的部署。
