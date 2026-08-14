# 通知渠道真实环境验收

通知配置的代码回归只能证明请求构造、有限重试、投递记录和权限边界正确，不能证明目标 SMTP、企业微信或钉钉公网渠道真的可达。真实环境验收使用统一脚本完成一次测试发送，并核对 `notification_deliveries` 中的实际结果。

## 安全准备

凭据只通过当前终端环境变量提供，不写入命令行参数、仓库文件或验收报告：

```powershell
$env:ATP_TOKEN = '<短期 API Token>'
```

或者使用工程师账号建立 Cookie 会话：

```powershell
$env:ATP_USERNAME = '<工程师用户名>'
$env:ATP_PASSWORD = '<临时密码>'
```

验收完成后清理当前终端变量：

```powershell
Remove-Item Env:ATP_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:ATP_USERNAME -ErrorAction SilentlyContinue
Remove-Item Env:ATP_PASSWORD -ErrorAction SilentlyContinue
```

## 执行

先在通知配置页面或 `GET /api/v1/notifications?project_id=...` 找到目标配置 ID，再执行：

```powershell
python scripts/notification-channel-smoke.py `
  --api-base-url https://atp.example.test `
  --config-id 7 `
  --wait-seconds 15 `
  --report docs/evidence/notification-smoke-2026-08-13.json
```

脚本会依次检查：

1. 通知配置可读并确认渠道类型。
2. `POST /api/v1/notifications/{config_id}/test` 返回成功，或记录供应商返回的安全错误。
3. 投递历史在等待窗口内出现新记录，且状态为 `sent`。
4. 记录实际尝试次数，用于核对重试策略。

报告只保存脱敏 URL、配置 ID、渠道、状态、尝试次数和安全错误摘要；服务端日志、API 错误和投递历史也会过滤 URL 用户信息、Webhook 查询参数中的 `key`、`access_token`、`api_key`、`token`、`secret`、`sign/signature`、SMTP 密码和 Cookie。脚本不会读取或输出完整通知配置，因此不会把 Webhook、SMTP 密码或 Token 写入证据。

如果供应商异常文本包含完整 Webhook URL，系统会保留参数名但将敏感值替换为 `<redacted>`；新增或变更敏感参数时，必须同时补充服务端和验收脚本的脱敏回归测试。

## 验收要求

- SMTP：验证 TLS/STARTTLS、收件人收到唯一测试邮件，并确认失败重试不会产生多封邮件。
- 企业微信/钉钉：验证公网 DNS、TLS、签名时间窗口和供应商限流响应；确认 HTTP 429/5xx 会重试，4xx 配置错误不会重试。
- 记录脚本报告路径、目标环境、执行时间和供应商侧消息 ID（消息 ID 不写入平台日志时可放在外部验收记录）。
- 生产保留周期必须结合合规要求确认 `NOTIFICATION_DELIVERY_RETENTION_DAYS`，删除动作应纳入备份和审计策略。

该脚本不能替代供应商后台投递记录，也不能把“API 请求成功”直接当作“收件人已收到”。
