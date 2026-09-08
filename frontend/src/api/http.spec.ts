import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/auth'
import http, { blocksPrototypeWrite, getBackendOrigin, prototypeWriteBlockedCode } from './http'
import router from '@/router'

vi.mock('@/router', () => ({
  default: {
    push: vi.fn(),
  },
}))

describe('http client', () => {
  const originalBaseURL = http.defaults.baseURL
  const originalAdapter = http.defaults.adapter

  beforeEach(() => {
    vi.unstubAllEnvs()
    setActivePinia(createPinia())
    http.defaults.baseURL = originalBaseURL
    http.defaults.adapter = originalAdapter
  })

  it('blocks business writes while prototype data mode is enabled', async () => {
    vi.stubEnv('VITE_ENABLE_PROTOTYPE_DATA', 'true')
    const adapter = vi.fn()
    http.defaults.adapter = adapter as AxiosAdapter

    expect(blocksPrototypeWrite('delete', '/devices/1')).toBe(true)
    await expect(http.delete('/devices/1')).rejects.toEqual({ code: prototypeWriteBlockedCode })
    expect(adapter).not.toHaveBeenCalled()
  })

  it('keeps session login available in prototype data mode', async () => {
    vi.stubEnv('VITE_ENABLE_PROTOTYPE_DATA', 'true')
    const adapter = vi.fn(async (config: InternalAxiosRequestConfig) => ({
      config,
      data: { authenticated: true },
      headers: {},
      status: 200,
      statusText: 'OK',
    }))
    http.defaults.adapter = adapter as AxiosAdapter

    await http.post('/auth/login', { username: 'demo', password: 'secret' })
    expect(adapter).toHaveBeenCalledOnce()
  })

  it('injects the bearer token into outgoing requests', async () => {
    const auth = useAuthStore()
    auth.token = 'access-token'
    const capturedConfigs: InternalAxiosRequestConfig[] = []

    http.defaults.adapter = (async (config) => {
      capturedConfigs.push(config)
      return {
        config,
        data: { ok: true },
        headers: {},
        status: 200,
        statusText: 'OK',
      }
    }) as AxiosAdapter

    await http.get('/ping')

    expect(capturedConfigs[0]?.headers.Authorization).toBe('Bearer access-token')
  })

  it('logs out and redirects to login on 401 responses', async () => {
    const auth = useAuthStore()
    auth.token = 'expired-token'
    auth.refreshToken = 'expired-refresh'

    http.defaults.adapter = (async () => Promise.reject({
      response: {
        status: 401,
        data: { detail: 'token expired' },
      },
    })) as AxiosAdapter

    await expect(http.get('/me')).rejects.toBe('token expired')

    expect(auth.token).toBeNull()
    expect(auth.refreshToken).toBeNull()
    expect(router.push).toHaveBeenCalledWith({ name: 'login' })
  })

  it('derives backend origin from absolute or relative base URLs', () => {
    const originalOrigin = import.meta.env.VITE_BACKEND_ORIGIN
    delete (import.meta.env as Record<string, unknown>).VITE_BACKEND_ORIGIN
    try {
      http.defaults.baseURL = 'https://api.example.com/api/v1'
      expect(getBackendOrigin()).toBe('https://api.example.com')

      http.defaults.baseURL = '/api/v1'
      expect(getBackendOrigin()).toBe('http://localhost:8000')
    } finally {
      if (originalOrigin !== undefined) {
        ;(import.meta.env as Record<string, unknown>).VITE_BACKEND_ORIGIN = originalOrigin
      }
    }
  })
})
