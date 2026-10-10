export function normalizeRecordingUrl(value: string): string {
  const input = value.trim()
  const hasScheme = /^[a-z][a-z\d+.-]*:\/\//i.test(input)
  const localHost = /^(localhost|127\.0\.0\.1|\[::1\])(?=[:/]|$)/i.test(input)
  const url = new URL(hasScheme ? input : `${localHost ? 'http' : 'https'}://${input}`)
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || !url.hostname) {
    throw new Error('Invalid recording URL')
  }
  return url.href
}

export function recordingErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === 'string') return error.trim() || fallback
  if (error instanceof Error) return error.message || fallback
  if (Array.isArray(error)) {
    return error.map(item => recordingErrorMessage(item, '')).filter(Boolean).join('；') || fallback
  }
  if (error && typeof error === 'object') {
    const detail = error as Record<string, unknown>
    for (const key of ['detail', 'msg', 'message']) {
      if (detail[key] !== undefined) return recordingErrorMessage(detail[key], fallback)
    }
  }
  return fallback
}
