# Android 真机联调说明

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

推荐顺序：

1. 宿主机先完成 `adb connect <device-ip>:5555`
2. 再启动 ATP worker
3. 通过 ATP 的设备扫描接口刷新设备列表

如果 Docker 环境网络桥接导致设备不可见，可尝试：

```yaml
worker:
  network_mode: host
```

注意：

- Windows / Docker Desktop 对 host 网络支持有限
- 如果 host 模式不可用，优先保证容器到设备 IP 可达

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

**宿主机先完成 ADB over TCP 连接，再由 ATP Worker 复用该链路执行。**

---

## 七、宿主网络与 Docker 环境差异

### 1. Docker Desktop vs Linux 宿主

| 平台 | host 网络支持 | 推荐方案 |
|------|---------------|---------|
| Linux | 完整 | `network_mode: host` 最简单 |
| Docker Desktop (Win/Mac) | 受限 | 优先用 ADB over TCP；宿主先 `adb connect`，容器复用 |

Docker Desktop 因 VM 层隔离，容器无法直接探测物理网卡上的设备 IP。推荐让宿主机维护 ADB 连接，容器通过 `host.docker.internal:5555` 或显式宿主 IP 访问。

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
