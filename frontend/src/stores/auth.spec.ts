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
    vi.unstubAllEnvs()
    setActivePinia(createPinia())
  })

  it('does not hold or persist JWTs on the client', () => {
    const store = useAuthStore()

    expect('token' in store).toBe(false)
    expect('refreshToken' in store).toBe(false)
    expect(localStorage.length).toBe(0)
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

    expect(store.user).toBeNull()
    expect(store.initialized).toBe(true)
  })

  it('does not synthesize an admin when the development backend session check fails', async () => {
    vi.stubEnv('MODE', 'development')
    mockedAuthApi.me.mockRejectedValue(new Error('backend unavailable'))

    const store = useAuthStore()
    expect(await store.fetchMe()).toBe(false)
    expect(store.user).toBeNull()
  })
})
