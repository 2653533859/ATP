# iOS/Appium 验收 Runbook

仓库新增 `scripts/ios-appium-acceptance.py`，用于 macOS Worker 上的显式 Appium 验收。默认命令只检查 Appium `/status` 的 `ready=true`；这不能代表 iPhone/Simulator 或 XCUITest 已可执行。

```bash
# 仅检查 Appium 服务
python scripts/ios-appium-acceptance.py \
  --appium-url http://127.0.0.1:4723 \
  --report docs/evidence/ios-appium-status-<date>.json

# 显式创建并销毁 XCUITest 会话，按需执行低代码步骤和采集附件
python scripts/ios-appium-acceptance.py \
  --appium-url http://127.0.0.1:4723 \
  --udid '<iphone-or-simulator-udid>' \
  --device-name '<device-name>' \
  --platform-version '<ios-version>' \
  --bundle-id '<bundle-id>' \
  --session-smoke \
  --steps-file /secure/path/ios-smoke-steps.json \
  --artifact-dir .local-run/ios-appium-artifacts \
  --record-video \
  --collect-syslog \
  --report docs/evidence/ios-appium-session-<date>.json
```

步骤文件必须是最多 100 项的 JSON 数组，支持与 iOS 低代码执行器一致的 `click`、`input`、`assert_text`、`assert_element`、`wait`、`screenshot`、`back`、`start_app`、`stop_app`、`get_source`、`tap` 和 `swipe`。报告不写入输入文本、UDID、完整 Appium URL、syslog 或二进制内容；附件只记录文件名、类型、大小和 SHA-256。

Appium URL 不允许用户名、密码、查询参数或片段。真实验收还必须记录 macOS/Xcode/Appium/XCUITest/WDA 版本、设备类型、签名/Provisioning Profile 状态、`ios` 队列、设备租约和最终 ATP run 结果；Windows/Linux 上的协议桩或 status-only 结果不能替代真实 macOS/iPhone/Simulator 证据。

## macOS Worker 启动前检查

仓库提供 `scripts/macos-ios-worker.sh`，把 Appium/XCUITest 前置检查和 Celery 队列隔离固化为一个入口：

```sh
cp config/startup-profiles/macos-ios-worker.env.example .env.ios-worker
set -a; . ./.env.ios-worker; set +a
sh scripts/macos-ios-worker.sh doctor
sh scripts/macos-ios-worker.sh start
```

`doctor` 会检查 Python、Celery、Appium、Xcode、`xcrun` 和已安装的 XCUITest Driver，并列出可用模拟器；`start` 只监听 `ios` 队列，不会启动 ADB 或性能任务。真实 iPhone 仍需信任开发者证书、可用 WebDriverAgent 和签名应用后再执行 `--session-smoke`。
