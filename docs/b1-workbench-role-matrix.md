# B1 工作台与角色矩阵验收

本验收用于确认管理员、工程师和只读成员在同一项目中的工作台可见范围与操作边界。它覆盖工作台概览、五类任务分页、失败诊断、Viewer 操作标记、跨项目拒绝，以及可选的 Viewer 写入拒绝。默认流程只读，不创建、不重试也不停止任务。

本地前端继续运行在 Windows；`--base-url` 指向 Linux Backend 的 `/api/v1`。打开页面、健康检查或未认证 `401` 只能证明基础连通，不能替代三角色验收。

## 准备账号与项目

选择一个受控项目，并满足以下条件：

- 管理员账号的全局角色为 `admin`；
- 工程师账号的全局角色为 `engineer`，在目标项目内为 `owner` 或 `editor`；
- 只读账号的全局角色为 `tester` 或 `viewer`，在目标项目内必须为 `viewer`；
- 如需关闭五类任务门禁，目标项目需各有 Case、Suite、Plan、Android、Performance 真实运行记录；
- 如需验证跨项目隔离，另选一个工程师和 Viewer 都不是成员的项目。

凭据只通过环境变量提供。优先使用短期 Token；不要把密码、Token 或带凭据的 URL 写入命令行、仓库、截图或证据文件。

```powershell
$env:ATP_ADMIN_TOKEN = '<short-lived-admin-token>'
$env:ATP_ENGINEER_TOKEN = '<short-lived-engineer-token>'
$env:ATP_VIEWER_TOKEN = '<short-lived-viewer-token>'

# 没有 Token 时，每个角色也可分别使用 USERNAME/PASSWORD：
# $env:ATP_ADMIN_USERNAME = '<admin>'
# $env:ATP_ADMIN_PASSWORD = '<password>'
# $env:ATP_ENGINEER_USERNAME = '<engineer>'
# $env:ATP_ENGINEER_PASSWORD = '<password>'
# $env:ATP_VIEWER_USERNAME = '<viewer>'
# $env:ATP_VIEWER_PASSWORD = '<password>'
```

## 执行验收

先执行只读探针：

```powershell
python scripts/b1-workbench-role-matrix.py `
  --base-url 'http://<linux-host>:<backend-port>/api/v1' `
  --project-id <project-id> `
  --foreign-project-id <foreign-project-id> `
  --require-five-domains `
  --report 'docs/evidence/b1-workbench-role-matrix-YYYY-MM-DD.json'
```

仅在受控环境中显式增加 `--verify-denials`。该步骤会以 Viewer 对一个当前可操作任务发送重试或停止请求，预期在创建命令和派发 Worker 前返回 HTTP 403；如果没有可操作任务，结果保持 `partial`。

Make 入口：

```text
make b1-workbench-role-matrix ARGS="--base-url ... --project-id ... --foreign-project-id ... --require-five-domains --verify-denials --report ..."
```

## 结果口径

- `passed`：所有已启用门禁均通过，五类任务有真实数据，失败诊断和跨项目/Viewer 拒绝均有证据。
- `partial`：基础契约通过，但缺少某类任务、失败任务、外部项目或显式拒绝探针；不能关闭 B1 真实环境门禁。
- `failed`：身份、项目成员关系、项目隔离、分页、操作标记、诊断或权限拒绝不符合契约。

报告只记录角色检查、数量、有限任务 ID 和脱敏 URL，不记录认证值或响应正文。活跃环境中的任务可能在三个角色依次读取时变化，因此探针验证每次响应的项目隔离和权限语义，不要求三个瞬时任务集合完全相等。

## 前端补充验收

API 探针通过后，仍需分别登录三个账号完成浏览器检查：项目切换与刷新保持 `project_id`，深链返回目标项目，侧栏折叠和窄屏不遮挡任务操作；Viewer 不展示重试/停止按钮，工程师仅能操作其可写项目，Android/Performance 还要求全局工程师角色。保留浏览器、提交 SHA、项目 ID 和时间戳证据，避免记录 Token 或密码。

2026-09-09 部署前置已完成：Windows Vite 到 Linux Backend 的代理传输正常，目标 K3s revision 12 的五个核心 Pod 均 Ready、零重启，Backend/Worker 使用提交 `5c0f6908` 的不可变标签，迁移位于 `20260908_0070`。Backend 在单节点 `hostNetwork` 下的滚动策略已固化为 `maxSurge=0/maxUnavailable=100%`。只读数据核查同时确认目标环境缺少全局工程师、项目级 Viewer 成员关系和五类真实运行数据；在明确创建受控账号与运行数据前，登录页、HTTP 401、Pod 健康和空数据接口仍不得写成 B1.3 通过。
