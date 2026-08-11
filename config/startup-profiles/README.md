# 启动配置档案

这些文件只提供启动模板，不包含真实密码。先复制需要的模板，并填写实际值：

```powershell
Copy-Item .\config\startup-profiles\local-all.env.example .\config\startup-profiles\local-all.env
Copy-Item .\config\startup-profiles\remote-infra.env.example .\config\startup-profiles\remote-infra.env
Copy-Item .\config\startup-profiles\android-agent.env.example .\config\startup-profiles\android-agent.env
```

实际 `.env` 文件已加入 `.gitignore`。使用 `android-agent` 或 `remote-infra` 时，数据库、Redis、MinIO 地址和加密密钥必须与公网 ATP 后端匹配。
