# T2.1 系统容量拐点智能推演与吞吐天花板挖掘器服务验收 (2026-10-18)

## 概述与交付物

T2.1（系统容量拐点智能推演与吞吐天花板挖掘器服务）已全量研发交付并通过各项工程门禁，**正式开启 ATP v6.2.0 Phase 2（架构容量基线拐点推演与自适应限流熔断看门狗）的核心研发**：
1. **Universal Scalability Law (USL 通用可伸缩性定律) 拟合引擎 (`fit_usl_parameters`)**：
   - 纯 Python 标准库最小二乘正规方程高斯消元法，求解 USL 核心系统参数：
     - 单并发基准处理效率系数 $\gamma$（Throughput per worker）；
     - 串行资源锁争用阻碍系数 $\sigma$（Amdahl Contention penalty）；
     - 线程/节点间数据相干同步开销系数 $\kappa$（Coherency delay penalty）；
   - 自动输出回归拟合优度判定（$R^2 \ge 0.85$）；
2. **最优性能拐点与系统饱和天花板推演 (`deduct_capacity_knee_point`)**：
   - **最优性能拐点 ($N_{knee}$)**：并发利用率最高、响应耗时平稳的最优并发推荐（在此之后延迟非线性攀升）；
   - **系统饱和极限点 ($N_{max} = \sqrt{(1 - \sigma) / \kappa}$)**：导数临界点，超出此并发系统将出现断崖倒挂雪崩（Thrashing）；
   - **吞吐量理论天花板 ($X_{max}$)**：系统在饱和点下的最大承载 TPS 极限；
3. **生产安全限流基线自动计算**：
   - 推荐生产网关限流阈值安全锁定在 $80\% \times N_{knee}$，留出 20% 防冲击缓冲。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_capacity_knee_point_deductor.py`：4 passed（USL 基础模型与单并发吞吐推演、真实阶梯采样高精度拟合、极少样本保守兜底策略、容量拐点与饱和极限全生命周期报告及字典序列化）；
   - **通过率**：**4 passed in 0.33s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：1/1 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
