import type { AndroidUiTargetDiagnostic } from '@/api'

export type AndroidLocatorWarning = 'request_failed' | 'unavailable'

/**
 * Only unavailable locator collection needs a warning. A missing match is a
 * normal coordinate-fallback case and should not interrupt recording.
 */
export function androidLocatorWarning(diagnostic?: AndroidUiTargetDiagnostic): AndroidLocatorWarning | null {
  if (diagnostic?.status !== 'unavailable') return null
  return diagnostic.code === 'request_failed' ? 'request_failed' : 'unavailable'
}
