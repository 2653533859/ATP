# N6 项目资产与角色矩阵验收

该脚本用于验证“临时项目 → 模块 → API 用例 → 用例评审 → 测试套件 → 测试计划 → 执行记录/报告 → 内部缺陷 → 清理”的链路；blank 临时项目没有模块时会显式创建一个临时模块。提供普通 viewer 账号时，脚本还会创建一个不授予 viewer 成员资格的隔离项目，验证项目/成员/用例/套件/计划/缺陷的跨项目读取拒绝，以及项目内已创建资产的读取和写入边界。

脚本是有副作用的验收命令，必须显式传入 `--allow-mutations`。凭据只从环境变量读取，不要把密码、Token 或带凭据的 URL 写入命令行、仓库或证据文件。

## Windows PowerShell

```powershell
$env:ATP_USERNAME = '<admin-or-engineer>'
$env:ATP_PASSWORD = '<password>'
# 推荐使用短期令牌；没有令牌时再使用普通账号密码。
$env:ATP_VIEWER_TOKEN = '<short-lived-viewer-token>'
# $env:ATP_VIEWER_USERNAME = '<ordinary-project-user>'
# $env:ATP_VIEWER_PASSWORD = '<password>'

python scripts/n6-project-asset-acceptance.py `
  --base-url 'http://127.0.0.1:8000/api/v1' `
  --allow-mutations `
  --execute `
  --target-url 'http://127.0.0.1:8000/health' `
  --require-role-matrix `
  --report 'docs/evidence/n6-project-asset-acceptance-YYYY-MM-DD.json'
```

Linux/macOS 可使用同名参数；也可以通过 `ATP_ACCEPTANCE_BASE_URL`、`ATP_ACCEPTANCE_TARGET_URL`、`ATP_TOKEN` 和 `ATP_VIEWER_TOKEN` 提供连接信息。`ATP_VIEWER_TOKEN` 与 `ATP_VIEWER_USERNAME/ATP_VIEWER_PASSWORD` 二选一，令牌优先；认证值只从环境变量读取，报告不会记录。`--execute` 只允许无认证、无 query/fragment 的 HTTP(S) 目标，默认只发起只读 GET。

## 结果解释

- `passed`：所有步骤完成并清理临时项目；只有同时提供 `--execute` 和 `--require-role-matrix` 才覆盖完整执行与角色门禁，提供 viewer 账号时还会覆盖跨项目读取拒绝。
- `partial`：没有执行或没有提供普通角色账号/令牌，只能作为本地链路准备结果，不能关闭 N6 发布门禁。
- `failed`：连接、权限、链路、执行超时或清理失败；优先处理 `cleanup`，避免遗留临时数据。

证据 JSON 只记录检查状态、脱敏 endpoint、资源 ID 和有限长度的安全说明，不记录密码、Token、请求正文、响应正文、Cookie 或预签名 URL。真实验收后应审查并确认主项目、隔离项目、成员、套件、计划、运行、缺陷和对象存储产物均已清理。

2026-08-26 q19 受控真实验收证据：[`docs/evidence/n6-project-asset-acceptance-2026-08-26.json`](evidence/n6-project-asset-acceptance-2026-08-26.json) 为 `passed`；项目 → 模块 → 用例 → 评审 → 套件 → 计划 → 计划运行（终态 `passed`）→ 内部缺陷关联全链路完成，viewer 可读主项目全部资产而跨项目读取与用例/模块写入均被 `HTTP 403` 拒绝，主项目与隔离项目分别删除。N6 门禁已关闭。

2026-08-25 q19 基础链路证据（历史）：[`docs/evidence/n6-project-asset-acceptance-2026-08-25.json`](evidence/n6-project-asset-acceptance-2026-08-25.json) 为 `partial`；管理员链路、`--execute` 终态运行、缺陷关联和清理均通过，仅因未提供普通 viewer 账号跳过角色矩阵。

命令入口：

```text
make n6-project-asset-acceptance ARGS="--base-url ... --allow-mutations --execute --target-url ... --require-role-matrix --report ..."
```
