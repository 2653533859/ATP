import http from './http'

export type NotificationChannel = 'wechat' | 'dingtalk' | 'feishu' | 'email' | 'slack'
export type DeliveryPriority = 'P0' | 'P1' | 'P2' | 'P3'

export interface NotificationCardPayload {
  title: string
  summary: string
  status: string
  project_name: string
  run_id: string | number
  pass_rate_pct: number
  duration_sec: number
  report_url?: string | null
  metrics?: Record<string, any>
  actions?: Array<{ text: string; url: string }>
  mentions?: string[]
}

export interface NotificationRouteTarget {
  channel: NotificationChannel
  webhook_url: string
  secret?: string
  enabled: boolean
}

export interface DeliveryAuditRecordItem {
  success: boolean
  channel: NotificationChannel
  target_webhook_masked: string
  priority: DeliveryPriority
  attempts: number
  http_status: number | null
  response_message: string
  dispatched_at: string
  duration_ms: number
}

export interface DispatcherStats {
  total_dispatched_count: number
  overall_success_rate_pct: number
  channel_distribution: Record<string, number>
}

export interface DispatchNotificationRequest {
  target: NotificationRouteTarget
  card: NotificationCardPayload
  priority?: DeliveryPriority
}

export interface BroadcastNotificationRequest {
  targets: NotificationRouteTarget[]
  card: NotificationCardPayload
  priority?: DeliveryPriority
}

export const notificationHubApi = {
  dispatch(data: DispatchNotificationRequest): Promise<{ message: string; record: DeliveryAuditRecordItem }> {
    return http.post('/reporting/notifications/dispatch', data)
  },

  broadcast(data: BroadcastNotificationRequest): Promise<{
    message: string
    total: number
    success_count: number
    records: DeliveryAuditRecordItem[]
  }> {
    return http.post('/reporting/notifications/broadcast', data)
  },

  listAudits(params?: { channel?: string }): Promise<{ total: number; records: DeliveryAuditRecordItem[] }> {
    return http.get('/reporting/notifications/audits', { params })
  },

  getStats(): Promise<DispatcherStats> {
    return http.get('/reporting/notifications/stats')
  },
}
