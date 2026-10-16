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

export type HpaScalingDirection = 'scale_up' | 'scale_down' | 'maintain'

export interface HpaPolicyItem {
  policy_id: string
  target_queue: string
  min_replicas: number
  max_replicas: number
  target_concurrency_per_pod: number
  target_latency_slo_sec: number
  scale_up_stabilization_sec: number
  scale_down_stabilization_sec: number
  enabled: boolean
}

export interface CreateHpaPolicyRequest {
  policy_id: string
  target_queue?: string
  min_replicas?: number
  max_replicas?: number
  target_concurrency_per_pod?: number
  target_latency_slo_sec?: number
  scale_up_stabilization_sec?: number
  scale_down_stabilization_sec?: number
  enabled?: boolean
}

export interface HpaEvaluationDecisionItem {
  decision_id: string
  policy_id: string
  target_queue: string
  direction: HpaScalingDirection
  current_replicas: number
  desired_replicas: number
  replicas_delta: number
  reason: string
  evaluated_at: string
  metrics_snapshot: {
    queue_name?: string
    current_queue_depth?: number
    running_tasks_count?: number
    p95_queue_latency_sec?: number
    current_replicas?: number
  }
}

export interface EvaluateHpaRequest {
  policy_id: string
  current_queue_depth: number
  running_tasks_count: number
  p95_queue_latency_sec: number
  current_replicas: number
}

export interface ApplyHpaScalingRequest {
  decision_id: string
  policy_id: string
  direction: string
  replicas_delta: number
  target_queue?: string
}

export type ImageCategory = 'python' | 'nodejs' | 'android_sdk' | 'browser' | 'performance' | 'generic'

export interface WorkerImageItem {
  image_id: string
  name: string
  image_url: string
  category: ImageCategory
  tags: string[]
  is_default: boolean
  weight: number
  min_cpu_cores: number
  min_memory_mb: number
  created_at: string
  metadata?: Record<string, any>
}

export interface RegisterWorkerImageRequest {
  image_id: string
  name: string
  image_url: string
  category?: ImageCategory
  tags?: string[]
  is_default?: boolean
  weight?: number
  min_cpu_cores?: number
  min_memory_mb?: number
  metadata?: Record<string, any>
}

export interface ResolveWorkerImageRequest {
  required_tags: string[]
  category?: string
  available_cpu_cores?: number
  available_memory_mb?: number
}

export interface ImageRouteMatchResult {
  matched: boolean
  selected_image: WorkerImageItem
  match_score: number
  matched_tags: string[]
  unmatched_tags: string[]
  is_fallback: boolean
  reason: string
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

export const hpaAutoscalingApi = {
  createPolicy(data: CreateHpaPolicyRequest): Promise<{ message: string; policy: HpaPolicyItem }> {
    return http.post('/cloud-native/autoscaling/policies', data)
  },

  listPolicies(): Promise<{ total: number; policies: HpaPolicyItem[] }> {
    return http.get('/cloud-native/autoscaling/policies')
  },

  evaluateHpa(data: EvaluateHpaRequest): Promise<HpaEvaluationDecisionItem> {
    return http.post('/cloud-native/autoscaling/evaluate', data)
  },

  applyScaling(data: ApplyHpaScalingRequest): Promise<{
    message: string
    policy_id: string
    direction: string
    replicas_delta: number
    executed_actions: string[]
  }> {
    return http.post('/cloud-native/autoscaling/apply', data)
  },

  listHistory(policyId?: string): Promise<{ total: number; history: HpaEvaluationDecisionItem[] }> {
    return http.get('/cloud-native/autoscaling/history', { params: { policy_id: policyId } })
  },
}

export const workerImageMatrixApi = {
  registerImage(data: RegisterWorkerImageRequest): Promise<{ message: string; image: WorkerImageItem }> {
    return http.post('/cloud-native/images/register', data)
  },

  listImages(category?: string): Promise<{ total: number; images: WorkerImageItem[] }> {
    return http.get('/cloud-native/images', { params: { category } })
  },

  getImage(imageId: string): Promise<WorkerImageItem> {
    return http.get(`/cloud-native/images/${imageId}`)
  },

  deleteImage(imageId: string): Promise<{ message: string }> {
    return http.delete(`/cloud-native/images/${imageId}`)
  },

  resolveImage(data: ResolveWorkerImageRequest): Promise<ImageRouteMatchResult> {
    return http.post('/cloud-native/images/resolve', data)
  },
}
