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

  it('does not persist JWTs in localStorage', () => {
    const store = useAuthStore()

    expect(store.token).toBeNull()
    expect(store.refreshToken).toBeNull()
  })

  it('fetches the current user after cookie login', async () => {
    mockedAuthApi.login.mockResolvedValue({ authenticated: true })
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
    expect(store.token).toBeNull()
    expect(store.refreshToken).toBeNull()
    expect(store.user).toEqual({
      id: 7,
      username: 'alice',
      email: 'alice@example.com',
      role: 'engineer',
    })
  })

  it('logs out when fetching the current user fails', async () => {
    mockedAuthApi.me.mockRejectedValue(new Error('unauthorized'))

    const store = useAuthStore()
    await store.fetchMe()

    expect(store.token).toBeNull()
    expect(store.refreshToken).toBeNull()
    expect(store.user).toBeNull()
    expect(store.initialized).toBe(true)
  })
})
