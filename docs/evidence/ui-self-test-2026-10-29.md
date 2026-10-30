# ATP 界面补充自测（2026-10-29）

## 范围与结论

使用用户已连接的 Chrome 扩展控制通道完成实际页面操作。本机 browser-harness 已更新为 0.1.13，但直接 CDP 通道仍返回 403；扩展通道可用，没有更改浏览器安全设置。

后端采用独立 SQLite/对象目录与临时管理员，前端通过 Vite 的 `VITE_ATP_LOCAL_MODE=true` 和代理连接该后端。测试页面为 `127.0.0.1:5175`，后端为 `127.0.0.1:64427`，未使用原有 8000 服务的数据。

共记录 **20 项检查：18 项通过，2 项失败**。这是 UI 补测结果，不替代 10 月 28 日尚未通过的后端测试门禁。

## 通过项

1. 登录空表单显示用户名/密码必填提示。
2. 错误密码显示“用户名或密码错误”。
3. 正常登录后进入仪表盘，可见已准备的运行结果。
4. 服务器版前端接本地后端时显示模式不一致保护；使用正确的本地模式前端后正常进入。
5. 项目中心展示隔离测试项目。
6. 新建项目时校验必填名称。
7. 经 UI 新建 `UI Selftest 20261029`，刷新后仍存在。
8. 从项目卡片正文进入项目概览。
9. 项目用例列表显示 `Selftest HTTP`。
10. 从 UI 点击 Run，确认执行环境，产生 Run #2 并进入 `passed`。
11. 运行详情显示 1 个通过步骤、HTTP 200、请求/响应及断言通过；请求目标为测试创建的本地 HTTP 服务。
12. 运行详情显示 Outbox Pending 状态。
13. HTML 报告下载成功（2535 字节），包含 `Live HTTP` 步骤及 passed 结果。
14. JUnit XML 下载并解析成功：1 个测试、0 failures、0 errors。
15. PDF 报告下载成功（61033 字节），校验 `%PDF-` 文件头；未做逐页排版验收。
16. 同步中心展示 2 条待同步、0 条已同步，与准备运行及 UI 新运行一致。
17. 从用户菜单退出后返回登录页。
18. 退出后访问 Run #2，自动跳转到带 redirect 参数的登录页。

浏览器日志未发现 error 级消息，存在 `cloud_sync.*` 翻译键缺失与语言回退 warning。HTML 下载事件等待曾超时，但实际文件已落入 Downloads，随后以文件内容确认成功，未将工具事件超时误判为产品导出失败。

## 两项失败

### P2：项目卡片标题被按钮遮挡，点击标题误触导出

- 在实际浏览器约 929 像素宽的窗口中，项目卡片标题区域与 Edit/Copy/Export/Archive/Delete 操作区重叠。
- 在项目中心点击 `Selftest API` 标题，没有进入概览，而是出现 `Project configuration exported`，焦点落在 Export 按钮。
- DOM 验证：标题矩形 `x=503.33, y=347.06, width=67.63, height=17`，中心点命中元素文字为 `Export`。点击卡片正文后则正常进入 `/projects/2/overview`。
- 关联代码：`frontend/src/views/project/ProjectList.vue` 的卡片 title/extra 区域（45–87 行）。
- 建议：操作区换行时独占行或改为紧凑菜单，保证标题可见且可点击，并增加窄窗口真实布局回归。
- 截图：`.local-run/ui-selftest-20261029/project-header-overlap.png`。

### P2：未配置云端时仍提示“已完成同步”

- 后端没有配置 `CLOUD_SYNC_URL`/API Key，自动同步关闭；同步中心仍有 2 条待同步记录。
- 点击 Sync to Cloud，两次均显示成功样式的“已完成同步：成功 0 条，失败 0 条”，队列依然待同步 2、已同步 0。
- `frontend/src/views/cloud-sync/CloudSyncDashboard.vue:408–418` 未检查返回的 `status`，直接调用 `message.success`；后端未配置时返回 `status=disabled`。
- 建议：区分 disabled、成功与失败；未配置时解释配置缺失，不显示完成成功提示。
- 队列截图为 `sync-disabled-success.png`；成功提示文本由实际页面 accessibility 状态及 `ui-results.json` 记录，截图仅用于核对队列状态。

## 证据与清理

证据目录：`.local-run/ui-selftest-20261029/`，包括 `ui-results.json`、`browser-logs.json`、`dashboard.png`、`projects.png`、`project-header-overlap.png`、`run-detail.png`、队列截图与三个实际导出文件。

测试账号密码仅用于该隔离服务，页面登录后已删除临时凭据文件；没有将凭据写入报告或源码。测试结束已退出页面会话并关闭隔离服务，保留测试数据库与证据供追溯。

未连接真实云端同步、未进行真机或 LLM 验收；本次未修改业务源码。

上述两项问题已在后续修复，代码与复验证据见 [两项界面修复记录](ui-fixes-2026-10-29.md)。此文件保留修复前的观测结果。
