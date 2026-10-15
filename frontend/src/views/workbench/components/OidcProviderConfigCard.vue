<template>
  <div class="oidc-provider-config-card">
    <a-card size="small" class="main-card">
      <template #title>
        <div class="card-title-box">
          <span class="title-text">企业级 OIDC / OAuth2 身份提供商 (IdP) 与单点登录</span>
          <a-tag color="blue">SSO Single Sign-On</a-tag>
        </div>
      </template>

      <template #extra>
        <a-space>
          <a-button size="small" :loading="loading" @click="loadProviders">
            刷新身份源
          </a-button>
          <a-button size="small" type="primary" @click="showRegisterModal = true">
            接入新身份提供商
          </a-button>
        </a-space>
      </template>

      <!-- 简介与安全合规提示 -->
      <div class="card-intro">
        <p class="subtitle">
          统一接入企业统一身份认证中枢（支持 Keycloak、Okta、Microsoft ADFS、Azure AD 等标准 OpenID Connect 1.0 协议）。所有应用客户端私钥（Client Secret）在网络传输与渲染中严格执行脱敏脱壳掩码保护。
        </p>
      </div>

      <!-- 身份提供商卡片网格 -->
      <div v-if="providers.length" class="providers-grid">
        <div
          v-for="p in providers"
          :key="p.provider_id"
          class="idp-card"
          :class="{ disabled: !p.enabled }"
        >
          <div class="idp-header">
            <div class="idp-title-group">
              <strong class="idp-name">{{ p.name }}</strong>
              <code class="idp-id-tag">{{ p.provider_id }}</code>
            </div>
            <a-tag :color="p.enabled ? 'green' : 'default'">
              {{ p.enabled ? '已启用' : '已停用' }}
            </a-tag>
          </div>

          <div class="idp-meta">
            <div class="meta-row">
              <span class="lbl">颁发者 (Issuer):</span>
              <span class="val mono" :title="p.issuer">{{ p.issuer }}</span>
            </div>
            <div class="meta-row">
              <span class="lbl">Client ID:</span>
              <span class="val mono">{{ p.client_id }}</span>
            </div>
            <div class="meta-row">
              <span class="lbl">Client Secret:</span>
              <span class="val mono secret-val">{{ p.client_secret }}</span>
            </div>
            <div class="meta-row">
              <span class="lbl">授权权限域 (Scopes):</span>
              <a-space size="small" class="scopes-wrap">
                <a-tag v-for="s in p.scopes" :key="s" color="cyan" class="mini-tag">
                  {{ s }}
                </a-tag>
              </a-space>
            </div>
            <div class="meta-row">
              <span class="lbl">默认映射角色:</span>
              <a-tag color="purple">{{ p.default_role }}</a-tag>
            </div>
          </div>

          <div class="idp-footer">
            <a-button
              type="primary"
              size="small"
              :disabled="!p.enabled"
              class="sso-btn"
              @click="handleInitiateSso(p)"
            >
              一键发起企业 SSO 单点登录
            </a-button>
          </div>
        </div>
      </div>

      <a-empty v-else description="暂无配置的身份提供商，请点击上方「接入新身份提供商」" class="empty-box" />

      <!-- SSO 发起成功展示弹窗 -->
      <a-modal
        v-model:open="showSsoModal"
        title="企业 IdP 认证重定向已生成"
        :footer="null"
        destroy-on-close
      >
        <div v-if="ssoUrlData" class="sso-modal-body">
          <a-alert
            type="success"
            show-icon
            message="已成功通过防 CSRF 与防重放随机数校验 (State & Nonce)"
            style="margin-bottom: 12px;"
          />

          <div class="sso-field">
            <span class="field-lbl">防伪 State 参数:</span>
            <code>{{ ssoUrlData.state }}</code>
          </div>

          <div class="sso-field">
            <span class="field-lbl">防重放 Nonce 参数:</span>
            <code>{{ ssoUrlData.nonce }}</code>
          </div>

          <div class="sso-field">
            <span class="field-lbl">IdP 授权重定向地址:</span>
            <div class="url-box">{{ ssoUrlData.authorization_url }}</div>
          </div>

          <div class="modal-actions">
            <a-button type="primary" block @click="showSsoModal = false">
              确认并关闭
            </a-button>
          </div>
        </div>
      </a-modal>

      <!-- 注册新身份提供商弹窗 -->
      <a-modal
        v-model:open="showRegisterModal"
        title="接入企业级 OIDC 身份提供商"
        :confirm-loading="registering"
        destroy-on-close
        @ok="handleRegisterSubmit"
      >
        <a-form layout="vertical">
          <a-form-item label="IdP 唯一标识 (provider_id)" required>
            <a-input v-model:value="registerForm.provider_id" placeholder="例如: adfs_corp 或 azure_ad" />
          </a-form-item>

          <a-form-item label="身份提供商显示名称" required>
            <a-input v-model:value="registerForm.name" placeholder="例如: 集团企业级 Active Directory SSO" />
          </a-form-item>

          <a-form-item label="颁发者 URL (Issuer)" required>
            <a-input v-model:value="registerForm.issuer" placeholder="例如: https://sso.corp.internal/realms/master" />
          </a-form-item>

          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item label="Client ID" required>
                <a-input v-model:value="registerForm.client_id" placeholder="atp-sso-client" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="Client Secret" required>
                <a-input-password v-model:value="registerForm.client_secret" placeholder="••••••••" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-form-item label="授权登录端点 (Authorization Endpoint)" required>
            <a-input v-model:value="registerForm.authorization_endpoint" placeholder="https://.../auth" />
          </a-form-item>

          <a-form-item label="令牌交换端点 (Token Endpoint)" required>
            <a-input v-model:value="registerForm.token_endpoint" placeholder="https://.../token" />
          </a-form-item>

          <a-form-item label="默认映射平台角色">
            <a-select v-model:value="registerForm.default_role" style="width: 100%">
              <a-select-option value="tester">测试人员 (Tester)</a-select-option>
              <a-select-option value="engineer">研发工程师 (Engineer)</a-select-option>
              <a-select-option value="admin">系统管理员 (Admin)</a-select-option>
            </a-select>
          </a-form-item>
        </a-form>
      </a-modal>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  oidcSsoApi,
  type OidcProvider,
  type SsoLoginUrlResponse,
  type RegisterOidcProviderRequest,
} from '@/api/oidcSso'

const loading = ref(false)
const registering = ref(false)
const providers = ref<OidcProvider[]>([])

const showRegisterModal = ref(false)
const showSsoModal = ref(false)
const ssoUrlData = ref<SsoLoginUrlResponse | null>(null)

const registerForm = reactive<RegisterOidcProviderRequest>({
  provider_id: 'adfs_corp',
  name: '集团企业级 Active Directory SSO',
  issuer: 'https://adfs.corp.internal/adfs',
  client_id: 'atp-adfs-client',
  client_secret: 'sec_corp_adfs_9918',
  authorization_endpoint: 'https://adfs.corp.internal/adfs/oauth2/authorize',
  token_endpoint: 'https://adfs.corp.internal/adfs/oauth2/token',
  userinfo_endpoint: 'https://adfs.corp.internal/adfs/userinfo',
  jwks_uri: 'https://adfs.corp.internal/adfs/discovery/keys',
  scopes: ['openid', 'profile', 'email'],
  enabled: true,
  default_role: 'engineer',
})

async function loadProviders() {
  loading.value = true
  try {
    const res = await oidcSsoApi.listProviders()
    providers.value = res.providers
  } catch (err: any) {
    message.error(err.message || '获取身份提供商列表失败')
  } finally {
    loading.value = false
  }
}

async function handleInitiateSso(p: OidcProvider) {
  try {
    const res = await oidcSsoApi.getLoginUrl(
      p.provider_id,
      window.location.origin + '/sso/callback'
    )
    ssoUrlData.value = res
    showSsoModal.value = true
    message.success(`已生成 ${p.name} 单点登录重定向！`)
  } catch (err: any) {
    message.error(err.message || '生成 SSO 登录地址失败')
  }
}

async function handleRegisterSubmit() {
  if (!registerForm.provider_id.trim() || !registerForm.name.trim()) {
    message.warning('请填写完整的身份提供商标识与名称')
    return
  }
  registering.value = true
  try {
    await oidcSsoApi.registerProvider(registerForm)
    message.success('新身份提供商已成功注册！')
    showRegisterModal.value = false
    await loadProviders()
  } catch (err: any) {
    message.error(err.message || '注册身份提供商失败')
  } finally {
    registering.value = false
  }
}

onMounted(() => {
  loadProviders()
})
</script>

<style scoped>
.oidc-provider-config-card {
  width: 100%;
}

.main-card {
  border-radius: 8px;
}

.card-title-box {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-text {
  font-weight: 600;
  font-size: 14px;
  color: var(--c-text, #0f172a);
}

.card-intro {
  margin-bottom: 14px;
}

.subtitle {
  margin: 0;
  font-size: 12px;
  color: var(--c-text-secondary, #64748b);
  line-height: 1.6;
}

.providers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.idp-card {
  background: var(--c-bg-subtle, #f8fafc);
  border: 1px solid var(--c-border, #e2e8f0);
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: all 0.2s ease;
}

.idp-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.08);
}

.idp-card.disabled {
  opacity: 0.65;
}

.idp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.idp-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.idp-name {
  font-size: 14px;
  color: var(--c-text, #0f172a);
}

.idp-id-tag {
  font-size: 11px;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 1px 6px;
  border-radius: 4px;
}

.idp-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
}

.meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.lbl {
  color: var(--c-text-secondary, #64748b);
  min-width: 115px;
  flex-shrink: 0;
}

.val {
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mono {
  font-family: monospace;
  font-size: 11px;
}

.secret-val {
  color: #dc2626;
  font-weight: 600;
}

.mini-tag {
  font-size: 10px;
  padding: 0 4px;
}

.idp-footer {
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px dashed var(--c-border, #e2e8f0);
}

.sso-btn {
  width: 100%;
}

.empty-box {
  padding: 24px 0;
}

.sso-modal-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sso-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}

.field-lbl {
  color: #64748b;
  font-weight: 500;
}

.sso-field code {
  color: #2563eb;
  font-size: 11px;
}

.url-box {
  font-family: monospace;
  font-size: 11px;
  background: #0f172a;
  color: #38bdf8;
  padding: 8px;
  border-radius: 4px;
  word-break: break-all;
}

.modal-actions {
  margin-top: 12px;
}
</style>
