import { describe, expect, it } from 'vitest'

import { createBackendProxy, DEFAULT_BACKEND_ORIGIN, resolveBackendOrigin } from './backendProxy'

describe('backend dev proxy', () => {
  it('uses the configured Linux origin for HTTP and WebSocket traffic', () => {
    const origin = resolveBackendOrigin({ VITE_BACKEND_ORIGIN: ' http://192.168.3.196:8000/// ' })
    const proxy = createBackendProxy(origin)

    expect(proxy['/api'].target).toBe('http://192.168.3.196:8000')
    expect(proxy['/ws'].target).toBe('ws://192.168.3.196:8000')
    expect(proxy['/ws'].ws).toBe(true)
  })

  it('falls back to the loopback backend when no origin is configured', () => {
    expect(resolveBackendOrigin({})).toBe(DEFAULT_BACKEND_ORIGIN)
  })
})
