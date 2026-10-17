# T2.1 ~ T2.3 多模态 VLM 自主探索引擎与轨迹固化验收 (2026-10-17)

## 概述与结论

T2.1（多模态 VLM 屏幕语义理解与自主动作决策器）、T2.2（探索过程白屏、死锁与崩溃异常侦测器）、T2.3（探索成功轨迹逆向自动化工作流转换器）已全量交付并完成验证，**标志着 ATP v5.2.0 Phase 2（基于多模态 VLM 界面理解的移动与 Web 自主探索引擎）全量大闭环**：
1. **VLM 视觉屏幕理解与启发式探索决策 (`backend/app/services/vlm_autonomous_explorer.py`)**：
   - 接收屏幕快照并感知可交互控件元素（按钮、输入框、导航 Tab、弹窗），推导页面唯一状态指纹 (`compute_ui_signature`)；
   - 构建页面状态迁移图谱 (`StateTransitionGraph`: 状态节点 `UIStateNode` 与跳转边 `StateTransitionEdge`)；
   - 启发式决策下一步最优手势（点击、输入、滑动拖拽、返回），防范无用循环探索。
2. **白屏、死锁与崩溃异常侦测器 (`backend/app/services/exploration_anomaly_detector.py`)**：
   - 自动检测三种典型前端/端侧崩溃异常：
     - 白屏/黑屏卡死 (`WHITE_SCREEN`，严重等级 `CRITICAL`)；
     - 连续同态死锁 (`STATE_DEADLOCK`，交互多次状态未转移)；
     - 业务错误与网络异常弹窗 (`ERROR_DIALOG`，自动提取弹窗警告信息并建议处理对策)。
3. **探索轨迹逆向工作流转换器 (`backend/app/services/exploration_to_workflow_converter.py`)**：
   - 将验证通过的连贯手势与输入轨迹，一键逆向固化为标准低代码多端自动化工作流草稿（前置连接节点 + 序列 UI/真机动作节点 + 拓扑有向边），支持直接导入工作流画布与用例库。
4. **REST API 端点集成 (`backend/app/api/v1/intent_workflow_api.py`)**：
   - `POST /api/v1/workflow/intent/exploration/start`：启动多模态自主探索会话；
   - `POST /api/v1/workflow/intent/exploration/step`：单步探索执行与异常巡检；
   - `GET /api/v1/workflow/intent/exploration/{id}`：获取状态迁移图谱；
   - `GET /api/v1/workflow/intent/exploration/list/sessions`：查询全量探索会话；
   - `POST /api/v1/workflow/intent/exploration/convert`：一键轨迹固化转换为工作流；
   - `GET /api/v1/workflow/intent/exploration/anomalies/list`：查询检出的异常缺陷。

## 质量与测试门禁验证

1. **服务与 API 单元测试**：
   - `backend/tests/services/test_vlm_autonomous_explorer.py`：1 passed；
   - `backend/tests/services/test_exploration_anomaly_detector.py`：1 passed；
   - `backend/tests/services/test_exploration_to_workflow_converter.py`：1 passed；
   - `backend/tests/api/test_intent_workflow_api.py`：2 passed；
   - 总体通过率：**9 passed across all Phase 1 & 2 tests (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：6/6 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed!**；
   - `ruff format --check`：**All files already formatted.**；
   - `mypy`：**Success: no issues found in 3 source files.**。
