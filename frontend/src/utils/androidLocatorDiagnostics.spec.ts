import { describe, expect, it } from 'vitest'

import { androidLocatorWarning } from './androidLocatorDiagnostics'

describe('androidLocatorWarning', () => {
  it('does not warn when a target is found or simply not matched', () => {
    expect(androidLocatorWarning({ status: 'found', code: null })).toBeNull()
    expect(androidLocatorWarning({ status: 'not_found', code: 'target_not_found' })).toBeNull()
    expect(androidLocatorWarning()).toBeNull()
  })

  it('distinguishes an API request failure from a device-side unavailable hierarchy', () => {
    expect(androidLocatorWarning({ status: 'unavailable', code: 'request_failed' })).toBe('request_failed')
    expect(androidLocatorWarning({ status: 'unavailable', code: 'uiautomator_dump_failed' })).toBe('unavailable')
  })
})
