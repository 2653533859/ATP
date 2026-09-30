# Windows 本地 Web 录制修复

- 移除旧的本地模式录制写接口拦截，接通已有 API 进程内 Playwright 录制和本地目录文件存储。
- 本地录制起始地址复用浏览器网络策略，允许 localhost/127.0.0.1/::1；仅接受 HTTP/HTTPS。服务器仍使用原有公网地址校验。
- 重启本地服务后，通过真实接口在 Chromium 打开本机登录页并停止：状态 recording → stopped，1 条 goto 步骤，Trace/HAR/报告共 3 个文件，artifact_error 为 None。
- 修改文件 Ruff 检查通过。本次未执行新增测试或正式服务器现场验收；交互点击录制及录制后执行用例仍需后续验收。
