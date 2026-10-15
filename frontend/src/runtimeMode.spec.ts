import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getRuntimeMode, supportsFeature, verifyRuntimeMode } from './runtimeMode'

describe('runtimeMode verification and feature gating', () => {
  const originalFetch = globalThis.fetch

  beforeEach(() => {
    vi.unstubAllEnvs()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('verifies local mode successfully and registers features', async () => {
    vi.stubEnv('VITE_ATP_LOCAL_MODE', 'true')
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/runtime') {
        return Promise.resolve(new Response(JSON.stringify({
          mode: 'local',
          database: 'sqlite',
          storage: 'filesystem',
          execution: 'local',
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      if (url === '/api/v1/runtime/capabilities') {
        return Promise.resolve(new Response(JSON.stringify({
          features: ['api', 'web', 'android'],
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.reject(new Error(`Unexpected fetch URL: ${url}`))
    })

    await verifyRuntimeMode()

    const mode = getRuntimeMode()
    expect(mode).not.toBeNull()
    expect(mode?.mode).toBe('local')
    expect(mode?.database).toBe('sqlite')
    expect(mode?.features).toEqual(['api', 'web', 'android'])
    expect(supportsFeature('api')).toBe(true)
    expect(supportsFeature('schedules')).toBe(false)
  })

  it('rejects when frontend expects local mode but backend is server mode', async () => {
    vi.stubEnv('VITE_ATP_LOCAL_MODE', 'true')
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/runtime') {
        return Promise.resolve(new Response(JSON.stringify({
          mode: 'server',
          database: 'postgresql',
          storage: 'minio',
          execution: 'celery',
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.reject(new Error(`Unexpected fetch URL: ${url}`))
    })

    await expect(verifyRuntimeMode()).rejects.toThrow('页面和后端运行模式不一致，请打开正确的本地或服务器入口。')
  })

  it('verifies server mode successfully and allows all features by default', async () => {
    vi.stubEnv('VITE_ATP_LOCAL_MODE', 'false')
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/runtime') {
        return Promise.resolve(new Response(JSON.stringify({
          mode: 'server',
          database: 'postgresql',
          storage: 'minio',
          execution: 'celery',
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.reject(new Error(`Unexpected fetch URL: ${url}`))
    })

    await verifyRuntimeMode()

    const mode = getRuntimeMode()
    expect(mode).not.toBeNull()
    expect(mode?.mode).toBe('server')
    expect(mode?.database).toBe('postgresql')
    expect(supportsFeature('schedules')).toBe(true)
    expect(supportsFeature('nodes')).toBe(true)
  })

  it('rejects when frontend expects server mode but backend is local mode', async () => {
    vi.stubEnv('VITE_ATP_LOCAL_MODE', 'false')
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/runtime') {
        return Promise.resolve(new Response(JSON.stringify({
          mode: 'local',
          database: 'sqlite',
          storage: 'filesystem',
          execution: 'local',
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      }
      return Promise.reject(new Error(`Unexpected fetch URL: ${url}`))
    })

    await expect(verifyRuntimeMode()).rejects.toThrow('页面和后端运行模式不一致，请打开正确的本地或服务器入口。')
  })

  it('supports legacy server fallbacks when runtime endpoint is 404', async () => {
    vi.stubEnv('VITE_ATP_LOCAL_MODE', 'false')
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url === '/api/v1/runtime') {
        return Promise.resolve(new Response(null, { status: 404 }))
      }
      if (url === '/api/v1/auth/me') {
        return Promise.resolve(new Response(null, { status: 401 }))
      }
      return Promise.reject(new Error(`Unexpected fetch URL: ${url}`))
    })

    await verifyRuntimeMode()

    const mode = getRuntimeMode()
    expect(mode?.mode).toBe('server')
    expect(mode?.database).toBe('postgresql')
  })
})
