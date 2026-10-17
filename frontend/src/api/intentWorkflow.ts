import http from './http'
import type { WorkflowNodeItem, WorkflowEdgeItem } from './hybridWorkflow'
export interface IntentSemanticSlotsDTO {
  raw_prompt: string
  business_domain: string
  protocols: string[]
  actions: string[]
  extracted_entities: string[]
  suggested_node_count: number
  analyzed_at: string
}

export interface SynthesizedWorkflowDAGDTO {
  synthesis_id: string
  workflow_id: string
  workflow_name: string
  semantic_summary: string
  nodes: WorkflowNodeItem[]
  edges: WorkflowEdgeItem[]
  variable_bindings: Record<string, string>
  slots: IntentSemanticSlotsDTO
  created_at: string
}

export interface DetectedUIElementDTO {
  element_id: string
  element_type: string
  label: string
  bounding_box: number[]
  center_coords: [number, number]
  clickable: boolean
  confidence: number
}

export interface UIStateNodeDTO {
  state_id: string
  screen_name: string
  ui_signature: string
  elements: DetectedUIElementDTO[]
  visit_count: number
  first_seen_at: string
}

export interface StateTransitionEdgeDTO {
  transition_id: string
  from_state_id: string
  to_state_id: string
  action_type: string
  target_element_label: string
  performed_at: string
}

export interface ExplorationSessionDTO {
  session_id: string
  platform: 'web' | 'android' | 'ios'
  device_id: string
  goal: string
  status: 'ACTIVE' | 'COMPLETED' | 'CIRCUIT_BROKEN'
  states_count: number
  transitions_count: number
  states: UIStateNodeDTO[]
  transitions: StateTransitionEdgeDTO[]
  current_state_id: string | null
  step_count: number
  max_steps: number
  started_at: string
}

export interface ExplorationAnomalyDTO {
  anomaly_id: string
  session_id: string
  anomaly_type: 'WHITE_SCREEN' | 'BLACK_SCREEN' | 'STATE_DEADLOCK' | 'ERROR_DIALOG' | 'APP_CRASH'
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM'
  state_id: string | null
  title: string
  description: string
  suggested_action: string
  detected_at: string
}

export const intentWorkflowApi = {
  generateWorkflow(payload: {
    prompt: string
    workflow_id?: string
    workflow_name?: string
  }): Promise<{ message: string; synthesis: SynthesizedWorkflowDAGDTO }> {
    return http.post('/workflow/intent/generate', payload)
  },

  refineWorkflow(payload: {
    synthesis_id: string
    refinement_prompt: string
  }): Promise<{ message: string; synthesis: SynthesizedWorkflowDAGDTO }> {
    return http.post('/workflow/intent/refine', payload)
  },

  getSynthesis(synthesisId: string): Promise<{ synthesis: SynthesizedWorkflowDAGDTO }> {
    return http.get(`/workflow/intent/${synthesisId}`)
  },

  listHistory(limit: number = 50): Promise<{ total: number; history: SynthesizedWorkflowDAGDTO[] }> {
    return http.get('/workflow/intent/history/list', { params: { limit } })
  },

  startExploration(payload: {
    platform?: string
    device_id?: string
    goal?: string
    max_steps?: number
  }): Promise<{ message: string; session: ExplorationSessionDTO }> {
    return http.post('/workflow/intent/exploration/start', payload)
  },

  stepExploration(payload: {
    session_id: string
    screenshot_base64: string
    consecutive_same_state_count?: number
  }): Promise<{
    message: string
    action: { action_type: string; target_label?: string; coords?: [number, number]; input_text?: string }
    anomaly: ExplorationAnomalyDTO | null
    current_step: number
    states_count: number
  }> {
    return http.post('/workflow/intent/exploration/step', payload)
  },

  getExploration(sessionId: string): Promise<{ session: ExplorationSessionDTO }> {
    return http.get(`/workflow/intent/exploration/${sessionId}`)
  },

  listExplorationSessions(limit: number = 50): Promise<{ total: number; sessions: ExplorationSessionDTO[] }> {
    return http.get('/workflow/intent/exploration/list/sessions', { params: { limit } })
  },

  convertExploration(payload: {
    session_id: string
    workflow_id?: string
    workflow_name?: string
  }): Promise<{ message: string; workflow_draft: any }> {
    return http.post('/workflow/intent/exploration/convert', payload)
  },

  listAnomalies(sessionId?: string, limit: number = 50): Promise<{ total: number; anomalies: ExplorationAnomalyDTO[] }> {
    return http.get('/workflow/intent/exploration/anomalies/list', { params: { session_id: sessionId, limit } })
  },
}
