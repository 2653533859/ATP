# C3.1 瞬时轻量级仿真沙箱与动态端口生命周期调度验收（2026-10-16）

## 概述与结论

C3.1（瞬时轻量级仿真沙箱与动态端口生命周期调度）已完成全量交付与验证，正式拉开 **v3.2.0 Phase 3（多协议测试执行动态沙箱与隔离环境编排）** 的研发大幕：
1. **防冲突动态端口探测与分配器 (`EphemeralPortManager`)**：
   - 管理瞬时专用端口区间（`20000 ~ 29999`）；
   - 具备真机/容器操作系统套接字（OS Socket）真实绑定探测能力（`SO_REUSEADDR`），杜绝因端口残留或并发竞争导致的端口冲突；
   - 支持端口池动态回收与安全再复用。
2. **多协议瞬时沙箱实例生命周期模型 (`EphemeralSandboxInstance`)**：
   - 原生支持 `http`、`grpc`、`websocket` 与 `multi_protocol` 四大多协议通信方案；
   - 自动组装协议访问基地址（`http://127.0.0.1:{port}`、`grpc://...`、`ws://...`）；
   - 严格管理沙箱生命周期时效（TTL，默认 300s，上限 3600s），自动计算到期时间戳。
3. **沙箱隔离 Mock 路由执行引擎 (`dispatch_sandbox_mock_request`)**：
   - 隔离存放测试执行所需的各协议 Mock 规则；
   - 支持 Method 与 Path 模糊及等值匹配，未命中提供安全 404 回退，沙箱终止自动阻断后续请求。
4. **全自动 TTL 过期收割巡检机制 (`reap_expired_sandboxes`)**：
   - 定期或按需触发过期扫描，自动将超过 TTL 的僵死沙箱置为 `expired` 并强制归还网络端口，杜绝资源泄露。
5. **REST API 统一扩展 (`api/v1/ephemeral_sandboxes.py` & `router.py`)**：
   - `POST /api/v1/sandboxes`：按需秒级拉起瞬时隔离 Mock 仿真沙箱；
   - `GET /api/v1/sandboxes`：查询当前活跃沙箱与分配端口；
   - `GET /api/v1/sandboxes/{id}`：获取指定沙箱详情与 Mock 规则；
   - `POST /api/v1/sandboxes/{id}/terminate`：手动终止沙箱并释放端口；
   - `POST /api/v1/sandboxes/reap`：强制触发全集群过期沙箱与端口巡检回收；
   - `POST /api/v1/sandboxes/{id}/mock-dispatch`：模拟请求分发与 Mock 响应验证。

---

## 质量门禁与验证

1. **专项自动化测试**：
   - `backend/tests/services/test_ephemeral_sandbox_manager.py`：**5 passed in 0.25s**（覆盖端口冲突探测分配与释放、HTTP/gRPC/WebSocket 协议沙箱拉起、沙箱手动销毁与幂等性、TTL 过期自动收割与端口回收、Mock 路由分发匹配与 404 回退）；
   - `scripts/pytest-standalone-sweep.py`：**1 passed, 0 failed standalone**。
2. **静态质量与类型安全**：
   - `ruff check` 与 `ruff format --check`：**All checks passed**；
   - `mypy`：**Success: no issues found in 237 source files**。
