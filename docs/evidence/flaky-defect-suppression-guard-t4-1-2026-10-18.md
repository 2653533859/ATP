# T4.1 偶发抖动缺陷提单防击穿安全沙箱看门狗服务验收 (2026-10-18)

## 概述与交付物

T4.1（偶发抖动缺陷提单防击穿安全沙箱看门狗服务）已全量研发交付并通过各项工程门禁，**正式开启 ATP v6.0.0 Phase 4（生产防误提安全沙箱、合规存证与全量发布）的缺陷防垃圾提单防线**：
1. **多重抖动自愈与防击穿判定引擎 (`flaky_defect_suppression_guard.py`)**：
   - **重试自愈检验门禁 (`SUPPRESS_FLAKY_RECOVERED`)**：用例在自动重试后通过，判定为偶发环境抖动（Flaky），安全沙箱绝对拦截创建外部工单；
   - **历史高频震荡隔离池 (`SUPPRESS_QUARANTINED_FLAKY`)**：计算用例历史通过/失败翻转率（Flipping Frequency），若震荡率超过 30%，自动列入隔离观察池并抑制提单，通知测试框架维护者定向优化；
   - **网络瞬态异常模式匹配 (`SUPPRESS_TRANSIENT_NETWORK`)**：命中 DNS 解析超时、TCP 握手重置、短时管道破损等瞬态特征且重试未达上限时，暂时抑制提单；
   - **确定性真实缺陷放行 (`DISPATCH_GENUINE_DEFECT`)**：多次重试持续失败且历史稳定无抖动，准予正式分发创建工单。
2. **结构化裁决记录输出 (`FlakyEvaluationDecision`)**：
   - 记录抑制状态（`is_suppressed`）、动作类型、重试轮次、历史抖动分与详尽判定说明。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_flaky_defect_suppression_guard.py`：6 passed（历史翻转震荡率计算、瞬态网络错误识别、重试自愈成功拦截提单、高频抖动进入隔离池、瞬态网络模式过滤、确定性缺陷放行提单及字典序列化）；
   - **通过率**：**6 passed in 0.39s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：1/1 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 1 source file.**。
