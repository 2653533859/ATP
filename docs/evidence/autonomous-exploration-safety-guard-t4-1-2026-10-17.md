# T4.1 自主探索高危动作防护看门狗服务验收 (2026-10-17)

## 概述与交付物

T4.1（自主探索高危动作防护看门狗服务）已全量研发交付并通过各项质量门禁，**正式开启 ATP v5.2.0 Phase 4（探索安全沙箱、合规签名与全量发布）关键防护里程碑**：
1. **看门狗安全评估引擎 (`backend/app/services/autonomous_exploration_safety_guard.py`)**：
   - **高危操作模式矩阵 (`DEFAULT_SAFETY_RULES`)**：涵盖五大高危灾难场景：
     - `ACCOUNT_DESTRUCTION`（注销账号、删除账号、销户、永久注销）；
     - `SYSTEM_PURGE`（恢复出厂设置、抹掉所有内容、清空所有数据、抹掉真机）；
     - `FINANCIAL_RISK`（解绑银行卡、大额真实扣款、转出全部余额）；
     - `SECURITY_TAMPERING`（修改交易密码、重置支付密码、开启开发者 Root、关闭防火墙）；
     - `DATABASE_DESTRUCTION`（DROP DATABASE, TRUNCATE TABLE, DELETE FROM 无条件删库）。
   - **动态风险审查结论 (`SafetyVerdict`)**：
     - `ALLOW`：正常业务手势，放行；
     - `WARN`：警示手势，标记告警并归档；
     - `BLOCK`：高危破坏性手势，立即触发熔断拦截。
   - **违规审计事件归档 (`SafetyViolationEvent`)**：记录触发会话 ID、高危分类、触发关键字、动作详情、处置建议与时间戳。
2. **深度集成至自主探索引擎 (`backend/app/services/vlm_autonomous_explorer.py`)**：
   - 在 `decide_and_step_exploration()` 启发式推导演算后，所有待下发动作实时经看门狗评估；
   - 一旦触发 `BLOCK`，动作被替换为终止保护手势，会话状态自动置为 `CIRCUIT_BROKEN`，彻底杜绝下游真实物理真机或测试数据库遭受不可逆破坏。
3. **REST API 端点集成 (`backend/app/api/v1/intent_workflow_api.py`)**：
   - `POST /api/v1/workflow/intent/exploration/safety/evaluate`：动作安全事前审查；
   - `GET /api/v1/workflow/intent/exploration/safety/violations`：高危违规拦截记录审计列表。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_autonomous_exploration_safety_guard.py`：5 passed（正常操作放行、账号注销阻断、系统抹除阻断、删库指令阻断、熔断保护联动）；
   - `backend/tests/api/test_intent_workflow_api.py`：2 passed；
   - 总体通过率：**14 passed across all Phase 1 ~ 4 backend test files (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：7/7 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**5 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
