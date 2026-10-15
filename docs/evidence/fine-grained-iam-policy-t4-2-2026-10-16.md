# T4.2 基于 RBAC + 细粒度操作资源鉴权边界验收（2026-10-16）

## 概述与结论

T4.2（基于 RBAC + 细粒度操作资源鉴权边界）已完成全量交付与验证：
1. **统一资源与操作分类分级模型 (`ResourceKind` & `IamAction`)**：
   - 细粒度资产覆盖：`case`（用例）、`suite`（套件）、`plan`（计划）、`device`（设备）、`secret`（凭证密钥）、`dataset`（数据集）、`mesh_chaos`（网关混沌）；
   - 细粒度动作控制：`read`（只读查询）、`create`（新建录入）、`modify`（配置修改）、`execute`（任务执行）、`delete`（数据删除）、`manage_permissions`（权限委派）。
2. **多租户横向越权隔离防护 (Anti-IDOR Protection)**：
   - 当请求项目上下文与目标资产所属项目不一致（`project_id != resource_project_id`）时，立即拦截并触发 `anti_idor_cross_project_isolation` 拒绝，杜绝水平越权。
3. **企业级策略决策点引擎 (Policy Decision Point, PDP)**：
   - 采用显式拒绝优先（Explicit Deny Precedence）与最小特权（Default Deny）原则；
   - 严格管控角色权限边界：访客/测试人员严禁修改核心资产与窥探企业密钥；工程师可正常维护与执行资产但严禁擅自销毁密钥；管理员与项目拥有者享有完整管理权。
4. **自定义安全策略动态注册 (`register_custom_policy`)**：
   - 支持安全运维管理员动态注册项目级或全局级细粒度封锁/放行规则（如封锁高危生产环境混沌执行等）。
5. **REST API 统一扩展 (`api/v1/iam_policy.py` & `router.py`)**：
   - `POST /api/v1/iam/evaluate`：在线模拟评估当前登录用户在指定项目及资源上的动作权限判定；
   - `GET /api/v1/iam/policies`：获取平台当前生效的细粒度安全规则基线；
   - `POST /api/v1/iam/policies`：动态注册企业自定义细粒度安全策略（需系统管理员权限）。

---

## 质量门禁与验证

1. **专项自动化测试**：
   - `backend/tests/services/test_fine_grained_iam_policy.py`：**5 passed in 0.31s**（覆盖 Admin/Owner 完全权限、Engineer/Editor 读写执行与密钥删除拦截、Tester/Viewer 读执行与修改及密钥窥探拦截、Anti-IDOR 跨项目越权隔离、自定义策略动态注册与 Explicit Deny 优先原则）；
   - `scripts/pytest-standalone-sweep.py`：**1 passed, 0 failed standalone**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 229 source files**。
