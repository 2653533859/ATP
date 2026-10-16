# UI2.3 消息事件总线消费延迟、死信重放与幂等压测卡片验收 (2026-10-16)

## 概述与结论

UI2.3（消息事件总线消费延迟、死信重放与幂等压测卡片）已完成全量交付与验证，**标志着 ATP v4.1.0 Phase 2（微服务分布式事务与跨系统数据最终一致性对账大盘）100% 达成全量大闭环**：
1. **消息总线防线卡片组件 (`EventBusDeadletterIdempotencyCard.vue`)**：
   - **Tab 1: 幂等消费重复投递压测 (Idempotency Stress Test)**：
     - 支持输入业务幂等凭证（`idempotency_key`）与重复投递轮次（2~10 次）；
     - 压测裁决大横幅直观展示 `IDEMPOTENT` 绿色合规或 `MUTATION_LEAK` 红色漏洞；
     - 3 项关键数据指标：重复投递总轮次、底层实际状态写入次数（标称严格为 1）、以及幂等拦截安全抑制次数；
   - **Tab 2: Topic 消费延迟与积压监控 (Consumer Lag)**：
     - 表格展示 Topic 名称、消费者组（Consumer Group）、当前未消费积压量（Current Lag）；
     - 积压健康度评级徽章（`HEALTHY` / `WARNING` / `CRITICAL_BACKLOG`）；
     - 平均消费处理耗时与最长未消费消息存活期；
   - **Tab 3: 死信队列 (DLQ) 隔离与重放**：
     - 死信积压报警提示与有毒消息列表；
     - 显示死信消息 ID、所属 Topic、重试超限次数（3/3 次）与有毒异常原因；
     - 提供「重放重新排队」操作，调用 `requeueDeadLetter` 重新入队消费重试。
2. **工作台集成 (`ApiWorkbenchView.vue`)**：
   - 顶部工具栏挂载「消息总线防线」入口；
   - 支持一键滑出 1120px 宽幅控制台抽屉。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/workbench/components/EventBusDeadletterIdempotencyCard.spec.ts`：**2 passed in 45ms**；
   - `src/views/quality/CrossDbConsistencyAuditDashboardView.spec.ts`：**2 passed**；
   - `src/views/workbench/components/SagaTransactionStateTrackerDrawer.spec.ts`：**2 passed**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed**；
   - Phase 2 核心测试套件：**18 passed in 715ms**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 9.91s, 0 errors**。
