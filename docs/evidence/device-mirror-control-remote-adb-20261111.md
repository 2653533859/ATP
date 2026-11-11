# 投屏控制租约修复与远程 ADB server 部署验证（2026-11-11）

## 现象与根因

用户在 APP 工作台/设备中心打开投屏弹窗后，按键、点击返回 `409 设备控制需要先获取有效租约`；设备画面无法进入 scrcpy 极速流。

三处独立缺陷，均已修复：

1. 投屏弹窗从设备中心打开时没有携带 `leaseToken`，也从不申请租约，因此所有写操作（tap/swipe/keyevent/text）都被后端门禁拒绝。
2. scrcpy WebSocket 未携带 `token`，云端握手返回 403；后端 `/ws/scrcpy/{serial}` 支持 Cookie 或 `?token=`，前端此前两者都不带。
3. 云端镜像内 `bundled_resource("backend/assets/scrcpy-server.jar")` 解析到 `/backend/assets/...`（不存在）；容器把 `backend/` 复制到 `/app/`，实际文件在 `/app/assets/scrcpy-server.jar`。即使修好前两项，流也启动不了。
4. 远程 ADB server 模式下 `adb forward` 的监听在 ADB server 主机（Windows），而 `manager.py` 固定连 `127.0.0.1:<port>`，容器内连接必然超时（日志 `Video socket 连接超时`）。

另有一次现场运维事件：Windows 宿主 ADB server 被普通 `adb start-server` 重新拉起后只绑定 `127.0.0.1:5037`，云端 `adb devices` 报 `Connection refused`；改以 `adb -a start-server` 重启后恢复（该要求已写入 `docs/android-device-debugging.md`）。

## 代码变更

| 提交 | 内容 |
| --- | --- |
| `4489cb82` | `DeviceMirrorModal.vue`：打开弹窗时自动申请 600s 交互租约（静默，避免每次弹提示）、25s 心跳续期、倒计时展示、只读时禁用按键/输入并提示、关闭/卸载释放；scrcpy WS 追加 `?token=<jwt>`；重做弹窗头部、机身外框与底部状态栏。`DeviceMirrorModal.spec.ts` 增加自动租约用例。 |
| `79df0d22` | `app/core/package_paths.py`：`installation_root()` 支持容器布局（`/app` 即应用根），`bundled_resource()` 在直达路径缺失时去掉 `backend/` 前缀重试；新增容器布局回归用例。 |
| `a81e27ee` | `app/device_stream/manager.py`：新增 `_adb_forward_host()`，远程 `ADB_SERVER_SOCKET=tcp:host:port` 时 scrcpy 的 video/control socket 连接 `<host>:<forward_port>`，未配置时仍为 `127.0.0.1`；补远程/回环两条用例。 |

> `79df0d22` 同时带入了同一工作区中另一并行会话（Android Agent M2/M3）已暂存的未提交改动（13 个文件），提交说明因此只覆盖 assets 修复本身；内容未丢失，云端未部署该提交。

## 部署

服务器 `192.168.3.196`（`mylinux`），K3s 命名空间 `atp-single-node`，数据库 `atp_acceptance`：

1. 部署基线取 `4489cb82`（含投屏修复），叠加 `package_paths` 与 `manager` 两处后端修复；从未部署含未完成 Android Agent 改动的 `79df0d22` 树。
2. 发布目录 `/opt/atp-release-4489cb82-20261110`、`/opt/atp-release-4489cb82-assetfix-20261111`、`/opt/atp-release-4489cb82-remoteadb-20261111`；升级前 `pg_dump -Fc atp_acceptance` 备份到发布目录（`pre-release-atp.dump`，388 KiB）。
3. 镜像：`registry.local/atp/backend:4489cb82-remoteadb`、`registry.local/atp/worker:4489cb82-remoteadb`（overlay 于现有基础镜像）；前端 `registry.local/atp/frontend:4489cb82-20261110` 由 `npm run build` 产物重建。
4. `helm upgrade atp-single-node` 依次到 revision 79（`4489cb82`）、80（`4489cb82-assetfix`）、81（`4489cb82-remoteadb`）；迁移头 `20261110_0087`（head），未引入新迁移。
5. `atp-cloud-web` 容器指向 `frontend:4489cb82-20261110`，`docker compose` 重建后 200 健康。

## 验证（全部实测）

部署后从 backend Pod 内发起，针对真实 OPPO R11（`b01ac8cb`）：

```text
device 4701 b01ac8cb online OPPO R11
lease 200            # 获取控制权（ttl 600s）
conflict_lease 409   # 第二会话申请被拒「设备已被其他任务占用」
keyevent_back 200    # 持租约按返回键成功
screenshot 200 image/png 2610289 bytes
heartbeat 200
keyevent_without_lease 409  # 无租约仍被门禁拦截
release 204
```

scrcpy WebSocket（`/ws/scrcpy/b01ac8cb`）：

```text
no_token: rejected InvalidStatus server rejected WebSocket connection: HTTP 403
token:    frames 5 bytes 43359     # 收到真实 H.264 帧
```

其他核查：`GET /health` 200；`/api/v1/runtime` = `{"mode":"server","database":"postgresql","storage":"minio","execution":"celery"}`；`http://192.168.3.196:8080/` 与深链接 `/device/list` 均 200；6 个核心 Pod 1/1 Running、0 重启。

## 残留与限制

- `adb -a start-server` 不是持久配置：任何 `adb kill-server` 或普通 adb 客户端自动拉起的 server 都会退回回环绑定，需要人工重跑；未在 `scripts/windows-android-worker.ps1` 中自动检测。
- 云端镜像内没有 `scripts/`，`/device-agents/agent-script` 下载端点仍指向缺失文件（既有问题，未在本轮修改）。
- 未执行 MSI/便携包重建；前端改动仅部署到云端 Web 入口。
- 真机验收只覆盖单台 OPPO R11（USB 经 Windows ADB server 转发），未覆盖多设备并发与模拟器。
