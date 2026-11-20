export interface LocalAndroidWorkerIdentity {
  worker_id: string
  hostname?: string
  adb_ok?: boolean
  instance_generation?: number | null
  queues?: string[]
}

const DEFAULT_LOCAL_IDENTITY_PORT = 17321
const DEFAULT_PROBE_TIMEOUT_MS = 800

function resolveIdentityPort(port?: number): number {
  if (typeof port === 'number' && Number.isFinite(port) && port > 0) {
    return Math.floor(port)
  }
  const envPort = Number(import.meta.env.VITE_ANDROID_WORKER_IDENTITY_PORT)
  if (Number.isFinite(envPort) && envPort > 0) {
    return Math.floor(envPort)
  }
  return DEFAULT_LOCAL_IDENTITY_PORT
}

export async function probeLocalAndroidWorker(options?: {
  port?: number
  timeoutMs?: number
}): Promise<LocalAndroidWorkerIdentity | null> {
  if (typeof window === 'undefined' || typeof fetch !== 'function') {
    return null
  }
  const port = resolveIdentityPort(options?.port)
  const timeoutMs = options?.timeoutMs ?? DEFAULT_PROBE_TIMEOUT_MS
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null
  const timer = controller ? window.setTimeout(() => controller.abort(), timeoutMs) : null

  try {
    const response = await fetch(`http://127.0.0.1:${port}/identity`, {
      method: 'GET',
      mode: 'cors',
      cache: 'no-store',
      ...(controller ? { signal: controller.signal } : {}),
    })
    if (!response.ok) return null
    const data = (await response.json()) as Record<string, unknown>
    const workerId = typeof data?.worker_id === 'string' ? data.worker_id.trim() : ''
    if (!workerId) return null
    return {
      worker_id: workerId,
      hostname: typeof data.hostname === 'string' ? data.hostname : undefined,
      adb_ok: typeof data.adb_ok === 'boolean' ? data.adb_ok : undefined,
      instance_generation:
        typeof data.instance_generation === 'number' ? data.instance_generation : null,
      queues: Array.isArray(data.queues)
        ? data.queues.filter((item): item is string => typeof item === 'string')
        : undefined,
    }
  } catch {
    return null
  } finally {
    if (timer !== null) {
      window.clearTimeout(timer)
    }
  }
}
