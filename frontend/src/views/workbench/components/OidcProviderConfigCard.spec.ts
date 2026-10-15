import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import OidcProviderConfigCard from './OidcProviderConfigCard.vue'

const mockProviders = [
  {
    provider_id: 'keycloak',
    name: 'Keycloak Enterprise SSO',
    issuer: 'https://sso.enterprise.internal/auth/realms/atp',
    client_id: 'atp-web-client',
    client_secret: '***REDACTED***',
    authorization_endpoint: 'https://sso.enterprise.internal/auth/realms/atp/protocol/openid-connect/auth',
    token_endpoint: 'https://sso.enterprise.internal/auth/realms/atp/protocol/openid-connect/token',
    userinfo_endpoint: 'https://sso.enterprise.internal/auth/realms/atp/protocol/openid-connect/userinfo',
    jwks_uri: 'https://sso.enterprise.internal/auth/realms/atp/protocol/openid-connect/certs',
    scopes: ['openid', 'profile', 'email'],
    enabled: true,
    default_role: 'tester',
  },
  {
    provider_id: 'okta',
    name: 'Okta Identity Cloud',
    issuer: 'https://company.okta.com/oauth2/default',
    client_id: '0oa98234atpClient',
    client_secret: '***REDACTED***',
    authorization_endpoint: 'https://company.okta.com/oauth2/default/v1/authorize',
    token_endpoint: 'https://company.okta.com/oauth2/default/v1/token',
    userinfo_endpoint: 'https://company.okta.com/oauth2/default/v1/userinfo',
    jwks_uri: 'https://company.okta.com/oauth2/default/v1/keys',
    scopes: ['openid', 'profile', 'email'],
    enabled: true,
    default_role: 'tester',
  },
]

const mockLoginUrlResponse = {
  authorization_url: 'https://sso.enterprise.internal/auth?response_type=code&client_id=atp-web-client&state=st_random_123&nonce=nc_random_456',
  state: 'st_random_123',
  nonce: 'nc_random_456',
  provider_id: 'keycloak',
}

const mockListProviders = vi.fn().mockResolvedValue({ providers: mockProviders })
const mockGetLoginUrl = vi.fn().mockResolvedValue(mockLoginUrlResponse)
const mockRegisterProvider = vi.fn().mockResolvedValue({ message: 'ok', provider: mockProviders[0] })

vi.mock('@/api/oidcSso', () => ({
  oidcSsoApi: {
    listProviders: (onlyEnabled?: boolean) => mockListProviders(onlyEnabled),
    getLoginUrl: (id: string, uri: string) => mockGetLoginUrl(id, uri),
    registerProvider: (data: unknown) => mockRegisterProvider(data),
    ssoCallback: vi.fn(),
  },
}))

const globalStubs = {
  'a-card': { template: '<div class="ant-card"><h4>{{ $attrs.title }}</h4><slot /><slot name="title" /><slot name="extra" /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-space': { template: '<div><slot /></div>' },
  'a-modal': { template: '<div class="ant-modal"><h3>{{ $attrs.title }}</h3><slot /></div>' },
  'a-form': { template: '<form><slot /></form>' },
  'a-form-item': { template: '<div class="form-item"><slot /></div>' },
  'a-input': { template: '<input />' },
  'a-input-password': { template: '<input type="password" />' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-alert': { template: '<div class="ant-alert">{{ $attrs.message }}</div>' },
  'a-empty': { template: '<div class="ant-empty">{{ $attrs.description }}</div>' },
  'a-row': { template: '<div class="ant-row"><slot /></div>' },
  'a-col': { template: '<div class="ant-col"><slot /></div>' },
}

describe('OidcProviderConfigCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads and renders OIDC identity providers with masked secrets', async () => {
    const wrapper = mount(OidcProviderConfigCard, {
      global: {
        stubs: globalStubs,
      },
    })
    await flushPromises()

    expect(mockListProviders).toHaveBeenCalled()
    expect(wrapper.text()).toContain('企业级 OIDC / OAuth2 身份提供商 (IdP) 与单点登录')
    expect(wrapper.text()).toContain('Keycloak Enterprise SSO')
    expect(wrapper.text()).toContain('Okta Identity Cloud')
    expect(wrapper.text()).toContain('***REDACTED***')
    expect(wrapper.text()).toContain('openid')
  })

  it('initiates SSO login redirect and displays state and nonce', async () => {
    const wrapper = mount(OidcProviderConfigCard, {
      global: {
        stubs: globalStubs,
      },
    })
    await flushPromises()

    const ssoBtn = wrapper.findAll('button').find((b) => b.text().includes('一键发起企业 SSO 单点登录'))
    expect(ssoBtn).toBeDefined()
    await ssoBtn!.trigger('click')
    await flushPromises()

    expect(mockGetLoginUrl).toHaveBeenCalledWith('keycloak', expect.stringContaining('/sso/callback'))
    expect(wrapper.text()).toContain('已成功通过防 CSRF 与防重放随机数校验 (State & Nonce)')
    expect(wrapper.text()).toContain('st_random_123')
    expect(wrapper.text()).toContain('nc_random_456')
  })
})
