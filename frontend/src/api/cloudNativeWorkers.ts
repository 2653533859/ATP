import http from './http'

export type ContainerRuntime = 'kubernetes' | 'docker' | 'containerd'
export type PodStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'terminated'

export interface ResourceQuotaItem {
  cpu_limit_cores: number
  memory_limit_mb: number
  cpu_request_cores: number
  memory_request_mb: number
}

export interface EphemeralWorkerPodItem {
  pod_id: string
  worker_name: string
  image: string
  runtime: ContainerRuntime
  assigned_queue: string
  resource_quota: ResourceQuotaItem
  status: PodStatus
  created_at: string
  started_at: string | null
  terminated_at: string | null
  exit_code: number | null
  logs_count: number
  logs?: string[]
  metadata?: Record<string, any>
}

export interface ProvisionPodRequest {
  worker_name: string
  image?: string
  assigned_queue?: string
  runtime?: ContainerRuntime
  cpu_limit_cores?: number
  memory_limit_mb?: number
  cpu_request_cores?: number
  memory_request_mb?: number
  metadata?: Record<string, any>
}

export const cloudNativeWorkersApi = {
  provisionPod(data: ProvisionPodRequest): Promise<{ message: string; pod: EphemeralWorkerPodItem }> {
    return http.post('/cloud-native/workers/provision', data)
  },

  listPods(params?: { assigned_queue?: string; status?: string }): Promise<{ total: number; pods: EphemeralWorkerPodItem[] }> {
    return http.get('/cloud-native/workers', { params })
  },

  getPod(podId: string): Promise<EphemeralWorkerPodItem> {
    return http.get(`/cloud-native/workers/${podId}`)
  },

  terminatePod(podId: string, exitCode: number = 0): Promise<{ message: string; pod: EphemeralWorkerPodItem }> {
    return http.post(`/cloud-native/workers/${podId}/terminate`, { exit_code: exitCode })
  },

  reapStalePods(maxLifetimeSec: number = 3600.0): Promise<{ message: string; reaped_count: number; reaped_pod_ids: string[] }> {
    return http.post('/cloud-native/workers/reap', null, { params: { max_lifetime_sec: maxLifetimeSec } })
  },
}
