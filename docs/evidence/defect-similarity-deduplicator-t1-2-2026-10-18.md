# T1.2 缺陷相似度计算与海量失败聚类去重器服务验收 (2026-10-18)

## 概述与交付物

T1.2（缺陷相似度计算与海量失败聚类去重器服务）已全量研发交付并通过各项工程门禁，**达成 ATP v6.0.0 Phase 1 第二个核心去重聚类计算引擎交付**：
1. **两级相似度判定算法 (`calculate_failure_similarity`)**：
   - 第一级：64 位 SHA-256 故障指纹比对，完全相同返回 1.0；
   - 第二级：语义与词符混合相似度（异常类型相同 +0.35、最深业务根因代码帧相同 +0.35、报错分词 Jaccard 相似度 +0.30），综合判定是否同源；
2. **海量失败聚类与主缺陷选举 (`cluster_and_deduplicate_failures`)**：
   - 自动将单批次海量失败（如 10 起同源超时）合并为一个主缺陷组（`ClusteredDefectGroup`），自动精算去重率（如 10 聚为 1，去重率 90.0%）；
   - 聚合关联的全部用例 ID（`linked_case_ids`）与用例名称；
3. **历史已知未关闭缺陷库智能联动**：
   - 匹配历史工单库（`known_open_defects`），若已有相同故障缺陷，自动标记 `MERGED_TO_EXISTING_DEFECT` 并关联 `existing_defect_id`，防止重复提单泛滥。

## 质量与测试门禁验证

1. **后端单元测试**：
   - `backend/tests/services/test_defect_similarity_deduplicator.py`：5 passed（两级相似度精算、10 处同源失败聚类为单一主缺陷与 90% 去重率验证、历史已知缺陷关联合并、多根因分组聚类验证、空失败列表容错及字典序列化）；
   - **通过率**：**5 passed in 0.32s (100% PASS)**；
   - **独立执行隔离扫描 (pytest-standalone-sweep)**：2/2 passed 100%。
2. **静态代码质量分析**：
   - `ruff check`：**All checks passed! (0 errors)**；
   - `ruff format --check`：**2 files already formatted.**；
   - `mypy`：**Success: no issues found in 2 source files.**。
