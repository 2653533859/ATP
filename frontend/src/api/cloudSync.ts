import http from './http'

export interface CloudSyncLocalStatus {
  local_mode: boolean
  machine_id: string | null
  machine_name: string | null
  cloud_sync_url: string
  cloud_sync_enabled: boolean
  stats: {
    pending: number
    syncing: number
    synced: number
    failed: number
    total: number
  }
  recent_items: Array<{
    id: number
    unique_key: string
    run_type: string
    run_id: number
    status: 'pending' | 'syncing' | 'synced' | 'failed'
    synced_at?: string | null
    last_error?: string | null
    created_at: string
  }>
}

export interface CloudRunItem {
  id: number
  client_id: string
  machine_name: string
  unique_key: string
  run_type: string
  run_id: number
  project_name: string
  project_code: string
  title: string
  status: string
  started_at?: string | null
  finished_at?: string | null
  duration_ms?: number | null
  triggered_by: string
  environment?: string | null
  metrics: Record<string, any>
  error_summary?: string | null
  step_count: number
  reported_at?: string | null
}

export interface CloudStepItem {
  step_index: number
  name: string
  status: string
  duration_ms?: number | null
  error_summary?: string | null
}

export interface CloudRunDetail extends CloudRunItem {
  steps: CloudStepItem[]
}

export interface CloudSyncStats {
  total_runs: number
  status_distribution: Record<string, number>
  type_distribution: Record<string, number>
  connected_clients: Array<{
    client_id: string
    machine_name: string
    runs_count: number
  }>
}

export interface RunSyncStatus {
  sync_status: 'synced' | 'pending' | 'syncing' | 'failed' | 'not_queued' | 'server_mode'
  synced_at?: string | null
  last_error?: string | null
  attempts?: number
  unique_key?: string
}

export const cloudSyncApi = {
  getLocalStatus: () => http.get<unknown, CloudSyncLocalStatus>('/cloud-sync/local/status'),
  syncNow: () =>
    http.post<unknown, { status: string; synced: number; failed: number; processed: number }>(
      '/cloud-sync/local/sync-now'
    ),
  getRunSyncStatus: (runType: string, runId: number) =>
    http.get<unknown, RunSyncStatus>(`/cloud-sync/local/runs/${runType}/${runId}`),
  listRuns: (params?: {
    client_id?: string
    project_code?: string
    run_type?: string
    status?: string
    page?: number
    page_size?: number
  }) =>
    http.get<unknown, { items: CloudRunItem[]; total: number; page: number; page_size: number }>(
      '/cloud-sync/runs',
      { params }
    ),
  getRunDetail: (uniqueKey: string) =>
    http.get<unknown, CloudRunDetail>(`/cloud-sync/runs/${encodeURIComponent(uniqueKey)}`),
  getStats: () => http.get<unknown, CloudSyncStats>('/cloud-sync/stats'),
}
