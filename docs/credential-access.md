# ATP 发布机账号与密码取回

本页记录 2026-09-24 在 `192.168.3.196` 核对的账号和密码文件位置。
这两个账号的当前密码保存在服务器受限文件中；本页不保存密码、令牌或密码哈希。

| 环境 | 用途 | 用户名 | 密码文件（服务器绝对路径） |
| --- | --- | --- | --- |
| K3s 业务库 `atp-single-node` | ATP 管理员 | `parado` | `/root/atp-credentials/parado-password-20260924` |
| K3s 业务库 `atp-single-node` | 每日 SLO canary 专用测试账号 | `atp-slo-canary` | `/etc/atp-slo-canary/password` |

在发布机上以有权限的管理员身份取回密码：

```bash
sudo cat /root/atp-credentials/parado-password-20260924
sudo cat /etc/atp-slo-canary/password
```

`parado` 密码于 2026-09-24 重置；重置后数据库哈希校验及真实登录接口均通过。
密码文件由 root 拥有，权限为 `0600`，父目录 `/root/atp-credentials` 为 `0700`。
canary 文件同样由 root 拥有，权限为 `0600`，通过 systemd `LoadCredential` 提供给定时服务。

两套账号不能混用。`FIRST_ADMIN_PASSWORD` 仅在首次初始化时创建管理员，旧部署的引导配置不是当前 `parado` 密码。独立 Hermes 验收栈也不是这里的 K3s 业务库。以后轮换密码时，应同步更新此处的文件路径和日期；不要把密码值写入 Git、日志或工单。
