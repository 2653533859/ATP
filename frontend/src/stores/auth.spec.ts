import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { authApi } from '@/api'

import { useAuthStore } from './auth'

vi.mock('@/api', () => ({
  authApi: {
    login: vi.fn(),
    me: vi.fn(),
  },
}))

const mockedAuthApi = vi.mocked(authApi)

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes tokens from localStorage', () => {
    localStorage.setItem('access_token', 'stored-access')
    localStorage.setItem('refresh_token', 'stored-refresh')

    const store = useAuthStore()

    expect(store.token).toBe('stored-access')
    expect(store.refreshToken).toBe('stored-refresh')
  })

  it('stores tokens and fetches the current user after login', async () => {
    mockedAuthApi.login.mockResolvedValue({
      access_token: 'new-access',
      refresh_token: 'new-refresh',
    })
    mockedAuthApi.me.mockResolvedValue({
      id: 7,
      username: 'alice',
      email: 'alice@example.com',
      role: 'engineer',
    })

    const store = useAuthStore()
    await store.login('alice', 'secret')

    expect(mockedAuthApi.login).toHaveBeenCalledWith('alice', 'secret')
    expect(mockedAuthApi.me).toHaveBeenCalledOnce()
    expect(store.token).toBe('new-access')
    expect(store.refreshToken).toBe('new-refresh')
    expect(store.user).toEqual({
      id: 7,
      username: 'alice',
      email: 'alice@example.com',
      role: 'engineer',
    })
    expect(localStorage.getItem('access_token')).toBe('new-access')
    expect(localStorage.getItem('refresh_token')).toBe('new-refresh')
  })

  it('logs out when fetching the current user fails', async () => {
    localStorage.setItem('access_token', 'expired-access')
    localStorage.setItem('refresh_token', 'expired-refresh')
    mockedAuthApi.me.mockRejectedValue(new Error('unauthorized'))

    const store = useAuthStore()
    await store.fetchMe()

    expect(store.token).toBeNull()
    expect(store.refreshToken).toBeNull()
    expect(store.user).toBeNull()
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })
})
