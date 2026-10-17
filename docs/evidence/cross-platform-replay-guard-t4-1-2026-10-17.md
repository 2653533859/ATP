# T4.1 跨端迁移回放安全防护看门狗服务验收 (2026-10-17)

## 概述与交付物

T4.1（跨端迁移回放安全防护看门狗服务）已全量研发交付并通过各项工程门禁，**正式开启 ATP v5.3.0 Phase 4（跨端回放安全沙箱、合规存证与全量发布）关键安全防护里程碑**：
1. **多重安全看门狗引擎 (`backend/app/services/cross_platform_replay_guard.py`)**：
   - **高危破坏手势拦截 (`HIGH_RISK_GESTURE`)**：
     - 黑名单覆盖注销账号、销户、抹掉数据、恢复出厂设置、格式化、真实大额转账、解绑银行卡、删库指令等高危敏感词；
     - 严防跨端转译模糊匹配误触敏感按钮引发生产或物理真机灾难。
   - **坐标物理漂移与越界保护 (`COORDINATE_OUT_OF_BOUNDS`)**：
     - `ScreenViewport` 视口有效性校验，拦截负坐标、超出目标屏幕最大宽高以及落在顶端系统状态栏或悬浮黑区的手势。
   - **低置信度动作阻断门禁 (`LOW_CONFIDENCE_GATE`)**：
     - 当步骤映射置信度低于安全阈值（默认 `0.50`）时，对交互性写操作（点击、输入）实施阻断熔断，要求人工复核。
2. **REST API 端点拓展 (`backend/app/api/v1/cross_platform_migration_api.py`)**：
   - `POST /api/v1/migration/replay/guard`：单步回放动作安全事前审查；
   - `GET /api/v1/migration/replay/violations`：回放看门狗违规拦截事件列表查询。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_cross_platform_replay_guard.py`：4 passed（安全操作放行、高危敏感词阻断、坐标超出边界阻断、低置信度交互门禁阻断）；
   - `backend/tests/api/test_cross_platform_migration_api.py`：7 passed；
   - **总体通过率**：**30 passed across all Phase 1 ~ 4 backend test files (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：7/7 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**4 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
