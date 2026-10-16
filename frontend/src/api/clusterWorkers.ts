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

export type TaskPriority = 'P0' | 'P1' | 'P2' | 'P3'
export type TaskStatus = 'queued' | 'running' | 'suspended' | 'completed' | 'aborted'

export interface QueuedTaskItem {
  task_id: string
  task_name: string
  queue_name: string
  priority: TaskPriority
  assigned_worker_id: string | null
  status: TaskStatus
  enqueued_at: number
  started_at: number | null
  estimated_duration_sec: number
  preempted_count: number
  preempted_by_task_id: string | null
  retry_count?: number
  last_failed_worker_id?: string | null
}

export interface TaskEtaResult {
  task_id: string
  status: string
  queue_position: number
  total_queued_in_line: number
  estimated_wait_seconds: number
  active_workers_count: number
  message: string
}

export interface EnqueueTaskRequest {
  task_name: string
  queue_name?: string
  priority?: TaskPriority
  estimated_duration_sec?: number
  allow_preemption?: boolean
}

export interface FailoverRecoveredTask {
  task_id: string
  task_name: string
  dead_worker_id: string
  action: 'rescheduled' | 'aborted'
  retry_count?: number
  max_retries?: number
  reason?: string
}

export interface FailoverSummaryReport {
  report_id: string
  timestamp: string
  dead_worker_ids: string[]
  recovered_tasks: FailoverRecoveredTask[]
  aborted_tasks: FailoverRecoveredTask[]
  orphan_tasks_scanned: number
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

  enqueueTask(data: EnqueueTaskRequest): Promise<{ task: QueuedTaskItem; preempted: boolean }> {
    return http.post('/cluster/workers/tasks/enqueue', data)
  },

  listTasks(queueName?: string): Promise<{ total: number; tasks: QueuedTaskItem[] }> {
    return http.get('/cluster/workers/tasks', { params: { queue_name: queueName } })
  },

  completeTask(taskId: string, statusCode: string = 'completed'): Promise<{ message: string; task: QueuedTaskItem }> {
    return http.post(`/cluster/workers/tasks/${taskId}/complete`, null, {
      params: { status_code_str: statusCode },
    })
  },

  getTaskEta(taskId: string): Promise<TaskEtaResult> {
    return http.get(`/cluster/workers/tasks/${taskId}/eta`)
  },

  triggerFailoverScan(maxHeartbeatAgeSec: number = 30.0): Promise<FailoverSummaryReport> {
    return http.post('/cluster/workers/failover/scan', null, {
      params: { max_heartbeat_age_sec: maxHeartbeatAgeSec },
    })
  },

  listFailoverHistory(): Promise<{ total: number; history: FailoverSummaryReport[] }> {
    return http.get('/cluster/workers/failover/history')
  },
}
