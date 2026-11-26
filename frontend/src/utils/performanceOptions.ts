export interface PerformanceOptionsFormState {
  vus?: number
  duration: string
  spawn_rate?: number
  iterations?: number
  host: string
  max_p95_ms?: number
  max_error_rate?: number
  env: Record<string, string>
  extraKeys: string[]
}

const KNOWN_TOP_KEYS = new Set([
  'vus',
  'users',
  'concurrency',
  'duration',
  'duration_seconds',
  'run_time',
  'spawn_rate',
  'iterations',
  'host',
  'env',
  'thresholds',
])

function positiveNumber(raw: unknown): number | undefined {
  if (typeof raw === 'number' && Number.isFinite(raw) && raw > 0) return raw
  if (typeof raw === 'string' && raw.trim()) {
    const parsed = Number(raw.trim())
    if (Number.isFinite(parsed) && parsed > 0) return parsed
  }
  return undefined
}

function nonNegativeNumber(raw: unknown): number | undefined {
  if (typeof raw === 'number' && Number.isFinite(raw) && raw >= 0) return raw
  if (typeof raw === 'string' && raw.trim()) {
    const parsed = Number(raw.trim())
    if (Number.isFinite(parsed) && parsed >= 0) return parsed
  }
  return undefined
}

export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export function parsePerformanceOptionsText(text: string): {
  valid: boolean
  state: PerformanceOptionsFormState
  error?: string
} {
  const emptyState: PerformanceOptionsFormState = {
    duration: '',
    host: '',
    env: {},
    extraKeys: [],
  }
  const trimmed = text.trim()
  if (!trimmed) {
    return { valid: true, state: emptyState }
  }
  try {
    const parsed = JSON.parse(trimmed)
    if (!isPlainObject(parsed)) {
      return { valid: false, state: emptyState, error: 'Root must be a JSON object' }
    }

    const vus = positiveNumber(parsed.vus ?? parsed.users ?? parsed.concurrency)
    let duration = ''
    if (typeof parsed.duration === 'string') duration = parsed.duration
    else if (typeof parsed.run_time === 'string') duration = parsed.run_time
    else if (typeof parsed.duration_seconds === 'number') duration = `${parsed.duration_seconds}s`
    else if (typeof parsed.duration === 'number') duration = `${parsed.duration}s`

    const env: Record<string, string> = {}
    if (isPlainObject(parsed.env)) {
      for (const [k, v] of Object.entries(parsed.env)) {
        env[k] = v == null ? '' : String(v)
      }
    }

    const thresholds = isPlainObject(parsed.thresholds) ? parsed.thresholds : {}
    const extraKeys = Object.keys(parsed).filter((key) => !KNOWN_TOP_KEYS.has(key))

    return {
      valid: true,
      state: {
        vus,
        duration,
        spawn_rate: positiveNumber(parsed.spawn_rate),
        iterations: positiveNumber(parsed.iterations),
        host: typeof parsed.host === 'string' ? parsed.host : '',
        max_p95_ms: nonNegativeNumber(thresholds.max_p95_ms),
        max_error_rate: nonNegativeNumber(thresholds.max_error_rate),
        env,
        extraKeys,
      },
    }
  } catch (err) {
    return {
      valid: false,
      state: emptyState,
      error: err instanceof Error ? err.message : String(err),
    }
  }
}

export function mergePerformanceOptionsText(
  baseText: string,
  state: PerformanceOptionsFormState,
  executor?: string,
): string {
  let base: Record<string, unknown> = {}
  if (baseText.trim()) {
    try {
      const parsed = JSON.parse(baseText)
      if (isPlainObject(parsed)) {
        base = { ...parsed }
      }
    } catch {
      base = {}
    }
  }

  delete base.vus
  delete base.users
  delete base.concurrency
  delete base.duration
  delete base.duration_seconds
  delete base.run_time
  delete base.spawn_rate
  delete base.iterations
  delete base.host
  delete base.env

  if (state.vus != null && state.vus > 0) {
    if (executor === 'locust') base.users = state.vus
    else if (executor === 'grpc') base.concurrency = state.vus
    else base.vus = state.vus
  }

  const trimmedDuration = state.duration.trim()
  if (trimmedDuration) {
    if (executor === 'locust') {
      base.run_time = trimmedDuration
    } else if (executor === 'grpc') {
      const numeric = /^\d+(\.\d+)?$/.test(trimmedDuration)
        ? Number(trimmedDuration)
        : /^\d+(\.\d+)?s$/i.test(trimmedDuration)
          ? Number(trimmedDuration.slice(0, -1))
          : null
      if (numeric != null && Number.isFinite(numeric)) base.duration_seconds = numeric
      else base.duration = trimmedDuration
    } else {
      base.duration = trimmedDuration
    }
  }

  if (state.spawn_rate != null && state.spawn_rate > 0) {
    base.spawn_rate = state.spawn_rate
  }
  if (state.iterations != null && state.iterations > 0) {
    base.iterations = Math.trunc(state.iterations)
  }
  if (state.host.trim()) {
    base.host = state.host.trim()
  }

  const cleanEnv: Record<string, string> = {}
  for (const [k, v] of Object.entries(state.env || {})) {
    const key = k.trim()
    if (key) cleanEnv[key] = v
  }
  if (Object.keys(cleanEnv).length) {
    base.env = cleanEnv
  }

  const existingThresholds = isPlainObject(base.thresholds) ? { ...base.thresholds } : {}
  delete existingThresholds.max_p95_ms
  delete existingThresholds.max_error_rate
  if (state.max_p95_ms != null && state.max_p95_ms >= 0) {
    existingThresholds.max_p95_ms = state.max_p95_ms
  }
  if (state.max_error_rate != null && state.max_error_rate >= 0) {
    existingThresholds.max_error_rate = state.max_error_rate
  }
  if (Object.keys(existingThresholds).length) {
    base.thresholds = existingThresholds
  } else {
    delete base.thresholds
  }

  return JSON.stringify(base, null, 2)
}
