import http from './http'

export interface DeviceHealthMetricDTO {
  device_id: string
  platform: 'ios' | 'android'
  battery_temperature_c: number
  battery_level_percent: number
  battery_state: 'CHARGING' | 'DISCHARGING' | 'FULL'
  cpu_usage_percent: number
  memory_free_mb: number
  current_concurrency: number
  max_concurrency: number
  tunnel_rtt_ms: number
  health_status: 'HEALTHY' | 'WARMING' | 'OVERHEATED' | 'LOW_BATTERY' | 'OFFLINE'
  health_score: number
  recorded_at: string
}

export interface CandidateEvaluationDTO {
  device_id: string
  platform: string
  eligible: boolean
  disqualify_reason: string
  health_score: number
  load_margin_score: number
  latency_score: number
  affinity_score: number
  composite_fitness: number
}

export interface RoutingDecisionDTO {
  decision_id: string
  task_id: string
  target_platform: string
  status: 'ROUTED' | 'QUEUED' | 'NO_AVAILABLE_DEVICE'
  selected_device_id: string | null
  fitness_score: number
  candidate_evaluations: CandidateEvaluationDTO[]
  routing_reason: string
  allocated_at: string
}

export interface CapacitySummaryDTO {
  total_devices: number
  healthy_count: number
  warming_count: number
  overheated_count: number
  low_battery_count: number
  offline_count: number
  total_capacity: number
  used_concurrency: number
  available_capacity: number
  cluster_averages: {
    avg_temperature_c: number
    avg_battery_percent: number
    avg_tunnel_rtt_ms: number
  }
}

export interface BackpressureStatusDTO {
  snapshot_id: string
  current_window_size: number
  queue_depth: number
  total_fleet_capacity: number
  used_concurrency: number
  saturation_ratio: number
  average_wait_latency_ms: number
  level: 'NORMAL' | 'LIGHT_THROTTLING' | 'HEAVY_BACKPRESSURE' | 'OVERFLOW_REJECTION'
  action_description: string
  timestamp: string
}

export const fleetSchedulerApi = {
  reportTelemetry(payload: {
    device_id: string
    platform?: string
    battery_temperature_c: number
    battery_level_percent: number
    battery_state?: string
    cpu_usage_percent?: number
    memory_free_mb?: number
    current_concurrency?: number
    max_concurrency?: number
    tunnel_rtt_ms?: number
  }): Promise<{ message: string; telemetry: DeviceHealthMetricDTO }> {
    return http.post('/scheduler/telemetry/report', payload)
  },

  listDevicesTelemetry(platform?: string): Promise<{ total: number; devices: DeviceHealthMetricDTO[] }> {
    return http.get('/scheduler/devices/telemetry', { params: { platform } })
  },

  dispatchTask(payload: {
    task_id: string
    target_platform: string
    task_name?: string
    preferred_device_id?: string
    min_battery_percent?: number
    max_temperature_c?: number
    priority?: string
    estimated_duration_sec?: number
  }): Promise<{ message: string; decision: RoutingDecisionDTO; is_allocated: boolean }> {
    return http.post('/scheduler/route/dispatch', payload)
  },

  releaseLease(payload: {
    device_id: string
    task_id: string
  }): Promise<{ message: string; released: boolean }> {
    return http.post('/scheduler/route/release', payload)
  },

  getCapacitySummary(platform?: string): Promise<CapacitySummaryDTO> {
    return http.get('/scheduler/capacity/summary', { params: { platform } })
  },

  listRoutingHistory(limit: number = 50): Promise<{ total: number; history: RoutingDecisionDTO[] }> {
    return http.get('/scheduler/routing/history', { params: { limit } })
  },

  getRoutingDecision(decisionId: string): Promise<{ decision: RoutingDecisionDTO }> {
    return http.get(`/scheduler/routing/${decisionId}`)
  },

  adjustBackpressure(payload: {
    queue_depth?: number
    average_wait_latency_ms?: number
  }): Promise<{ message: string; snapshot: BackpressureStatusDTO }> {
    return http.post('/scheduler/backpressure/adjust', payload)
  },

  getBackpressureStatus(): Promise<{ status: BackpressureStatusDTO }> {
    return http.get('/scheduler/backpressure/status')
  },

  listBackpressureSnapshots(limit: number = 50): Promise<{ total: number; snapshots: BackpressureStatusDTO[] }> {
    return http.get('/scheduler/backpressure/snapshots', { params: { limit } })
  },
}
