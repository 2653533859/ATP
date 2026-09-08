import type { FailureDiagnosisResult, HermesQueryResult } from '@/api'

export type HermesSource = { label: string; path: string }

export type HermesMessage = {
  id: number
  role: 'assistant' | 'user'
  text: string
  createdAt: string
  sources?: HermesSource[]
  taskIds?: string[]
  mode?: HermesQueryResult['mode']
  toolSteps?: Array<{ tool: string; status: string }>
  isWelcome?: boolean
  backendIndex?: number
}

export type HermesPromptKey = 'failed_tasks' | 'explain_failure' | 'test_plan' | 'quality'

export type HermesPromptOption = {
  key: HermesPromptKey
  mark: string
  title: string
  description: string
}

export type HermesDiagnosis = { taskId: string; result: FailureDiagnosisResult }
