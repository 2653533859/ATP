# MinIO 与外部通知渠道验收

> 更新：2026-08-13

## 1. 真实 MinIO 数据集验收

`scripts/minio-dataset-acceptance.py` 只在随机生成的 `datasets/{project_id}/{dataset_id}/` 前缀中操作，并在结束时清理源对象和备份对象。它会验证：

- 25,000 行、10MB 以上数据通过 ATP 存储 helper 上传并按 SHA-256 回读一致；
- 孤儿对象 dry-run 不删除，显式 purge 才删除；
- 模拟数据库提交失败后，补偿 helper 删除本次上传对象；
- 超过 50MB 的对象在上传前被拒绝；
- 对象复制到独立备份 bucket、删除源对象后可恢复且摘要一致；
- 提供只读账号时，该账号能读取数据集对象但不能写入。

应用管理凭据继续读取 `MINIO_*` 配置。只读验收账号仅通过 `ATP_MINIO_READONLY_USER` 和 `ATP_MINIO_READONLY_PASSWORD` 注入，报告不会记录凭据。

```bash
ATP_MINIO_READONLY_USER='<read-only-user>' \
ATP_MINIO_READONLY_PASSWORD='<read-only-password>' \
backend/.venv/bin/python scripts/minio-dataset-acceptance.py \
  --rows 25000 \
  --backup-bucket atp-acceptance-backup \
  --report docs/evidence/minio-dataset-acceptance-YYYY-MM-DD.json
```

发布环境执行前必须确认 source/backup bucket 均为验收用途。脚本不会删除 bucket，也不会扫描或删除随机项目前缀以外的对象。只读账号未配置时权限检查显示 `SKIP`，不能据此关闭权限门禁。

## 2. SMTP、企业微信与钉钉验收

两个脚本分工不同，发布证据需要同时保留：

| 脚本 | 前置条件 | 覆盖范围 |
| --- | --- | --- |
| `scripts/notification-channel-smoke.py` | 运行中的 ATP 服务 + 已配置的项目通道 | 真实 API 认证、`POST /notifications/{id}/test`、投递历史行核对 |
| `scripts/notification-channel-acceptance.py` | 仅需渠道凭据，无需运行服务 | 真实性能摘要正文逐字段核对 + 真实供应商送达 |

`scripts/notification-channel-acceptance.py` 通过生产入口 `send_notification_channel` 发送一条包含 RPS、P95/P99、错误率、阈值状态和触发原因的真实性能摘要，因此渠道配置校验和重试策略与线上一致。Webhook 会先执行公网 URL/DNS 校验；Webhook、签名和 SMTP 密码不会进入命令行或报告。

```bash
# SMTP：SMTP_* 继续从应用配置读取
ATP_ACCEPTANCE_SMTP_RECIPIENTS='qa@example.com' \
backend/.venv/bin/python scripts/notification-channel-acceptance.py \
  --channel smtp --report docs/evidence/notification-smtp-YYYY-MM-DD.json

# 企业微信
ATP_ACCEPTANCE_WECOM_WEBHOOK_URL='<sandbox-webhook>' \
backend/.venv/bin/python scripts/notification-channel-acceptance.py \
  --channel wecom --report docs/evidence/notification-wecom-YYYY-MM-DD.json

# 钉钉；启用加签时额外注入 ATP_ACCEPTANCE_DINGTALK_SECRET
ATP_ACCEPTANCE_DINGTALK_WEBHOOK_URL='<sandbox-webhook>' \
ATP_ACCEPTANCE_DINGTALK_SECRET='<sandbox-secret>' \
backend/.venv/bin/python scripts/notification-channel-acceptance.py \
  --channel dingtalk --report docs/evidence/notification-dingtalk-YYYY-MM-DD.json
```

Webhook 报告 `passed` 表示供应商返回成功码；SMTP 报告 `passed` 表示 SMTP 服务接受邮件。报告中的 `content_checks` 按“标签 + 取值”逐字段实测，不是固定值；任一字段为 `false` 时脚本返回非零状态。发布证据还必须保留接收端消息或供应商日志。缺少凭据、DNS 不可解析、HTTP/供应商错误或正文缺字段均返回非零状态，不能记为通过。

## 3. 邮件链路本地自检（不替代供应商送达）

在拿到供应商凭据之前，可以先用 `scripts/notification-smtp-link-check.py` 验证邮件渠道自身的链路。它在 `127.0.0.1` 上启动一个一次性 SMTP 接收端，走生产入口 `send_notification_channel` 真实完成一次 SMTP 会话，然后解析收到的原始邮件：

```bash
backend/.venv/bin/python scripts/notification-smtp-link-check.py \
  --report docs/evidence/notification-smtp-link-check-YYYY-MM-DD.json
```

覆盖范围：SMTP 信封（`MAIL FROM`/`RCPT TO`）、收件人规范化结果、MIME multipart 结构、`To` 头显示名保留，以及正文六个性能字段。

明确不覆盖：供应商侧送达、反垃圾与退信、DKIM/SPF、TLS/SSL 链路、限流与重复投递。因此报告状态固定为 `local_link_only`，永远不会写出 `passed`；该脚本不能用于关闭外部渠道门禁。首次执行结果见 [`evidence/notification-smtp-link-check-2026-08-20.json`](evidence/notification-smtp-link-check-2026-08-20.json)，最新复核见 [`evidence/notification-smtp-link-check-2026-08-24.json`](evidence/notification-smtp-link-check-2026-08-24.json)。

## 4. 通知投递目标校验规则

配置校验与实际投递共用 `notifier.normalize_email_recipients` 和同一套 Webhook 规则，保证“保存成功”等于“可投递”：

- 邮件：允许 `Name <addr@example.com>` 显示名格式，自动跳过空白条目；拒绝换行注入和缺少 `@` 或缺少本地部分/域名的地址；全部条目为空时拒绝。
- Webhook：配置阶段拒绝非 `http`/`https`、带用户名密码、`localhost` 和字面内网/保留地址；投递阶段再解析域名复核公网地址，DNS 解析发生在线程池中，不阻塞事件循环。
- 因此域名解析到内网的自建网关无法用于通知投递。目标环境若必须使用内网网关，需要先提供公网可解析的出口地址，不能通过配置绕过校验。

历史无效配置可以先禁用或改名，但重新启用、切换渠道或更新配置前必须修复投递目标。
