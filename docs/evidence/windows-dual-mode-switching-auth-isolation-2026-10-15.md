# N3.4 双模式切换、认证隔离与错误配置保护验收（2026-10-15）

## 概述与结论

N3.4（双模式切换、认证隔离、错误配置保护与双侧业务回归）已完成代码加固与全自动化测试验证：
1. **认证 Cookie 彻底隔离**：
   - 本地单机模式下由 `settings.ACCESS_COOKIE_NAME` 动态驱动，生成 `atp_local_access_token` 与 `atp_local_refresh_token`；
   - 服务器模式下保持标准 `atp_access_token` 与 `atp_refresh_token`；
   - `auth.py` 中 `_set_auth_cookies` 与 `_clear_auth_cookies` 均采用动态解析属性，在任一模式下登出仅清除该模式对应的专属 Cookie，绝不跨模式清除或覆盖另一模式的会话。
2. **WebSocket 跨模式鉴权隔离**：
   - WebSocket 认证仅抽取并校验当前激活模式下的 Cookie（`settings.ACCESS_COOKIE_NAME`）；
   - 在本地单机模式下，仅携带服务器 Token 的长连接握手直接被拒绝（`None`）；在服务器模式下，仅携带本地 Token 的长连接握手同样直接被拒绝。
3. **错误后端与模式不一致拦截保护**：
   - 前端 HTTP 拦截器在每个请求中自动注入 `X-ATP-Client-Mode: local | server` 请求头；
   - 后端在 `main.py` 的全局中间件中严格校验 `X-ATP-Client-Mode` 与后端 `ATP_LOCAL_MODE` 设置；
   - 若出现前端与后端模式不匹配（如在本地模式端口下向服务器模式发送请求），后端即时熔断返回 HTTP 409 Conflict，阻止错误写入；
   - `/api/v1/runtime` 预留豁免，保证启动阶段与模式探测的握手可用。
4. **前端运行模式断言与功能门禁**：
   - 补齐 `frontend/src/runtimeMode.spec.ts` 单元测试矩阵；
   - 覆盖本地模式正常启动与特征注册、本地期待但后端为服务器模式时的硬阻断、服务器模式正常启动与遗留 404 兜底 fallback 等 5 类场景。
5. **本地配置与服务器基础设施隔离**：
   - 本地模式严格锁定 SQLite、本地文件存储与内存 Celery，调用 `redis_url` 抛出 `RuntimeError`，杜绝误连服务器基础设施。

---

## 代码与测试清单

- `backend/app/api/v1/auth.py`：动态解析 `_access_cookie_name()` 与 `_refresh_cookie_name()`，防止静态模块常量导致的 Cookie 漂移；
- `backend/app/main.py`：在 `reject_unsupported_local_writes` 中增加 `X-ATP-Client-Mode` 跨模式调用检测与 HTTP 409 拦截；
- `frontend/src/api/http.ts`：请求拦截器自动注入 `X-ATP-Client-Mode` 报头，响应拦截器捕获 409 模式冲突并给出友好提示；
- `backend/tests/api/test_dual_mode_isolation.py`：新建双模式隔离专项测试，覆盖 Local/Server Cookie 签发/销毁、WS 鉴权隔离、中间件 409 拦截与本地配置防御（5 passed）；
- `frontend/src/runtimeMode.spec.ts`：新建前端模式校验与功能门禁单元测试（5 passed）。

---

## 质量门禁与验证

1. **后端质量门禁**：
   - `pytest backend/tests/api/test_dual_mode_isolation.py`：**5 passed in 2.62s**；
   - 关联回归集（`test_dual_mode_isolation.py`, `test_runtime_identity.py`, `test_local_mode_config.py`, `test_auth_routes.py`, `test_scrcpy_stream.py`）：**28 passed in 2.87s**；
   - `ruff check` 检查相关后端文件：**All checks passed**（0 告警、0 格式错误）。
2. **前端质量门禁**：
   - `vue-tsc --noEmit -p frontend/tsconfig.json`：**0 error**，全类型推导一致；
   - `vitest run` 覆盖 `runtimeMode.spec.ts`, `navigation.spec.ts`, `navigationRoutes.spec.ts`, `AppWorkbenchView.spec.ts`, `ApiWorkbenchView.spec.ts`, `DeviceList.spec.ts`：**7 个文件、49 项测试 100% 通过**。
