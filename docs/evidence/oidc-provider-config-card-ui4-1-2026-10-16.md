# UI4.1 企业级 OIDC / OAuth2 身份提供商接入与单点登录卡片验收（2026-10-16）

## 概述与结论

UI4.1（企业级 OIDC / OAuth2 身份提供商接入与单点登录卡片）已完成全量交付与验证，正式开启 **v3.1.0 Phase 4（企业级 OIDC/SSO 与不可篡改审计安全中心）**：
1. **统一 API 客户端 (`frontend/src/api/oidcSso.ts`)**：
   - 封装 `listProviders`、`registerProvider`、`getLoginUrl` 与 `ssoCallback` 4 大身份源接入接口；
   - 建立 `OidcProvider`、`RegisterOidcProviderRequest` 与 `SsoLoginUrlResponse` 完整强类型。
2. **企业级身份提供商接入交互卡片 (`OidcProviderConfigCard.vue`)**：
   - **身份源卡片网格**：全景展示已接入的企业身份中枢（如 Keycloak、Okta、ADFS 等），直观展示 Issuer URL、Client ID、授权作用域（Scopes）与默认映射平台角色；
   - **安全敏感凭据脱敏**：客户端私钥（Client Secret）在网络拉取与前端视图中严格显示为 `***REDACTED***` 掩码；
   - **一键发起企业 SSO 登录跳转**：
     - 点击触发 `getLoginUrl` 接口；
     - 弹出防 CSRF（State）与防重放（Nonce）随机校验参数及最终 IdP 授权登录重定向地址；
   - **动态接入新身份源弹窗**：支持管理员录入自定义 IdP 颁发者、Client ID/Secret、OAuth2 授权/令牌端点，提交即时入库生效。
3. **系统配置中心挂载集成 (`ConfigurationCenterView.vue`)**：
   - 在系统配置中心顶部操作区挂载「企业 SSO 身份源」快捷入口；
   - 支持从配置中心一键滑出企业级 OIDC/SSO 身份提供商管理抽屉。

---

## 质量门禁与验证

1. **单元测试与组件交互**：
   - `frontend/src/views/workbench/components/OidcProviderConfigCard.spec.ts`：**2 passed in 171ms**（覆盖列表渲染、密钥脱敏检验、一键发起 SSO 获取 State/Nonce 跳转 URL）；
   - `ConfigurationCenterView.spec.ts`：**4 passed in 120ms**。
2. **类型检查与生产构建**：
   - `npm run type-check` (`vue-tsc --noEmit`)：**0 issues, clean PASS**；
   - `npm run build` (`vite build`)：**✓ built in 2.43s, 0 errors**。
