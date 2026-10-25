# M1 Android 镜像录制与用例草稿衔接

日期：2026-10-25。状态：代码与定向验证完成；真机录制和回放待 M3 验收。

## 实现

- App 工作台的设备镜像可显式开始录制，点按、滑动、输入和按键形成 ATP 既有低代码步骤。截图模式点按先查元素目标，保留资源 ID 与坐标回退；滑动保留屏幕尺寸供回放缩放。Scrcpy 模式使用实际画面坐标录制。
- 失败的截图模式操作不加入草稿；关闭镜像或主动丢弃时不写入正式用例。录制完成后在 Android 用例抽屉中编辑并由用户显式保存。
- 工作台先释放设备租约，再打开用例抽屉，由编辑器按现有逻辑重新获取租约。释放失败时草稿留在当前项目，可重试打开；切换项目不会把草稿带到另一项目。

## 验证

- `npx vitest run src/views/device/components/DeviceMirrorModal.spec.ts src/views/workbench/AppWorkbenchView.spec.ts src/views/case/AndroidCaseDrawer.spec.ts --silent`：20 passed，覆盖成功点按、失败操作、Scrcpy 画布坐标与宽高映射、草稿传递、租约释放失败和抽屉初始化。
- `npm run type-check`：通过。

## 真机待验收

- 需在 Android 真机上分别试 Scrcpy 与截图降级模式，确认录制坐标、输入/按键、保存、回放及报告。WebSocket 发送成功仅表示操作消息已提交，不能替代真机确认实际动作成功。
