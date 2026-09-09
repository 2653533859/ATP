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

## 2026-09-09 实测结果

B1.3 已在受控数据集上通过。运行版本为 Backend/Worker 不可变标签 `5c0f6908`、Helm revision 12、迁移 `20260908_0070 (head)`；目标项目为 `77`，隔离项目为 `78`。脱敏 API 证据见 [`evidence/b1-workbench-role-matrix-2026-09-09.json`](evidence/b1-workbench-role-matrix-2026-09-09.json)：管理员、工程师和 Viewer 三个独立身份均通过认证与项目成员关系检查，Case、Suite、Plan、Android、Performance 各有 2 条运行，失败诊断可读，非成员跨项目读取与 Viewer 写操作均返回 HTTP 403。证据不包含密码、Token 或响应正文。

Windows 本地前端以 `http://127.0.0.1:4173` 运行，并通过 Vite 直接代理到 K3s Backend `http://192.168.3.196:8000`。三角色浏览器矩阵确认：

- Admin 与 Engineer 在可写项目中可见失败任务的重试入口，Viewer 仅显示查看与失败诊断，批量重试和批量终止保持禁用；
- `project_id=77&status=failed` 深链、手动刷新、侧栏折叠和 390 px 窄屏均保持目标项目和任务可用；
- Admin 从项目 77 切换到隔离项目 78 时 URL 与空任务状态同步，切回项目 77 后失败筛选和六条可见任务恢复；
- 临时验收账号、项目和运行数据为后续 B1.4 保留，未执行清理。

端口边界必须保持明确：`8000` 是当前 K3s `hostNetwork` Backend；`29080` 属于旧 q19 Docker Backend。二者虽然连接同一数据库，但 `29080` 不包含本次部署代码，不能用于 B1 或当前 K3s 验收。

B1.4 随后在项目 77 完成，脱敏动作证据见 [`evidence/b1-workbench-actions-2026-09-09.json`](evidence/b1-workbench-actions-2026-09-09.json)。五个领域均通过批量重试、轮询和源运行不变性检查；精确批量与单项重放未重复派发。Android 与 Performance 批量停止分别收敛到 `stopped` 和 `cancelled`，跨命令 ID 重复停止返回既有结果且不重复发信号。

实测还发现首次对独立终态运行发起过期停止时，命令失败持久化在回滚后读取已过期 ORM 对象，触发 `MissingGreenlet` 并返回 500。提交 `86668152` 在回滚前保存命令主键，并为失败和不确定结果补充回归测试；修复部署为 Helm revision 13 后，五域动作矩阵在同一运行版本完整重跑，新建 Performance Run 35 成功结束，首次停止和同键重放均稳定返回 409，详情一致，Backend 日志无新异常。B1.1～B1.4 至此关闭。单节点没有 Android 执行 Worker，Android 自主执行仍属于 B4 环境门禁，不由工作台控制面验收替代。
