# Android Agent M1–M3 实施证据（2026-11-11）

## 范围

本轮按[实施清单](../plans/2026-11-06-android-agent-implementation-backlog.md)补齐 M1–M3 的**代码与自动化验证**：

| 阶段 | 本轮动作 | 结论 |
| --- | --- | --- |
| M1 A10–A13 | 复核 11-10 已落地实现，补记进度 | 代码完成，真机矩阵未验收 |
| M2 A20–A23 | 数据模型/迁移、协调器、API、最小控制页 | 代码完成；模型循环未接入，真机闭环未验收 |
| M3 A30–A33 | 轨迹编译、草稿版本、独立回放、幂等保存 | 代码完成；真实设备回放待补 |

## 交付物

### 后端

| 文件 | 说明 |
| --- | --- |
| `backend/app/services/android_agent/compiler.py` | 轨迹→低代码草稿编译，纯函数、可重复得到同一 `content_hash` |
| `backend/app/services/android_agent/replay.py` | 冻结快照、回放前核对、回放用例与 `TestRun` 创建、验证资格判定 |
| `backend/app/models/android_agent.py` | 新增 `AndroidAgentDraft`、`AndroidAgentReplay` |
| `backend/app/api/v1/android_agent.py` | 新增 7 个端点（草稿 CRUD、replay-preview、replays、publish），共 13 条路由 |
| `backend/alembic/versions/20261111_0088_add_android_agent_draft_replay_tables.py` | 云端 PostgreSQL 迁移 |
| `backend/app/core/local_schema.py` | 本地 SQLite v20→v21，与 Alembic 字段一致 |

设计约束落实情况：

1. **不伪造成功**：只有 `passed` 且 `draft_version`/`content_hash` 与当前草稿一致的回放才允许保存；`finish` 不生成操作步骤，终态断言来自用户确认的成功条件。
2. **不写明文**：输入步骤只保存 `${var}` 引用与 `value_ref`，模型与草稿均不持有敏感值。
3. **不自动继续**：`recover_orphaned_sessions` 把非终态会话收敛为失败，不重放设备动作。
4. **幂等键唯一**：回放 `(draft_id, idempotency_key)` 与保存按 `published_case_id` 双重防重。
5. **回放不复用 Agent 决策**：回放用例配置固定 `strict_replay: true` 且携带 `android_agent.agent_replay`，由现有 Android 低代码执行器执行。

### 前端

| 文件 | 说明 |
| --- | --- |
| `frontend/src/api/androidAgent.ts` | 会话/事件/控制/草稿/回放/保存类型与请求封装 |
| `frontend/src/views/workbench/AndroidAgentPanel.vue` | 最小控制页：任务表单、控制栏、轨迹事件、草稿与回放入口 |
| `frontend/src/views/workbench/AppWorkbenchView.vue` | 挂载面板并摊平模块树供回放选择归属 |
| `frontend/src/locales/{zh-CN,en-US}.ts` | 新增 `android_agent` 文案段（中英各 52 条） |

## 验证记录

### 后端定向回归

```
python -m pytest backend/tests/api/test_android_agent_draft_replay.py
10 passed

python -m pytest backend/tests/migrations backend/tests/services/test_local_schema.py
100 passed
```

### 后端全量

```
python -m pytest backend/tests --ignore=backend/tests/integration
1 failed, 4341 passed, 3 skipped        # 唯一失败是本轮新增迁移头断言，已同步修正
```

修复后 `backend/tests/migrations` 全绿。

> 环境注意：本机 shell 注入了 `HTTP_PROXY=http://127.0.0.1:3067` 且 `NO_PROXY` 含 `[::1]`，httpx 解析 `[::1]` 端口报错，会让 11 个与代理无关的用例（数据集准备、富卡片通知、工作流 DAG/调试器、iOS WDA 探测）误报失败。去掉代理环境变量后 30 passed，属环境噪声而非代码缺陷。

### 前端

```
npx vue-tsc --noEmit          # 0 error
npx vitest run                # 88 files / 457 tests passed
```

### 真实契约冒烟

```
python scripts/android_agent_m3_smoke.py
{"ok": true, "routes": 13, "openapi_version": "3.1.0"}
```

## 未完成与风险

1. **M2 门槛未达成**：协调器目前只有状态机与控制面，尚未把 `single_step.py` 的模型循环接入持久协调器，没有"目标→真实操作→验证→轨迹"的真机闭环。
2. **M3 真机回放未验证**：回放链路只做到用例与 `TestRun` 创建与派发，真实设备上的严格回放（重置后 3 次通过率）未有证据。
3. **PostgreSQL 行为仅推断**：草稿/回放表在 PostgreSQL 上只做了迁移脚本审查，未连接真实库验证唯一约束与并发。
4. **设备访问策略未决**：实施清单第 8 节要求 M0 明确设备访问策略；当前仍按项目 editor 放行，未按设备归属授权。
5. **凭证与审计**：人工接管动作已留事件，但未写入系统审计表。

---

## 追加：M2 模型循环接入（同日第二轮）

### 交付

| 文件 | 说明 |
| --- | --- |
| `backend/app/services/android_agent/loop.py` | 持久协调器驱动的模型循环：每轮观察 → 模型 → 校验 → 再查代次与租约 → 串行执行 → 验证 → 写事件 |
| `backend/app/services/android_agent/coordinator.py` | 新增 `dispatch_prepared_command` 人工动作门禁；接管控制器统一为 `manual`；恢复错误码改为 `system_restarted_needs_review` |
| `backend/app/api/v1/android_agent.py` | 新增 `POST /sessions/{id}/run`（阻塞至收敛），装配视觉模型配置与设备适配层 |
| `frontend/src/views/workbench/AndroidAgentPanel.vue` | 控制栏新增"执行一轮"，循环执行期间暂停轮询 |
| `backend/tests/services/test_android_agent_loop.py` | 10 项循环回归 |
| `backend/tests/api/test_android_agent_run_api.py` | 4 项装配与门禁回归 |

### 关键安全性质（均有回归覆盖）

1. 未知执行结果（`*_outcome_unknown`）**只标记待核查，不重发**——测试断言模型只调用一次、动作只派发一次。
2. 模型请求期间被暂停时，代次变化让旧决策失效，**动作不发生**。
3. 会话停止/接管后门禁拒绝写入（`write_cancelled` / `manual_control_active`）。
4. 后端重启后 `recover_orphaned_sessions` 收敛为 `system_restarted_needs_review`，**不自动继续设备操作**。
5. 输入步骤只落 `value_ref`，不落明文值。

### 审查中修掉的缺陷

| 缺陷 | 影响 | 处置 |
| --- | --- | --- |
| 预算判定把"本轮未执行的动作"提前计入 | 5 步预算只跑 3 步就停 | 改为只按已落库用量判断 |
| 未执行动作的终止轮不记模型用量 | 成本统计偏低 | 新增 `record_model_usage` 记账 |
| `decision.target` 无 target 动作时解引用 | 潜在 AttributeError | 改用 `_target_node` 安全取值 |
| 枚举状态未归一化 | SQLite 返回枚举成员时门禁必然拒绝 | 统一 `_normalize_status` |
| 手动动作控制器值混用 `manual`/`human` | 手动动作永远不满足门禁 | 统一 `manual`，读取兼容 `human` |
| 人工动作直接写 `executed` 无门禁 | 绕过控制权检查 | 改为 `prepared` + `dispatch_prepared_command` |
| 前端轮询与阻塞循环抢状态 | 可能显示中间态 | 循环执行期间跳过轮询 |
| `HTTP_422_UNPROCESSABLE_ENTITY` | Starlette 弃用告警 | 改用新常量 |

### 本轮验证

```
pytest backend/tests --ignore=backend/tests/integration     # 干净环境
4364 passed, 3 skipped

pytest backend/tests/services/test_android_agent_loop.py \
       backend/tests/api/test_android_agent_run_api.py \
       backend/tests/api/test_android_agent_draft_replay.py
24 passed（无弃用告警）

npx vue-tsc --noEmit        # 0 error
npx vitest run              # 88 files / 457 tests
ruff check / ruff format    # 873 files already formatted
```

### 仍未完成

- 循环已接入但**没有真机/模拟器实跑**，"目标→真实操作→验证→轨迹"的真实闭环证据仍缺，M2 门槛依旧按未达成记录。
- 无真实视觉模型调用（单测全部使用 `probe_model` 替身）。
- PostgreSQL 上的并发与唯一约束行为仍未实测。
