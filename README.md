# ATP
一个自动化测试框架，兼顾 Web 端测试、接口测试、手机 UI 测试等场景。

## 通知配置

4.5 阶段当前支持三种通知渠道：
- SMTP 邮件
- 企业微信机器人 Webhook
- 钉钉机器人 Webhook

使用前请先在根目录 `.env` 中配置 SMTP 相关变量：
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_SSL`
- `SMTP_TLS`

其中：
- 企业微信与钉钉使用项目级通知配置页内填写的 Webhook 地址。
- 钉钉机器人如启用签名，还需要在通知配置中填写 `secret`。
- 当前通知会在测试套件和测试计划执行完成后触发；单用例通知暂不在本阶段范围内。
