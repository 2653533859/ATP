import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  // JWT 仅保存在 HttpOnly Cookie；token 仅保留给需要显式注入 Bearer 的外部场景。
  const token = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  const user = ref<{ id: number; username: string; email: string; role: string; is_active?: boolean } | null>(null)
  const initialized = ref(false)

  async function login(username: string, password: string) {
    await authApi.login(username, password)
    if (!(await fetchMe())) {
      throw new Error('登录会话建立失败')
    }
  }

  async function fetchMe(): Promise<boolean> {
    try {
      user.value = await authApi.me()
      initialized.value = true
      return true
    } catch {
      clearSession()
      return false
    }
  }

  async function restoreSession() {
    if (!initialized.value) await fetchMe()
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch {
      // 服务端不可用时仍清理本地会话状态。
    }
    clearSession()
  }

  function clearSession() {
    token.value = null
    refreshToken.value = null
    user.value = null
    initialized.value = true
  }

  return { token, refreshToken, user, initialized, login, logout, clearSession, fetchMe, restoreSession }
})
