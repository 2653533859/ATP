import http from './http'

export type CapacityLevel =
  | 'HEALTHY_IDLE'
  | 'MODERATE_LOAD'
  | 'HEAVY_LOAD'
  | 'OVERLOADED'
  | 'DRAINING'
  | 'OFFLINE'

export interface ClusterWorkerNodeItem {
  worker_id: string
  hostname: string
  ip_address: string
  queues: string[]
  current_concurrency: number
  max_concurrency: number
  cpu_usage_pct: number
  memory_usage_pct: number
  heartbeat_timestamp: number
  is_alive: boolean
  load_score: number
  capacity_score: number
  capacity_level: CapacityLevel
  weight: number
}

export interface ClusterCapacityOverview {
  total_nodes_registered: number
  total_alive_nodes: number
  total_concurrency_slots: number
  total_active_tasks: number
  cluster_utilization_pct: number
  average_cpu_pct: number
  average_memory_pct: number
  health_distribution: Record<string, number>
}

export const clusterWorkersApi = {
  listWorkers(params?: { queue?: string; only_alive?: boolean }): Promise<{
    total: number
    workers: ClusterWorkerNodeItem[]
  }> {
    return http.get('/cluster/workers', { params })
  },

  getOverview(): Promise<ClusterCapacityOverview> {
    return http.get('/cluster/workers/overview')
  },

  selectOptimal(data: {
    required_queue?: string
    exclude_worker_ids?: string[]
  }): Promise<{
    selected: boolean
    worker: ClusterWorkerNodeItem
  }> {
    return http.post('/cluster/workers/select-optimal', {
      required_queue: data.required_queue || 'default',
      exclude_worker_ids: data.exclude_worker_ids || [],
    })
  },
}
