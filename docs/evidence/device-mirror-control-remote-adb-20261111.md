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

## 第二轮：页面实测暴露的问题（同日修复）

用 Playwright 直接驱动云端页面（注入 `atp_access_token` Cookie）实测发现：

1. **弹窗标题插槽未渲染**：`a-modal` 同时传 `title` prop 与 `#title` 插槽时，ant-design-vue 4.2.6 的 `vc-dialog/Content.js` 取 `props.title ?? slots.title()`，插槽被丢弃 → 页面没有“只读模式/控制权已生效”标签和“获取控制权”按钮。去掉 `title` prop 后按插槽渲染。
2. **重复申请租约**：`watch(open, immediate)` 与 `watch(device.id)` 同时触发，实测出现 `409 → 200` 双请求，且 409 触发误导性提示。改为单飞（`leaseRequestInFlight`）。
3. **冲突原因被吞掉**：`http` 响应拦截器以字符串拒绝（`reject(error.response?.data?.detail)`），组件却按 axios 错误读 `err.response.data.detail`，只能显示兜底文案“设备可能正被其他任务占用”。新增 `leaseErrorText()` 兼容字符串与错误对象。
4. **占用无从判断**：后端冲突文案改为带占用者与剩余时间（`设备已被“自动化用例执行”占用，预计 1 分 30 秒后释放`），弹窗内以常驻 `a-alert` 展示并提供“重试获取控制权”。
5. **租约泄漏**：投屏租约原为 600s，关闭标签页不释放时设备被占约 10 分钟。改为 TTL 90s、每 25s 心跳续期（心跳接口新增可选 `ttl_seconds`），关闭弹窗仍显式释放。
6. **连接中布局塌陷**：首帧到达前 `.mirror-screen-wrapper` 宽度为 0，弹窗高度 230px、占位文字竖排。空状态给 9:16 固定尺寸（横屏 16:9）。
7. **状态与标题文案**：表头 `busy` 直接显示英文；标题重复品牌（`OPPO OPPO R11`）。改为映射（在线/执行中/离线）与去重。
8. **忙碌设备无法打开投屏**：表格视图 `v-if="record.status === 'online'"` 隐藏投屏入口，改为离线才隐藏（忙碌时仍可只读观察）。

第二轮验证（部署 `backend:d3f3d3d7`、`frontend:b65ac83d-3`）：

```text
earlyGeometry {"frame":{"w":316,"h":444},"wrapper":{"w":300,"h":418}}   # 0.9s 时不再塌陷
headerTags ["在线","控制权已生效 (1:30)"]
200 POST /api/v1/devices/4701/lease      # 单次申请，无 409
200 POST /api/v1/devices/4701/keyevent   # 持租约按返回键
204 DELETE /api/v1/devices/4701/lease    # 关闭释放

# 外部占用场景（另一会话持租约）
alert: 当前无法控制设备：设备已被“自动化用例执行”占用，预计 1 分 30 秒后释放
tag: 只读模式 → 释放占用后点“重试获取控制权” → 控制权已生效 (1:29)，alert 消失
```

## 第三轮：仍然无法操作的真实原因（同日修复）

用户反馈“浏览器里还是不能操作手机”。实测定位到两个叠加原因：

1. **被自己的其他页面锁住**：设备被租约 49 占用（`owner_label=android-case-editor`，TTL 900s，本人）。用例编辑器/APP 工作台打开即占设备，关闭标签页后仍要等 15 分钟过期；投屏弹窗此时只能拿到 409，用户无法自行解锁。
   - 后端：`acquire_device_lease(..., takeover_own=True)` 允许**本人**显式接管自己的遗留租约（按 id+令牌条件删除后重建）；他人租约即使带该标志仍冲突。`POST /devices/{id}/lease` 新增 `takeover_own` 字段。
   - 前端：投屏弹窗的冲突提示新增“接管我自己的租约”按钮；用例编辑器与 APP 工作台的租约改为 TTL 120s、每 30s 心跳（心跳带 `ttl_seconds`），关页面后最多占用 2 分钟。
2. **截图模式太慢**：`http://192.168.3.196:8080` 是明文 HTTP，`VideoDecoder` 只在安全上下文（HTTPS/localhost）暴露，`isWebCodecsSupported()` 恒为 false → 永远走“截图降级模式”。而截图接口返回 1080×1920 原始 PNG（约 2.6MB/帧），350ms 轮询 ≈ 7.4MB/s，操作明显滞后。
   - 后端：`GET /devices/{id}/screenshot` 新增 `max_width`、`fmt`（png/jpeg），Pillow 在后台线程降采样/转码。
   - 前端：投屏轮询改为 `max_width=540&fmt=jpeg`；设备真实分辨率优先取设备档案，避免预览缩小后点击坐标被按 540 宽换算。

部署：`backend/worker:dd492c9d`、`frontend:dd492c9d`，Helm revision 84，迁移头不变（`20261110_0087`）。

## 残留与限制

- **实时流需要 HTTPS**：明文 HTTP 下 WebCodecs 不可用，投屏固定走截图模式（现已优化为 JPEG 540 轮询）。要启用 60FPS scrcpy 实时流，需给云端 Web 入口配置 TLS（自签或正式证书）。
- `adb -a start-server` 不是持久配置：任何 `adb kill-server` 或普通 adb 客户端自动拉起的 server 都会退回回环绑定，需要人工重跑；未在 `scripts/windows-android-worker.ps1` 中自动检测。
- 云端镜像内没有 `scripts/`，`/device-agents/agent-script` 下载端点仍指向缺失文件（既有问题，未在本轮修改）。
- 未执行 MSI/便携包重建；前端改动仅部署到云端 Web 入口。
- 真机验收只覆盖单台 OPPO R11（USB 经 Windows ADB server 转发），未覆盖多设备并发与模拟器。
- 浏览器直接关闭标签页时不会立刻释放租约，依赖 TTL（投屏 90s、编辑器/工作台 120s）到期回收；未加 `pagehide` 上报。
- “接管我自己的租约”只在租约 owner 与当前账号一致时生效；管理员强制接管他人租约与审计仍未实现。
