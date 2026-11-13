import { getActivePinia } from 'pinia'
import type { RecordingKind, WebRecordingStep } from '@/api'
import { useAuthStore } from '@/stores/auth'

export interface LocalRecordingDraft {
  recordId?: number | null
  kind: RecordingKind
  projectId: number
  title?: string
  targetUrl?: string
  browser?: string
  deviceId?: number | null
  deviceSerial?: string | null
  assetIds?: number[]
  steps: WebRecordingStep[]
  updatedAt: string
}

const STORAGE_PREFIX = 'atp:recording-draft:'

function resolveUserScope(userId?: number | null): string {
  if (typeof userId === 'number' && userId > 0) {
    return String(userId)
  }
  try {
    if (getActivePinia()) {
      const storeUserId = useAuthStore().user?.id
      if (typeof storeUserId === 'number' && storeUserId > 0) {
        return String(storeUserId)
      }
    }
  } catch {
    // 单元测试未挂载 Pinia 或 auth store 未就绪时回退匿名作用域
  }
  return 'anon'
}

function storageKey(projectId: number, kind: RecordingKind, userId?: number | null): string {
  return `${STORAGE_PREFIX}${resolveUserScope(userId)}:${kind}:${projectId}`
}

/**
 * 校验录制产物的外链 URL，仅允许 http(s) 或站内单斜杠相对路径，阻断 javascript:/data:/双斜杠外跳。
 */
export function safeArtifactUrl(rawUrl?: string | null): string | null {
  if (typeof rawUrl !== 'string') return null
  const trimmed = rawUrl.trim()
  if (!trimmed) return null
  if (trimmed.startsWith('/')) {
    return trimmed.startsWith('//') ? null : trimmed
  }
  try {
    const parsed = new URL(trimmed)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.toString() : null
  } catch {
    return null
  }
}

function redactUrl(raw: unknown): string | undefined {
  if (typeof raw !== 'string') return undefined
  const trimmed = raw.trim()
  if (!trimmed) return undefined
  try {
    const parsed = new URL(trimmed)
    return `${parsed.origin}${parsed.pathname}`
  } catch {
    return trimmed.split('?')[0]?.slice(0, 512) || undefined
  }
}

export function sanitizeStepsForLocalDraft(rawSteps: unknown): WebRecordingStep[] {
  if (!Array.isArray(rawSteps)) return []
  const sanitized: WebRecordingStep[] = []
  for (const item of rawSteps.slice(0, 300)) {
    if (!item || typeof item !== 'object') continue
    const raw = item as Record<string, unknown>
    const action = typeof raw.action === 'string' ? raw.action.trim() : ''
    if (!action) continue
    const name = typeof raw.name === 'string' && raw.name.trim() ? raw.name.trim() : action
    const params =
      raw.params && typeof raw.params === 'object'
        ? { ...(raw.params as Record<string, unknown>) }
        : {}
    if (params.sensitive || params.is_password || name.includes('敏感值')) {
      if ('value' in params) params.value = ''
      if ('text' in params) params.text = ''
      delete params.is_password
    }
    if (typeof params.url === 'string') {
      params.url = redactUrl(params.url) || ''
    }
    sanitized.push({ action, name, params })
  }
  return sanitized
}

export function saveLocalRecordingDraft(
  draft: Omit<LocalRecordingDraft, 'steps' | 'updatedAt'> & {
    steps: unknown[]
    updatedAt?: string
  },
  userId?: number | null,
): LocalRecordingDraft | null {
  if (!draft.projectId || draft.projectId <= 0) return null
  const steps = sanitizeStepsForLocalDraft(draft.steps)
  if (steps.length === 0) {
    clearLocalRecordingDraft(draft.projectId, draft.kind)
    return null
  }
  const normalized: LocalRecordingDraft = {
    recordId: draft.recordId ?? null,
    kind: draft.kind,
    projectId: draft.projectId,
    title: draft.title?.slice(0, 255),
    targetUrl: redactUrl(draft.targetUrl),
    browser: draft.browser,
    deviceId: draft.deviceId ?? null,
    deviceSerial: draft.deviceSerial ?? null,
    assetIds: Array.isArray(draft.assetIds) ? draft.assetIds.slice(0, 500) : [],
    steps,
    updatedAt: draft.updatedAt || new Date().toISOString(),
  }
  if (typeof window === 'undefined' || !window.localStorage) {
    return normalized
  }
  try {
    window.localStorage.setItem(storageKey(draft.projectId, draft.kind, userId), JSON.stringify(normalized))
  } catch {
    // 存储配额不足或无痕模式禁用 localStorage 时静默降级，仍依赖后端记录
  }
  return normalized
}

export function loadLocalRecordingDraft(
  projectId: number | null | undefined,
  kind: RecordingKind,
  userId?: number | null,
): LocalRecordingDraft | null {
  if (!projectId || projectId <= 0 || typeof window === 'undefined' || !window.localStorage) {
    return null
  }
  try {
    const raw = window.localStorage.getItem(storageKey(projectId, kind, userId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<LocalRecordingDraft>
    const steps = sanitizeStepsForLocalDraft(parsed.steps)
    if (steps.length === 0) {
      clearLocalRecordingDraft(projectId, kind)
      return null
    }
    return {
      recordId: typeof parsed.recordId === 'number' ? parsed.recordId : null,
      kind,
      projectId,
      title: typeof parsed.title === 'string' ? parsed.title : undefined,
      targetUrl: redactUrl(parsed.targetUrl),
      browser: typeof parsed.browser === 'string' ? parsed.browser : undefined,
      deviceId: typeof parsed.deviceId === 'number' ? parsed.deviceId : null,
      deviceSerial: typeof parsed.deviceSerial === 'string' ? parsed.deviceSerial : null,
      assetIds: Array.isArray(parsed.assetIds) ? parsed.assetIds.filter((v): v is number => typeof v === 'number') : [],
      steps,
      updatedAt: typeof parsed.updatedAt === 'string' ? parsed.updatedAt : '',
    }
  } catch {
    return null
  }
}

export function clearLocalRecordingDraft(
  projectId: number | null | undefined,
  kind: RecordingKind,
  userId?: number | null,
): void {
  if (!projectId || projectId <= 0 || typeof window === 'undefined' || !window.localStorage) {
    return
  }
  try {
    window.localStorage.removeItem(storageKey(projectId, kind, userId))
  } catch {
    // ignore storage errors
  }
}
