export type DispatchStatus = 'pending' | 'publishing' | 'submitted' | 'uncertain' | 'blocked' | 'skipped'
export function normalizeDispatchStatus(value: unknown): DispatchStatus | undefined {
  if (typeof value === 'string' && ['pending', 'publishing', 'submitted', 'uncertain', 'blocked', 'skipped'].includes(value)) return value as DispatchStatus
}
export interface HermesActionReceipt {
  id: string
  action: string
  status: 'pending' | 'completed' | 'uncertain'
  createdAt: string
  path: string
  resourceId?: number
  runStatus?: string
  dispatchStatus?: DispatchStatus
}
const prefix = 'atp-hermes-receipts-v1'
const actions = new Set(['record', 'api', 'regression', 'repair', 'android', 'defect', 'knowledge', 'summary'])
function normalizeReceipt(value: unknown, projectId: number): HermesActionReceipt | undefined {
  if (!value || typeof value !== 'object') return
  const item = value as Record<string, unknown>
  if (typeof item.id !== 'string' || item.id.length > 64 || typeof item.action !== 'string' || !actions.has(item.action)) return
  if (!['pending', 'completed', 'uncertain'].includes(String(item.status)) || typeof item.createdAt !== 'string' || !Number.isFinite(Date.parse(item.createdAt))) return
  if (typeof item.path !== 'string' || !/^\/(cases|runs|suites|bugs|knowledge)(\/\d+)?(\?project_id=\d+)?$/.test(item.path)) return
  const query = item.path.split('?')[1]
  if (query && query !== `project_id=${projectId}`) return
  return {
    id: item.id, action: item.action, createdAt: item.createdAt, path: item.path,
    status: item.status === 'completed' ? 'completed' : 'uncertain',
    ...(typeof item.resourceId === 'number' && Number.isSafeInteger(item.resourceId) && item.resourceId > 0 ? { resourceId: item.resourceId } : {}),
    ...(typeof item.runStatus === 'string' && ['pending', 'running', 'passed', 'failed', 'error', 'cancelled', 'missing', 'unverified'].includes(item.runStatus) ? { runStatus: item.runStatus } : {}),
    ...(normalizeDispatchStatus(item.dispatchStatus) ? { dispatchStatus: normalizeDispatchStatus(item.dispatchStatus) } : {}),
  }
}
export function readActionHistory(userId: number, projectId: number): HermesActionReceipt[] {
  try {
    const data: unknown = JSON.parse(sessionStorage.getItem(`${prefix}:${userId}:${projectId}`) || '[]')
    if (!Array.isArray(data)) return []
    return data.map(item => normalizeReceipt(item, projectId)).filter((item): item is HermesActionReceipt => !!item).slice(0, 20)
  } catch { return [] }
}
export function writeActionHistory(userId: number, projectId: number, items: HermesActionReceipt[]): boolean {
  try { sessionStorage.setItem(`${prefix}:${userId}:${projectId}`, JSON.stringify(items.slice(0, 20))); return true }
  catch { return false }
}
