import type { ApiRequestTemplate } from '@/utils/apiTemplates'

const KEY_PREFIX = 'atp:custom_api_request_templates:'
const MAX_CUSTOM_TEMPLATES = 30

function buildStorageKey(projectId: number | null): string {
  return `${KEY_PREFIX}${projectId ?? 'global'}`
}

function getSafeStorage(): Storage | null {
  try {
    return typeof window !== 'undefined' && window.localStorage ? window.localStorage : null
  } catch {
    return null
  }
}

export function loadCustomRequestTemplates(projectId: number | null): ApiRequestTemplate[] {
  const storage = getSafeStorage()
  if (!storage) return []
  try {
    const raw = storage.getItem(buildStorageKey(projectId))
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (item): item is ApiRequestTemplate =>
        Boolean(item) &&
        typeof item === 'object' &&
        typeof item.id === 'string' &&
        typeof item.label === 'string' &&
        typeof item.method === 'string',
    )
  } catch {
    return []
  }
}

function persistCustomRequestTemplates(projectId: number | null, items: ApiRequestTemplate[]): ApiRequestTemplate[] {
  const storage = getSafeStorage()
  const capped = items.slice(0, MAX_CUSTOM_TEMPLATES)
  if (storage) {
    try {
      storage.setItem(buildStorageKey(projectId), JSON.stringify(capped))
    } catch {
      // Ignore quota errors in constrained browser environments
    }
  }
  return capped
}

export function saveCustomRequestTemplate(
  projectId: number | null,
  template: Omit<ApiRequestTemplate, 'id'> & { id?: string },
): ApiRequestTemplate[] {
  const existing = loadCustomRequestTemplates(projectId)
  const id = template.id || `custom_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
  const entry: ApiRequestTemplate = {
    ...template,
    id,
    description: template.description || `${template.method} · 自定义请求模板`,
  }
  const filtered = existing.filter((item) => item.id !== id)
  return persistCustomRequestTemplates(projectId, [entry, ...filtered])
}

export function deleteCustomRequestTemplate(projectId: number | null, id: string): ApiRequestTemplate[] {
  const existing = loadCustomRequestTemplates(projectId)
  return persistCustomRequestTemplates(
    projectId,
    existing.filter((item) => item.id !== id),
  )
}
