# 启动配置档案

这些文件只提供启动模板，不包含真实密码。先复制需要的模板，并填写实际值：

```powershell
Copy-Item .\config\startup-profiles\local-all.env.example .\config\startup-profiles\local-all.env
Copy-Item .\config\startup-profiles\remote-infra.env.example .\config\startup-profiles\remote-infra.env
Copy-Item .\config\startup-profiles\android-agent.env.example .\config\startup-profiles\android-agent.env
Copy-Item .\config\startup-profiles\performance-agent.env.example .\config\startup-profiles\performance-agent.env
```

实际 `.env` 文件已加入 `.gitignore`。使用 `android-agent` 或 `remote-infra` 时，数据库、Redis、MinIO 地址和加密密钥必须与公网 ATP 后端匹配。

Web 录制默认是 `WEB_RECORDER_MODE=local`。如需在 Windows 上把浏览器会话拆到独立进程，将 `local-all.env` 或 `remote-infra.env` 中的该值改为 `worker`；`local-dev.cmd up` 会自动启动并托管 Web Recording Worker。API 与 Worker 的 Redis 地址、队列前缀必须一致。
`android-agent.env.example` 用于仅启动 Windows Android Worker；脚本会自动注入 `ANDROID_WORKER_ID` 并通过 Redis TTL 注册心跳，设备页可查看在线 Agent。后端使用远程 Worker 时，后端配置应使用 `ADB_SCAN_MODE=worker`。
启动 `android-agent` 时会自动执行 doctor；基础服务、Python/Celery 或 ADB 配置不通过会阻止 Worker 启动，未连接设备仅作为 warning。
如需在 doctor/启动前核对公网 Backend 与 Windows Agent 的数据库、Redis、MinIO、密钥和队列配置，可为 `startup.ps1` 或 `windows-android-worker.ps1` 传入 `-BackendEnvFile`；校验器只输出字段名和状态，不输出密钥值。

`local-all` 与 `android-agent` 是两种互斥的 Android 队列运行方式：`local-all` 默认让本地普通 Worker 监听 `android,mobile_special`，适合整套服务都在 Windows 本机运行；`android-agent` 只适合远程后端/基础设施，由专用 Worker 在本机执行 ADB。不要在同一台 Windows 主机上同时启动两种模式，否则 Android 任务可能被两个 Worker 抢占。`windows-local.ps1` 和 `windows-android-worker.ps1` 会双向检测队列重叠并阻止冲突启动。

`performance-agent.env.example` 用于只启动 Windows 性能 Worker。它会自动注册 `PERFORMANCE_NODE_ID`、刷新节点心跳并只消费 `PERFORMANCE_NODE_QUEUE`，建议使用 `performance.worker-a` 这类独立队列，避免抢走共享 `performance` 队列中的未绑定任务。节点页面的名称、执行器、容量和出口白名单仍以页面配置为准；环境文件主要用于 Worker 身份和队列对齐。
