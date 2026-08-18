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

`scripts/notification-channel-acceptance.py` 发送一条包含 RPS、P95/P99、错误率、阈值状态和触发原因的真实性能摘要。Webhook 会先执行公网 URL/DNS 校验；Webhook、签名和 SMTP 密码不会进入命令行或报告。

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

Webhook 报告 `passed` 表示供应商返回成功码；SMTP 报告 `passed` 表示 SMTP 服务接受邮件。发布证据还必须保留接收端消息或供应商日志，并确认六类性能字段可见。缺少凭据、DNS 不可解析、HTTP/供应商错误或正文缺字段均返回非零状态，不能记为通过。

通知配置 API 现在会拒绝空收件人、空 Webhook 和非法 Webhook URL；历史无效配置可以先禁用或改名，但重新启用、切换渠道或更新配置前必须修复投递目标。
