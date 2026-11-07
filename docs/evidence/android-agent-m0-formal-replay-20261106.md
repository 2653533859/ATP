# Android Agent M0：正式低代码执行器接入租约续期、取消控制与严格回放

日期：2026-11-06。续接 [UIAutomator 无模型回放现场验证](android-agent-m0-uiautomator-replay-20261106.md)。本记录说明“实验脚本回放”如何落到平台正式链路：`TestCase(android, config.steps)` → `POST /cases/{id}/run` → `TestRun` → Android 低代码执行器 → 步骤结果、截图、HTML/PDF/JUnit 报告。

## 结论与边界

- 已实现并通过自动化回归：执行器每步续期设备租约、写设备前复核取消与租约期限；`POST /runs/{id}/stop` 支持 Android 低代码运行；新增用例级 `strict_replay` 模式，由 UIAutomator RPC 执行精确定位点击、直接中文输入并回读、条件等待和精确断言。
- 已在隔离的本地模式后端（SQLite、独立数据目录）完成无设备冒烟：建用例 → 预检阻断严格模式坐标步骤 → 本地队列执行 → 终态运行再次停止返回 409。
- **真机正式 TestRun 尚未完成**：准备开跑时 OPPO R11 已从 `adb devices` 消失（此前为 USB 在线），需重新连接后执行下文验收脚本。本记录不声明真机通过。
- 不包含：持久会话协调器、模型循环、草稿编译、模拟器与第二个可重置 App 的矩阵（仍属 M0 余项及 M2/M3）。

## 实现内容

| 位置 | 变更 |
| --- | --- |
| `backend/app/services/android_agent/strict_replay.py`（新） | `StrictReplayEngine`：`click` 唯一精确匹配（resourceId/text/className/contentDesc），控件不可点击时要求可点击祖先，执行前 `count` 复核，发送后异常记为“结果未知”且不重发；`input` 复用适配层 `replace_text`（setText + 回读精确比对），拒绝未解析的 `{{变量}}`；`wait_until` 按 visible/absent 轮询，超时（100–60000 ms）即失败，每轮检查取消；`assert_element` 支持 present/absent、`count` 精确数量、`min_count`；`assert_text` 为“存在文本精确相等的节点”。`validate_strict_step` 供预检与执行共用 |
| `backend/app/worker/executors/android_lowcode_executor.py` | `AndroidRunControl`：每步开始前检查取消并调用 `heartbeat_device_lease` 续期；续期失败 → 运行 `error`（“设备租约已失效”）；本地期限 = TTL − 30 秒，写设备前到期即阻断。取消 → 运行 `cancelled`，当前步骤记为 cancelled，后续步骤不执行；固定等待切成 ≤1 秒分片以响应取消。`strict_replay: true` 时定位类步骤交给严格引擎，`press_key/start_app/stop_app/wait/screenshot/swipe` 仍走原路径，其他动作直接失败；`wait_until` 仅严格模式可用。设备矩阵子运行同时响应自身与父运行取消，父运行聚合 `cancelled`。`result_summary.execution_control` 记录严格模式、目标包、租约心跳次数、是否取消/失租、已执行步数。运行结束总会释放租约并清除取消信号 |
| 同上（旧路径缺陷） | `assert_text`/`assert_element` 空预期、`assert_visual_element` 无预期文本或模板时不再判通过 |
| `backend/app/api/v1/cases/runs.py` | 停止入口扩展到 Android 低代码用例（config 含 `steps`）；Android 脚本用例和其他类型仍返回 409 |
| `backend/app/worker/tasks.py` | 开跑前已请求停止的 Android 低代码运行直接记为 cancelled，不占用设备 |
| `backend/app/services/android_precheck.py` | 严格模式下所有步骤按 `validate_strict_step` 校验（`STRICT_*` 错误码）；非严格模式使用 `wait_until` 报 `WAIT_UNTIL_REQUIRES_STRICT` |
| 前端 | 运行详情页对运行中 Web/Android 运行显示“停止执行”（二次确认）；用例抽屉低代码模式增加“严格回放”开关；步骤编辑器新增“条件等待”，严格模式下断言元素可填文本/类名/期望/精确数量；标准步骤摘要与中英文文案同步 |

租约续期与设备租约服务（`device_leases.py`，SQLite 时区比较修复）由并行会话负责，本变更只依赖 `acquire/heartbeat/release` 的既有签名与 `DeviceLeaseConflict` 语义。

### 已知边界

- 单个固定 `wait` 超过约 14.5 分钟（默认 TTL 900 秒减 30 秒余量）会因本地租约期限到期而在下一次写设备前失租报错。旧行为是租约静默过期、设备可能被他人占用，现为更严格的失败。
- 取消是协作式：已发送的点击/输入不会撤回，当前 RPC 返回后才停止；严格模式 `wait_until` 每轮观察前检查取消。
- 服务器模式取消信号在 Redis 不可用时视为未取消（沿用 Web 停止的既有语义）；本地模式为进程内集合，API 与本地执行队列同进程。
- 严格模式不支持 `long_click`、`rotate`、权限/网络切换等动作，预检与执行均会阻断。

## 自动化验证

| 命令 | 结果 |
| --- | --- |
| `pytest backend/tests/services/test_android_strict_replay.py` | 32 passed |
| `pytest backend/tests/worker/test_android_lowcode_run_control.py` | 12 passed（续期、中途取消、长等待取消、开跑前取消、续期失败、本地期限、矩阵父取消、严格分派、空断言） |
| `pytest backend/tests/worker/test_android_lowcode_executor*.py` | 93 passed |
| `pytest backend/tests --ignore=backend/tests/integration`（仓库内 basetemp） | 4248 passed, 3 skipped |
| `ruff check` / `ruff format --check` / `mypy`（项目配置） | 通过 |
| `cd frontend && npm run type-check` | 通过 |
| `cd frontend && npm run test` | 86 files / 439 tests passed |

## 平台内冒烟（无设备）

隔离后端：`ATP_LOCAL_MODE=true`，数据目录 `.local-run/android-replay-e2e/data`，端口 8011，随机管理员与密钥（本机文件，不提交）。脚本 `.local-run/android-replay-e2e/e2e.py smoke`：

- 预检返回 `DEVICE_NOT_FOUND`、`STRICT_SELECTOR_MISSING`（坐标点击在严格模式被阻断）；
- 触发运行经本地队列执行，终态 `error`（设备未注册），未执行任何步骤；
- 对终态运行调用停止返回 409。

## 真机验收（待设备重连后执行）

```bash
# 1. 启动隔离后端（见 .local-run/android-replay-e2e/，端口 8011）
# 2. 严格回放：启动汽水音乐 → 两轮「首页 → 搜索晴天 → 精确核对结果 → 返回首页」共 29 步，导出 HTML/JUnit
backend/.venv/Scripts/python.exe -I .local-run/android-replay-e2e/e2e.py replay
# 3. 取消：等待首页后进入 30 秒长等待，运行中调用 POST /runs/{id}/stop，核对 cancelled、后续点击未执行、设备恢复 online
backend/.venv/Scripts/python.exe -I .local-run/android-replay-e2e/e2e.py cancel
```

通过标准：回放运行 `passed`，29 步全部 passed 且每步有截图，`execution_control.lease_heartbeats` 等于已执行步数；HTML/JUnit 导出 200；默认输入法不变。取消运行 `cancelled`，第 4 步未执行，停止到终态 ≤ 2 秒，设备状态恢复 `online`。结果写入 `.local-run/android-replay-e2e/results/`，确认后补记到本文件。
