import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useAuthStore } from '@/stores/auth'

import http, { getBackendOrigin } from './http'
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
    setActivePinia(createPinia())
    http.defaults.baseURL = originalBaseURL
    http.defaults.adapter = originalAdapter
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
    localStorage.setItem('access_token', 'expired-token')
    localStorage.setItem('refresh_token', 'expired-refresh')

    http.defaults.adapter = (async () => Promise.reject({
      response: {
        status: 401,
        data: { detail: 'token expired' },
      },
    })) as AxiosAdapter

    await expect(http.get('/me')).rejects.toBe('token expired')

    expect(auth.token).toBeNull()
    expect(auth.refreshToken).toBeNull()
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(router.push).toHaveBeenCalledWith({ name: 'login' })
  })

  it('derives backend origin from absolute or relative base URLs', () => {
    http.defaults.baseURL = 'https://api.example.com/api/v1'
    expect(getBackendOrigin()).toBe('https://api.example.com')

    http.defaults.baseURL = '/api/v1'
    expect(getBackendOrigin()).toBe('http://localhost:8000')
  })
})
