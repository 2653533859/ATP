import http from './http'

export interface IosTunnelDeviceItem {
  udid: string
  device_name: string
  model: string
  ios_version: string
  agent_id: string
  agent_name: string
  remote_wda_port: number
  local_tunnel_port: number
  status: string
  battery_level: number
  temperature_celsius: number
  wda_alive: boolean
  health_status: string
  connected_at: string
  last_activity_at: string
}

export interface IosLeaseItem {
  lease_token: string
  udid: string
  owner_id: string
  owner_label: string
  purpose: string
  ttl_seconds: number
  acquired_at: string
  heartbeat_at: string
  expires_at: string
  is_active: boolean
}

export interface WdaSessionItem {
  session_id: string
  udid: string
  lease_token: string
  bundle_id: string
  capabilities: Record<string, any>
  status: string
  created_at: string
  last_ping_at: string
}

export interface PoolCapacitySummary {
  total_devices: number
  idle_devices: number
  busy_devices: number
  offline_devices: number
  ios_devices_count: number
  android_devices_count: number
  pool_utilization_rate: number
}

export interface UnifiedDeviceItem {
  unified_id: string
  raw_id: string
  platform: 'ios' | 'android'
  name: string
  model: string
  brand: string
  os_version: string
  status: 'IDLE' | 'BUSY' | 'OFFLINE'
  tunnel_port: number
  battery_level: number
  is_charging: boolean
  temperature_celsius: number
  current_lease_owner?: string | null
}

export const iosTunnelApi = {
  listDevices(): Promise<{ total: number; devices: IosTunnelDeviceItem[] }> {
    return http.get('/ios/tunnel/devices')
  },

  getDevice(udid: string): Promise<{ device: IosTunnelDeviceItem & { heartbeat?: any } }> {
    return http.get(`/ios/tunnel/device/${udid}`)
  },

  acquireLease(payload: {
    udid: string
    purpose?: string
    ttl_seconds?: number
    force_takeover?: boolean
  }): Promise<{ message: string; lease: IosLeaseItem }> {
    return http.post('/ios/tunnel/lease/acquire', payload)
  },

  heartbeatLease(payload: {
    udid: string
    lease_token: string
    additional_ttl_seconds?: number
  }): Promise<{ message: string; lease: IosLeaseItem }> {
    return http.post('/ios/tunnel/lease/heartbeat', payload)
  },

  releaseLease(payload: {
    udid: string
    lease_token?: string
    admin_force?: boolean
  }): Promise<{ message: string }> {
    return http.post('/ios/tunnel/lease/release', payload)
  },
  listLeases(): Promise<{ total: number; leases: IosLeaseItem[] }> {
    return http.get('/ios/tunnel/leases')
  },

  sweepHeartbeats(payload?: { timeout_seconds?: number }): Promise<{
    message: string
    offline_udids: string[]
  }> {
    return http.post('/ios/tunnel/sweep', payload || { timeout_seconds: 15.0 })
  },


  warmupWdaSession(payload: {
    udid: string
    lease_token: string
    bundle_id?: string
    capabilities?: Record<string, any>
  }): Promise<{ message: string; session: WdaSessionItem }> {
    return http.post('/ios/tunnel/wda/session/warmup', payload)
  },

  getScreenshot(udid: string, sessionId: string): Promise<{
    udid: string
    session_id: string
    screenshot_base64: string
  }> {
    return http.get(`/ios/tunnel/wda/screenshot/${udid}`, {
      params: { session_id: sessionId },
    })
  },

  dispatchGesture(payload: {
    udid: string
    session_id: string
    action: 'tap' | 'swipe' | 'home'
    x?: number
    y?: number
    end_x?: number
    end_y?: number
    duration_ms?: number
  }): Promise<{ message: string; result: any }> {
    return http.post('/ios/tunnel/wda/gesture', payload)
  },

  healWda(udid: string): Promise<{ result: string; message: string }> {
    return http.post('/ios/tunnel/wda/heal', { udid })
  },

  getPoolCapacity(): Promise<{ capacity: PoolCapacitySummary }> {
    return http.get('/ios/tunnel/pool/capacity')
  },

  getPoolDevices(): Promise<{ total: number; devices: UnifiedDeviceItem[] }> {
    return http.get('/ios/tunnel/pool/devices')
  },

  allocateDevice(payload: {
    platform?: string
    brand?: string
    min_os_version?: string
    auto_lease?: boolean
  }): Promise<{ message: string; device: UnifiedDeviceItem & { lease_token?: string } }> {
    return http.post('/ios/tunnel/pool/allocate', payload)
  },
}
