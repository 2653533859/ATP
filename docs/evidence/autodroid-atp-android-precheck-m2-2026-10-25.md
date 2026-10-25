# M2 Android 设备级执行前预检

日期：2026-10-25。状态：代码与定向验证完成；真机环境待 M3 验收。

## 实现

- **核心模型与预检服务**：新增 `app/schemas/android_precheck.py` 与 `app/services/android_precheck.py`。
  - **设备与平台**：检查目标设备序列号有效性、在库状态、在线状态、iOS 平台防呆拦截（`UNSUPPORTED_PLATFORM`）以及数据库设备租约冲突（`DEVICE_LEASE_CONFLICT`，租约持有者调用时放行）。
  - **环境与连通**：通过 `adb get-state` 做非侵入式 ADB 连通与授权检查（`DEVICE_UNAUTHORIZED`、`DEVICE_OFFLINE`）；预检本身不操作业务 App。
  - **应用映射与包名**：检查关联 APK 是否存在、所属项目是否匹配（`APK_PROJECT_MISMATCH`），以及启动/停止/权限控制步骤是否缺少目标应用包名（`MISSING_APP_PACKAGE`）。
  - **定位器与动作**：逐步验证动作支持度（`UNSUPPORTED_ACTION`）、点击/长按缺少定位或坐标（`MISSING_LOCATOR`）、滑动方向未知或坐标不全（`INVALID_SWIPE_DIRECTION`）、输入缺少内容（`MISSING_INPUT_CONTENT`）、按键缺失（`MISSING_KEY`）、断言参数缺失等。
  - **变量声明**：扫描步骤中 `{{VAR}}` 占位符，检查是否在运行变量或关联环境中声明，未声明项提示 `UNDEFINED_VARIABLE` 警告。
- **执行入口复核**：在 `app/worker/executors/android_lowcode_executor.py` 的 `run_android_lowcode` 中，获取设备租约后立即触发预检校验。若发现阻断性 `FAIL` 问题，立即停止执行并安全释放租约，防止录制/保存后设备状态变化。
- **API 与前端集成**：
  - 暴露 `POST /api/v1/cases/{case_id}/precheck` 与草稿端点 `POST /api/v1/cases/android/precheck`。
  - 在 `frontend/src/views/case/AndroidCaseDrawer.vue` 底部新增「执行预检」按钮及诊断结果对话框，结构化呈现各步骤错误码、问题描述与可修复提示。
  - App 工作台发起 Android 用例前校验预检结果，并确认当前所选设备与用例保存的执行设备一致。

## OMP CLI 审查与修复

- 修复草稿端点被动态路由遮挡、用例所属模块缺失时跳过权限检查，以及环境 ID 跨项目引用。
- ADB 检查移至线程执行；无法确认时返回明确诊断。API 主机缺少 ADB 时给出警告，Worker 执行前复核时阻断，避免把未知状态误报为在线。
- 应用控制步骤按执行器真实行为要求 `params.package`，不把用例级包名当作隐式参数；补充所选设备核对与回归测试。
- 复审中的“前端 API/schema 缺失”和“非对象步骤无诊断”为截取 diff 导致的误判，已核对实际定义和 `UNSUPPORTED_ACTION` 分支。

## 验证

- **后端测试**：`backend/.venv/bin/pytest -q backend/tests/services/test_android_precheck.py backend/tests/worker/test_android_lowcode_executor.py`，**62 passed**。
  - 覆盖设备缺失、未注册、iOS 平台拦截、离线状态、租约冲突与本人放行；
  - 覆盖 APK 缺失、项目不匹配、包名缺失、未定义变量警告；
  - 覆盖定位器/动作参数完整性、预检通过 Happy Path；
  - 覆盖执行器在获得租约后的安全阻断与租约释放；
  - 覆盖两个 API 端点的鉴权与调用。
- **前端测试**：`npm test -- src/views/case/AndroidCaseDrawer.spec.ts src/views/device/components/DeviceMirrorModal.spec.ts src/views/workbench/AppWorkbenchView.spec.ts src/utils/androidRecording.spec.ts`，**4 个文件、25 passed**。
- **前端类型检查**：`npm run type-check`（`vue-tsc --noEmit`）通过，0 错误。
- **代码规范**：`ruff check` 针对后端改动文件全部通过。

## 真机待验收

- 需在一台真实 Android 真机上验证设备在线、租约竞争、预检通过与阻断提示、以及进入回放的全流程，留待 M3 统一真机验收。
