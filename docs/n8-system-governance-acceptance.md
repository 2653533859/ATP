# N8 系统治理验收

该脚本用于在目标部署验证远程工具箱、配置中心、配置差异、单资源回滚、审计导出和普通角色拒绝边界。默认只读；配置版本和回滚会产生有意保留的审计记录，必须显式传入 `--allow-mutations`，回滚还必须传入 `--rollback`。

凭据只从环境变量读取，不要把密码、Token 或带凭据的 URL 写入命令行、仓库或证据文件。脚本不会记录响应正文、配置值、Endpoint 或密钥；配置快照由服务端加密保存，报告只保留检查状态和有限资源 ID。

## Windows PowerShell

```powershell
$env:ATP_USERNAME = '<global-admin>'
$env:ATP_PASSWORD = '<password>'
$env:ATP_VIEWER_USERNAME = '<ordinary-user>'
$env:ATP_VIEWER_PASSWORD = '<password>'

python scripts/n8-system-governance-acceptance.py `
  --base-url 'http://127.0.0.1:8000/api/v1' `
  --require-role-matrix `
  --report 'docs/evidence/n8-system-governance-acceptance-YYYY-MM-DD.json'
```

需要验证配置版本和回滚时，使用单独的显式变更命令：

```powershell
python scripts/n8-system-governance-acceptance.py `
  --base-url 'http://127.0.0.1:8000/api/v1' `
  --allow-mutations --rollback --require-rollback --require-role-matrix `
  --report 'docs/evidence/n8-system-governance-acceptance-YYYY-MM-DD.json'
```

## 结果解释

- `passed`：远程诊断、配置元数据、审计导出和已要求的回滚/角色拒绝均完成。
- `partial`：只读检查完成，但未提供 viewer、未启用变更或未要求回滚；不能关闭 N8 目标部署门禁。
- `failed`：连接、响应契约、权限边界、脱敏或回滚失败。优先处理服务端事务和审计记录，再重复验收。

远程工具箱返回 `error` 或 `warning` 只会被记录为目标环境状态；脚本不把“诊断接口可访问”误写成 PostgreSQL、Redis、MinIO、Worker 或 ADB 已健康。N8 完整门禁还需要目标部署的管理员和普通角色证据，以及配置差异、精确 `ROLLBACK` 和审计事件可回看。

命令入口：

```text
make n8-system-governance-acceptance ARGS="--base-url ... --require-role-matrix [--allow-mutations --rollback --require-rollback] --report ..."
```
