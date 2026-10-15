import http from './http'

export interface OidcProvider {
  provider_id: string
  name: string
  issuer: string
  client_id: string
  client_secret: string
  authorization_endpoint: string
  token_endpoint: string
  userinfo_endpoint: string
  jwks_uri: string
  scopes: string[]
  enabled: boolean
  default_role: string
}

export interface RegisterOidcProviderRequest {
  provider_id: string
  name: string
  issuer: string
  client_id: string
  client_secret: string
  authorization_endpoint: string
  token_endpoint: string
  userinfo_endpoint: string
  jwks_uri: string
  scopes?: string[]
  enabled?: boolean
  default_role?: string
}

export interface SsoLoginUrlResponse {
  authorization_url: string
  state: string
  nonce: string
  provider_id: string
}

export const oidcSsoApi = {
  listProviders(onlyEnabled: boolean = false): Promise<{ providers: OidcProvider[] }> {
    return http.get('/auth/sso/providers', {
      params: { only_enabled: onlyEnabled },
    })
  },

  registerProvider(data: RegisterOidcProviderRequest): Promise<{ message: string; provider: OidcProvider }> {
    return http.post('/auth/sso/providers', data)
  },

  getLoginUrl(providerId: string, redirectUri: string): Promise<SsoLoginUrlResponse> {
    return http.get(`/auth/sso/${providerId}/login-url`, {
      params: { redirect_uri: redirectUri },
    })
  },

  ssoCallback(
    providerId: string,
    data: { state: string; code?: string; id_token_claims?: Record<string, any> }
  ): Promise<{
    access_token: string
    refresh_token: string
    token_type: string
    user: { id: number; username: string; email: string; role: string }
    sso_provider: string
  }> {
    return http.post(`/auth/sso/${providerId}/callback`, data)
  },
}
