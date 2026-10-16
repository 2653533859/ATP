# UI1.2 跨服务关键路径分析与慢调用火焰图性能大盘验收 (2026-10-16)

## 概述与结论

UI1.2（跨服务关键路径分析与慢调用火焰图性能大盘）已完成全量交付与验证，持续推进 **ATP v4.1.0 Phase 1（分布式链路全息追踪、调用树与性能瓶颈火焰图控制台）**：
1. **全景性能大盘与路由注册 (`CriticalPathFlamegraphDashboardView.vue` & `/quality/trace-flamegraph`)**：
   - **头部 Hero 区域**：
     - 说明最长依赖路径动态规划算法在排除异步旁路干扰、精确定位端到端决定性时延瓶颈中的核心价值；
     - 提供「立即执行关键路径与火焰图分析」主操作入口；
   - **场景预设切换栏**：
     - `场景 1: 外部支付网关高时延瓶颈 (EXTERNAL_HTTP_LATENCY 300ms)`
     - `场景 2: 数据库行锁慢 SQL 瓶颈 (DATABASE_SLOW_QUERY 250ms)`
     - `场景 3: 内部密集计算递归瓶颈 (INTERNAL_COMPUTATION 180ms)`
   - **首要瓶颈裁决大横幅 (Bottleneck Verdict Banner)**：
     - 醒目大徽章：`EXTERNAL_HTTP_LATENCY`（红色）、`DATABASE_SLOW_QUERY`（紫色）、`INTERNAL_COMPUTATION`（橙色）；
     - 诊断结论摘要与关联 Trace ID；
     - 4 项核心数据指标：关键路径总耗时（ms）、首要瓶颈自身独占耗时（Self-Time）、瓶颈对关键路径贡献率（%）、关键路径节点数占全链路比例；
   - **分层交互式性能火焰图 (Interactive Flamegraph)**：
     - 按层级深度（D0, D1, D2...）堆叠渲染火条；
     - 火条宽度依据其总耗时占全链路比例动态计算 (`width: (val / total) * 100%`)；
     - 色彩编码：红色带发光与 ⚠️ 标识首要瓶颈节点，橙色标识关键路径（Critical Path），冷灰蓝色标识普通旁路；
     - 点击任何火条可在下方动态卡片下钻展示服务名、SpanId、持续耗时、独占自身耗时与瓶颈分类；
   - **关键路径执行序列与时延贡献矩阵 (Critical Path Table)**：
     - 顺序呈现 Step 1 ~ Step N 关键链路节点：微服务标签、操作名、总耗时、自身独占耗时（瓶颈高亮）、贡献比相对进度条与瓶颈类别。
2. **路由配置 (`frontend/src/router/index.ts`)**：
   - 挂载路由 `/quality/trace-flamegraph`（路由名 `critical-path-flamegraph-dashboard`），受工程师与管理员权限管控。

## 质量与测试门禁验证

1. **单元测试 (`vitest`)**：
   - `src/views/quality/CriticalPathFlamegraphDashboardView.spec.ts`：**2 passed in 66ms**；
   - `src/views/workbench/components/DistributedTraceSpanTreeDrawer.spec.ts`：**2 passed**；
   - `src/views/workbench/ApiWorkbenchView.spec.ts`：**12 passed**；
   - 工作台与大盘核心测试套件：**16 passed in 661ms**。
2. **TypeScript 类型安全**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**。
3. **生产环境构建**：
   - `npm run build` (`vite build`)：**✓ built in 10.09s, 0 errors**。
