# Android Agent 真机闭环验收证据（2026-11-11）

## 结论摘要

在真实设备 **OPPO R11（序列号 `b01ac8cb`，Android 9，1080x1920）** 上完成：

| 验收项 | 结果 | 说明 |
| --- | --- | --- |
| M1 基本动作真实可用 | **通过** | tap / 精确断言 / back / swipe / wait_for 全部在真机执行 |
| M1 content-desc 定位 | **通过（本轮修复）** | 真机图标按钮只有 content-desc，原定位器不支持 |
| M2 设备租约互斥 | **通过** | 第二会话被 `device_busy` 拒绝 |
| M2 写门禁 | **通过** | 未接管时人工动作被拒 |
| M2 目标→操作→验证→轨迹 | **通过** | 5 次真实点击 + 独立断言 + 完整轨迹落库 |
| M2 会话收敛 | **通过（本轮修复）** | 原状态机无 paused→completed 路径 |
| M3 草稿编译可回放 | **通过（本轮修复）** | 原断言来源错误，草稿永远不可回放 |
| M3 回放前核对 | **通过** | `ready=True`，无阻断项 |
| 模型决策 | **未验证** | 无可用视觉模型凭据，用确定性规划器替代 |

> 诚实边界：**模型决策环节没有真实验证**。本轮所有"模型"输出由读取真实观察的确定性规划器产生，
> 用于验证协调器、租约、门禁、轨迹与草稿链路；不代表视觉模型在真机上的决策质量。

## 环境

| 项 | 值 |
| --- | --- |
| 设备 | OPPO R11，`b01ac8cb`，Android 9，1080x1920，density 480 |
| uiautomator2 | 3.2.1（适配层锁定版本） |
| 目标 App | `com.android.calculator2`（离线、可确定性断言） |
| 数据目录 | `.local-run/android-agent-m2-live-20261111/data`（现场库副本，不改动用户真实库） |
| 库版本 | 现场库 v16 → **v22** 真实升级 |

## 一、现场库副本升级（v16 → v22）

复制 `.local-data/atp.sqlite3`（1048576 字节，schema v16）到隔离目录后执行
`ensure_local_schema`，依次应用 v17→v22 迁移：

```
target: 22 | migrated to: 22
agent tables: ['android_agent_commands', 'android_agent_drafts', 'android_agent_events',
               'android_agent_replays', 'android_agent_sessions']
```

现有业务数据（项目、设备、模型配置）在升级后保持可读，未触发 `_assert_current_schema` 拒启。

## 二、M1 动作矩阵（真机）

```
dialog_dismissed: True
assert_15: True
assert_absent_correctly_false: True
exact_match_count: 1
foreground_after_back: com.oppo.launcher
swipe: ok
wait_for_found: True
wait_timeout_raised: True
empty_target_rejected: True
ACTION MATRIX: PASS
```

计算器按下 `7 + 8 =` 后屏幕文本包含 `15`，且 `15` 在 UI 树中唯一匹配。
不存在的值（`999999`）断言正确判假 —— 空预期不会误通过。

## 三、M2 真机闭环

```
session: 6 started
loop_status: needs_review
loop_reason: finish_proposed
planner_steps: ['clear', 'press_7', 'press_add', 'press_8', 'press_eq', 'finish']
assertion_15: True
session_status: completed
lease_released: True
command_count: 5
command_statuses: ['succeeded']
```

- 5 次真实设备点击，命令记录全部 `succeeded`；
- 轨迹事件按 seq 有序落库，含每次动作的 observation_id、node、expected、error_code；
- 独立断言由测试侧执行，不采信模型 `finish`；
- 会话收敛后租约释放。

## 四、安全性质（真机 + 真实库）

```
device_busy_rejected: True
device_busy_detail: 设备已被其他任务占用
write_requires_manual_control: True
```

同一设备第二个会话无法启动；未接管状态下人工写动作被门禁拒绝。

## 五、M3 草稿与回放核对

```
draft_replayable: True
draft_actions: ['start_app', 'click', 'click', 'click', 'click', 'click']
draft_source_seqs: [None, 4, 5, 6, 7, 8]
draft_assertions: [{'type': 'element_visible', 'resource_id': 'com.android.calculator2:id/eq'}]
draft_blocking: []
preview_ready: True
preview_codes: ['DRAFT_READY', 'CASE_MODULE_BINDING', 'DEVICE_BOUND']
```

启动应用固定注入为第一步（`source_seq=None`），其余步骤保留原始事件序号，
终态断言来自用户确认值。

## 六、真机验证发现并修复的缺陷

真机验证的价值集中体现在这里 —— 以下问题在单元测试全绿时依然存在：

| # | 缺陷 | 影响 | 修复 |
| --- | --- | --- | --- |
| 1 | `UiTarget` 只支持 resource_id/text | 真机大量图标按钮只有 content-desc（如计算器运算符），完全无法定位 | 增加 `content_desc` 定位，RPC mask 补 `0x40`，`UiNode` 增加 `desc_truncated` |
| 2 | `complete_session` 全仓库无调用者 | **会话永远到不了 completed**，M3 草稿永远缺 `session_completed` | 新增 `POST /sessions/{id}/complete` |
| 3 | 状态机缺 `paused → completed` | `needs_review`（finish 建议）无法收敛，只能取消 | 增加该边，语义为"用户确认终态断言" |
| 4 | 终态断言依赖模型 `finish.expected` | 契约明确禁止模型定义成功，草稿永远 `missing_final_assertion` | 会话新增 `terminal_assertions` 列（迁移 0089 / 本地 v22），由用户确认写入 |
| 5 | `finish` 事件 `action_status=not_executed` 被判 `step_failed` | 每次正常结束都产生假阻断项 | 终止建议轮不参与步骤失败判定 |
| 6 | 轨迹建议值可直接作为断言 | 模型可间接决定"成功"，违反清单第 9 节 | 无用户确认时标注 `assertion_not_user_confirmed` 并阻断 |
| 7 | `Literal` 未导入（`AgentCompleteRequest`） | 模型无法实例化，端点必然 500 | 补导入 |

第 2–6 项是 **M2 与 M3 之间的集成断裂**：两条链路各自测试通过，但组合起来不可达。
只有把真机、真实库、真实状态机串起来才会暴露。

## 七、未验证与风险

1. **视觉模型决策未验证**：库中 `ai_llm_configs` 的 API Key 由第三个 `APP_SECRET_KEY` 加密
   （当前 `.env` 与 M0 阶段的 `secrets.env` 均无法解密），因此未发起真实模型调用。
2. **回放执行未跑**：草稿与回放用例创建链路已就绪，但未在真机上执行一次完整回放运行。
3. **PostgreSQL 未验证**：全部在 SQLite 上完成。
4. **模拟器矩阵未验证**：仅一台真机。
5. 计算器为验证夹具，不代表业务 App 的定位复杂度。

## 八、复现命令

```bash
# 1) 隔离数据目录 + 现场库副本升级
python scripts/android_agent_m2_live_setup.py

# 2) 模型凭据可解密性诊断
python scripts/android_agent_m2_probe_model.py
python scripts/android_agent_m2_keycheck.py

# 3) M1 真机动作矩阵
python scripts/android_agent_m2_action_matrix.py

# 4) M2+M3 真机端到端
python scripts/android_agent_m2_live_e2e.py

# 5) 互斥 / 写门禁 / 收敛 / 草稿编译
python scripts/android_agent_m2_live_safety.py
```
