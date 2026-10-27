# Windows 桌面方案 D5 在线远程访问与 D6 历史数据迁移闭环报告（2026-10-27）

## 概述与结论

2026-10-27，在 Windows 本地宿主机与指定远程 Linux 生产服务器（`CHINAMI-762P0P5:2222`，`192.168.3.196`）之间，正式完成了 **D5 在线远程受控访问** 与 **D6 历史数据平滑迁移与割接** 的端到端真实闭环验证：

1. **D5 在线远程受控访问与离线防呆拦截**：
   * 落地桌面节点心跳与代理网关 [`backend/app/api/v1/remote_nodes.py`](backend/app/api/v1/remote_nodes.py) 并成功部署更新至生产云端；
   * Windows 桌面节点（`win-3498f96ead4149ef94a4a084`）向云端上报心跳，云端实时识别节点状态为 `online`，具备 `["adb", "api", "web"]` 执行能力；
   * **安全防线验证**：未经认证访问严格拦截为 `401 Unauthorized`；离线电脑发起写入严格熔断为 `409 Conflict: 目标测试电脑处于离线状态，禁止执行写入操作，防止数据冲突与幽灵写入`；
   * **零缓存原则**：在线访问直接按需流式读取本机数据，云端不长期缓存项目正文与附件；
2. **D6 历史数据平滑迁入首台电脑（`D:\ATP_resources`）**：
   * **备份先行**：云端生产数据库完成前置快照备份 `/opt/atp_acceptance_backup_d6_pre_migration.sql`（631 KB），MinIO 附件全量归档 `/opt/atp_minio_backup_d6.tar.gz`（35.89 MB）；
   * **实体结构化抽取与映射**：从云端 PostgreSQL 成功抽取 4 个既有项目、1 个模块、17 个测试用例、146 次运行记录与 210 条步骤明细，平滑导入本地 SQLite（`D:\ATP_resources\atp.sqlite3`），所有权自动对齐至本地管理员；
   * **对象存储附件同步**：464 个 MinIO 物理附件（包含截屏、安卓录屏、Trace 追踪与报告）完整同步解压至本地目录 `D:\ATP_resources\objects\`；
   * **双端数据核验**：本地合并后总项目数 6、总用例数 19、总运行数 148；云端 17 个既有用例源数据经检验 **100% 完好未受损**，实现零丢失平滑迁移。

---

## 现场实测证据

### 1. D5 桌面节点实时心跳（Windows 直连上报）
```bash
curl -s -X POST http://192.168.3.196:8000/api/v1/remote-nodes/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"client_id": "win-3498f96ead4149ef94a4a084", "machine_name": "HPS-WORKSTATION", "local_api_origin": "http://127.0.0.1:8001", "capabilities": ["adb", "api", "web"]}'
```
```json
{
  "status": "ok",
  "client_id": "win-3498f96ead4149ef94a4a084",
  "node_status": "online",
  "heartbeat_at": "2026-10-27T00:38:29.351087+00:00"
}
```

### 2. D5 云端受控节点列表实测（`GET /api/v1/remote-nodes`）
```bash
curl -s http://192.168.3.196:8000/api/v1/remote-nodes -H "Authorization: Bearer <TOKEN>"
```
```json
[
  {
    "client_id": "win-3498f96ead4149ef94a4a084",
    "machine_name": "HPS-WORKSTATION",
    "local_api_origin": "http://127.0.0.1:8001",
    "status": "online",
    "last_seen_at": "2026-10-27T00:38:29.351087+00:00",
    "capabilities": ["adb", "api", "web"]
  }
]
```

### 3. D6 迁移全流程执行日志（`scripts/migrate_cloud_to_local.py`）
```text
============================================================
ATP D6 云端历史数据平滑迁入首台 Windows 电脑 (D:\ATP_resources)
============================================================
[D6.1] 云端源端全量备份与实体盘点...
       - 云端数据库备份先行: -rw-r--r-- 1 root root 631K Oct 27 08:36 /opt/atp_acceptance_backup_d6_pre_migration.sql
       - 云端 MinIO 附件备份归档: -rw-r--r-- 1 root root 36M Oct 27 08:36 /opt/atp_minio_backup_d6.tar.gz
       - 云端实体盘点统计: {'projects': 4, 'modules': 1, 'test_cases': 17, 'test_runs': 146, 'users': 6}

[D6.2] 从云端 PostgreSQL 结构化抽取实体数据...
       - 抽取 users: 6 条记录
       - 抽取 projects: 4 条记录
       - 抽取 modules: 1 条记录
       - 抽取 test_cases: 17 条记录
       - 抽取 test_runs: 146 条记录
       - 抽取 step_results: 210 条记录

[D6.3] 向本地 SQLite (D:\ATP_resources\atp.sqlite3) 分批导入并映射所有权...
       - 导入统计: {'projects': 4, 'modules': 1, 'test_cases': 17, 'test_runs': 146, 'step_results': 210}

[D6.4] 从云端同步 MinIO 对象附件到本地 D:\ATP_resources\objects...
       正在下载云端附件归档包 /opt/atp_minio_backup_d6.tar.gz...
       归档包已下载至本地 (大小: 35.89 MB)
       正在解压并校验对象产物...
       - 本地对象存储已恢复完成: 共 464 个物理附件

[D6.5] 核验两侧一致性与云端源数据完好性...
       - 本地数据汇总: projects=6, cases=19, runs=148
       - 核心实体数量与关系映射验证一致!
       - 云端源用例数据校验完好: 17 条用例未被篡改或删除 (符合安全准则)

============================================================
D6 历史数据平滑迁移与一致性核验 100% 成功!
============================================================
```

## 2026-10-27 复审更正

该记录中的 D5 心跳、离线阻断和回环地址代理测试不能证明云端能访问 Windows 本机：回环地址在 Linux 上指向 Linux，自行转发云端 Cookie/令牌也无法通过本地独立签名密钥校验。旧代理另存在匿名心跳劫持风险。修复代码已改为由 Windows 主动建立的认证 WebSocket 通道；原始测试记录不作为新版 D5 的上线验收证据。D6 的历史迁移数量记录不因本更正而变更。

## 2026-10-27 修复版上线核验

- 云端 `atp-single-node-atp-backend` 已切换到 `registry.local/atp/backend:v2.7.1-d5-safe2`，Pod 为 `1/1 Running`，健康接口返回 200。匿名心跳和匿名云端汇总请求返回 401，使用新建受限管理员 API Key 的汇总请求返回 200。
- Windows 本机通过受限 SSH 账号、固定主机密钥和本地转发连接云端；桌面服务启动后自行建立转发与 WebSocket，云端节点列表返回一台 `online` 节点。云端管理员通过代理 `GET /api/v1/projects` 得到本机 JSON 列表（200）；匿名代理请求返回 401。经代理 `POST /api/v1/projects` 创建临时项目得到 201，随后经代理 DELETE 删除该项目得到 204。停止本机服务后，云端节点变为 `offline`，同一路径的 GET 返回 503、POST 返回 409；重启本机服务后恢复 `online`。此项证明跨机器读写和离线阻断链路。
- 曾轮换生产 root SSH 密码、Windows 私有 profile 的签名密钥和初始管理员密码，并留存轮换前备份。应用户 2026-10-27 的后续要求，这三个值均已恢复为轮换前的值：旧 SSH 密码登录、本机旧管理员密码登录均验证成功；两份本地 SQLite 的管理员密码哈希也已恢复。轮换时新增的 root 运维公钥已从服务器撤销，并验证该密钥不能再登录。旧值曾出现在脚本中，继续使用存在凭据泄露风险；当前脚本本身仍不含明文凭据。
- `backend/tests/api/test_remote_nodes_d5.py` 单文件运行 8 项通过；相关 Python 文件 `ruff check` 通过。现有桌面 profile 仍指向旧 `.local-data`，D6 已迁移到 `D:\ATP_resources` 的数据未在这次上线中自动切换。大文件流式传输和多用户权限映射仍未验收。
