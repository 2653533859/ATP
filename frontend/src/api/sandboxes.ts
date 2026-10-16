import http from './http'

export type SandboxProtocol = 'http' | 'grpc' | 'websocket' | 'multi_protocol'
export type SandboxStatus = 'ready' | 'active' | 'terminated' | 'expired'

export interface EphemeralSandboxItem {
  sandbox_id: string
  session_name: string
  protocol: SandboxProtocol
  host: string
  allocated_port: number
  base_url: string
  status: SandboxStatus
  ttl_seconds: number
  created_at: string
  expires_at: string
  is_expired: boolean
  mock_rules_count: number
  metadata?: Record<string, any>
}

export interface ProvisionSandboxRequest {
  session_name: string
  protocol?: SandboxProtocol
  ttl_seconds?: number
  mock_rules?: Array<{
    method?: string
    path?: string
    status_code?: number
    response_body?: any
  }>
  metadata?: Record<string, any>
}

export interface MockDispatchResult {
  rendered?: any
  status?: number
  body?: any
  message?: string
  mock_match?: boolean
}

export interface InitSessionBusResponse {
  bus_id: string
  message: string
}

export interface SessionBusVarsResponse {
  bus_id: string
  variables: Record<string, any>
}

export interface PropagateContextResponse {
  direction: string
  grpc_metadata?: Record<string, any>
  websocket_context?: Record<string, any>
}

export interface RenderTemplateResponse {
  rendered: any
}

export const sandboxesApi = {
  provision(data: ProvisionSandboxRequest): Promise<{ message: string; sandbox: EphemeralSandboxItem }> {
    return http.post('/sandboxes/provision', data)
  },

  list(protocol?: string, status?: string): Promise<{ total: number; sandboxes: EphemeralSandboxItem[] }> {
    return http.get('/sandboxes', { params: { protocol, status } })
  },

  get(sandboxId: string): Promise<EphemeralSandboxItem> {
    return http.get(`/sandboxes/${sandboxId}`)
  },

  terminate(sandboxId: string): Promise<{ message: string; sandbox: EphemeralSandboxItem }> {
    return http.post(`/sandboxes/${sandboxId}/terminate`)
  },

  reapExpired(): Promise<{ message: string; reaped_count: number; reaped_sandbox_ids: string[] }> {
    return http.post('/sandboxes/reap-expired')
  },

  mockDispatch(
    sandboxId: string,
    data: { method?: string; path?: string }
  ): Promise<MockDispatchResult> {
    return http.post(`/sandboxes/${sandboxId}/mock-dispatch`, data)
  },
}

export const sessionBusApi = {
  initBus(busId?: string): Promise<InitSessionBusResponse> {
    return http.post('/sandboxes/bus/init', null, { params: { bus_id: busId } })
  },

  setVar(busId: string, key: string, value: any): Promise<{ message: string; key: string; value: any }> {
    return http.post(`/sandboxes/bus/${busId}/set-var`, { key, value })
  },

  getVars(busId: string): Promise<SessionBusVarsResponse> {
    return http.get(`/sandboxes/bus/${busId}/vars`)
  },

  propagateContext(
    busId: string,
    direction: 'http_to_grpc' | 'http_to_websocket'
  ): Promise<PropagateContextResponse> {
    return http.post(`/sandboxes/bus/${busId}/propagate`, { direction })
  },

  renderTemplate(busId: string, payload: any): Promise<RenderTemplateResponse> {
    return http.post(`/sandboxes/bus/${busId}/render`, { payload })
  },
}
