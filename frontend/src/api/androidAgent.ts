import http from './http'

/** Android 自然语言 Agent 会话、事件、控制与草稿/回放接口（M2 最小控制页 + M3 草稿链路）。 */

export type AgentSessionStatus =
  | 'created'
  | 'prechecking'
  | 'running'
  | 'pause_requested'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled'

export interface AgentSessionItem {
  id: number
  project_id: number
  device_id: number | null
  created_by: number | null
  title: string
  goal: string
  expected_outcome: string
  package_name: string
  llm_config_id: number | null
  status: AgentSessionStatus | string
  controller: string
  version: number
  control_epoch: number
  lease_token: string | null
  budget_max_steps: number
  budget_max_calls: number
  steps_count: number
  model_calls_count: number
  total_tokens: number
  error_code: string | null
  context_values: Record<string, string>
  terminal_assertions?: Array<{ type: 'element_visible' | 'element_absent'; resource_id: string }>
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}

export interface AgentEventItem {
  id: number
  session_id: number
  seq: number
  event_type: string
  payload: Record<string, unknown>
  artifact_refs: string[]
  created_at: string
}

export interface AgentEventsPage {
  items: AgentEventItem[]
  next_seq: number
  has_more: boolean
}

export interface AgentRunResult {
  status: string
  reason: string
  steps: number
  model_calls: number
  tokens: number
}

export interface AgentControlResult {
  session_id: number
  status: string
  controller: string
  control_epoch: number
  version: number
  message: string
}

export interface AgentAssertionItem {
  type: 'element_visible' | 'element_absent'
  resource_id: string
}

export interface AgentCompletePayload {
  terminal_assertion_confirmed: boolean
  terminal_assertions: AgentAssertionItem[]
  summary?: string
  outcome?: 'success' | 'partial'
}

export interface AgentManualActionPayload {
  action: 'tap' | 'input' | 'back' | 'wait' | 'swipe'
  params?: Record<string, unknown>
  idempotency_key?: string
  reason?: string
}

export interface AgentManualActionResult {
  command_id: number
  session_id: number
  seq: number
  control_epoch: number
  action: string
  status: string
  idempotency_key: string
  error_code?: string | null
}

export interface AgentDraftPatchPayload {
  expected_version: number
  steps?: Array<Record<string, unknown>>
  assertions?: Array<Record<string, unknown>>
  preconditions?: string[]
}

export interface AgentSessionCreatePayload {
  device_id: number
  package_name: string
  goal: string
  expected_outcome: string
  title?: string
  llm_config_id?: number | null
  context_values?: Record<string, string>
  budget?: { max_steps?: number; max_calls?: number; max_duration_seconds?: number }
}

export interface AgentDraftItem {
  id: number
  project_id: number
  session_id: number
  version: number
  schema_version: number
  status: string
  content_hash: string
  steps: Array<Record<string, unknown>>
  assertions: Array<Record<string, unknown>>
  preconditions: string[]
  variables: string[]
  blocking_issues: Array<{ code: string; message: string; source_seq?: number }>
  source_map: Record<string, unknown>
  environment_snapshot: Record<string, unknown>
  published_case_id: number | null
  created_at: string
}

export interface AgentReplayPreview {
  draft_id: number
  draft_version: number
  content_hash: string
  ready: boolean
  frozen_snapshot: Record<string, unknown>
  items: Array<{ code: string; status: string; message: string }>
}

export interface AgentReplayItem {
  id: number
  draft_id: number
  draft_version: number
  status: string
  case_id: number | null
  run_id: number | null
}

export interface AgentReplayHandoff {
  replay: AgentReplayItem
  case_id: number
  run_id: number
  frozen_snapshot: Record<string, unknown>
}

export interface AgentPublishResult {
  draft_id: number
  draft_version: number
  case_id: number
  verified_replay_id: number
  published: boolean
  idempotent_replay: boolean
}

export interface AgentVisionModelItem {
  id: number
  name: string
  provider: string
  model_name: string
  enabled: boolean
  supports_vision: boolean
  description?: string | null
}

const base = (projectId: number) => `/projects/${projectId}/android-agent`

export const androidAgentApi = {
  listModels: (projectId: number) => http.get<unknown, AgentVisionModelItem[]>(`${base(projectId)}/models`),
  listSessions: (projectId: number, limit = 30) =>
    http.get<unknown, AgentSessionItem[]>(`${base(projectId)}/sessions`, { params: { limit } }),
  createSession: (projectId: number, payload: AgentSessionCreatePayload, idempotencyKey: string) =>
    http.post<unknown, AgentSessionItem>(`${base(projectId)}/sessions`, payload, {
      headers: { 'Idempotency-Key': idempotencyKey },
    }),
  startSession: (projectId: number, sessionId: number) =>
    http.post<unknown, AgentSessionItem>(`${base(projectId)}/sessions/${sessionId}/start`),
  getSession: (projectId: number, sessionId: number) =>
    http.get<unknown, AgentSessionItem>(`${base(projectId)}/sessions/${sessionId}`),
  runSession: (projectId: number, sessionId: number, maxRounds = 30) =>
    http.post<unknown, AgentRunResult>(`${base(projectId)}/sessions/${sessionId}/run`, undefined, {
      params: { max_rounds: maxRounds },
    }),
  completeSession: (projectId: number, sessionId: number, payload: AgentCompletePayload) =>
    http.post<unknown, AgentSessionItem>(`${base(projectId)}/sessions/${sessionId}/complete`, payload),
  events: (projectId: number, sessionId: number, afterSeq = 0, limit = 100) =>
    http.get<unknown, AgentEventsPage>(`${base(projectId)}/sessions/${sessionId}/events`, {
      params: { after_seq: afterSeq, limit },
    }),
  control: (
    projectId: number,
    sessionId: number,
    action: 'pause' | 'takeover' | 'resume' | 'cancel',
    expectedVersion: number,
    reason = '',
  ) =>
    http.post<unknown, AgentControlResult>(`${base(projectId)}/sessions/${sessionId}/control`, {
      action,
      expected_version: expectedVersion,
      reason,
    }),
  manualAction: (projectId: number, sessionId: number, payload: AgentManualActionPayload) =>
    http.post<unknown, AgentManualActionResult>(`${base(projectId)}/sessions/${sessionId}/manual-action`, payload),
  listSessionDrafts: (projectId: number, sessionId: number) =>
    http.get<unknown, AgentDraftItem[]>(`${base(projectId)}/sessions/${sessionId}/drafts`),
  compileDraft: (projectId: number, sessionId: number) =>
    http.post<unknown, AgentDraftItem>(`${base(projectId)}/sessions/${sessionId}/drafts`, {}),
  getDraft: (projectId: number, draftId: number) =>
    http.get<unknown, AgentDraftItem>(`${base(projectId)}/drafts/${draftId}`),
  updateDraft: (projectId: number, draftId: number, payload: AgentDraftPatchPayload) =>
    http.patch<unknown, AgentDraftItem>(`${base(projectId)}/drafts/${draftId}`, payload),
  replayPreview: (projectId: number, draftId: number) =>
    http.get<unknown, AgentReplayPreview>(`${base(projectId)}/drafts/${draftId}/replay-preview`),
  startReplay: (
    projectId: number,
    draftId: number,
    payload: { initial_state_confirmed: boolean; module_id: number; device_id?: number; idempotency_key: string },
  ) => http.post<unknown, AgentReplayHandoff>(`${base(projectId)}/drafts/${draftId}/replays`, payload),
  getReplay: (projectId: number, replayId: number) =>
    http.get<unknown, AgentReplayItem>(`${base(projectId)}/replays/${replayId}`),
  publishDraft: (projectId: number, draftId: number, idempotencyKey: string) =>
    http.post<unknown, AgentPublishResult>(`${base(projectId)}/drafts/${draftId}/publish`, undefined, {
      headers: { 'Idempotency-Key': idempotencyKey },
    }),
}
