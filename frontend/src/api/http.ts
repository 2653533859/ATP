import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  withCredentials: true,
})

const prototypeWriteAllowedPaths = new Set(['/auth/login', '/auth/logout'])
export const prototypeWriteBlockedCode = 'prototype_write_blocked'

export function blocksPrototypeWrite(method?: string, url?: string) {
  if (import.meta.env.VITE_ENABLE_PROTOTYPE_DATA !== 'true') return false
  const normalizedMethod = (method || 'get').toLowerCase()
  if (['get', 'head', 'options'].includes(normalizedMethod)) return false
  const normalizedUrl = (url || '').split(/[?#]/, 1)[0]?.replace(/^\/api\/v1/, '') || ''
  return !prototypeWriteAllowedPaths.has(normalizedUrl)
}

export function getBackendOrigin() {
  const configuredOrigin = import.meta.env.VITE_BACKEND_ORIGIN?.trim()
  if (configuredOrigin) {
    return configuredOrigin.replace(/\/+$/, '')
  }

  const baseURL = http.defaults.baseURL ?? ''
  if (/^https?:\/\//.test(baseURL)) {
    return new URL(baseURL).origin
  }

  return import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin
}

// 浏览器使用 HttpOnly Cookie；Bearer 仅保留给显式注入的外部客户端场景。
http.interceptors.request.use((config) => {
  if (blocksPrototypeWrite(config.method, config.url)) {
    return Promise.reject({ code: prototypeWriteBlockedCode })
  }
  const auth = useAuthStore()
  config.headers['X-Requested-With'] = 'XMLHttpRequest'
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// 响应拦截：401 跳转登录
http.interceptors.response.use(
  (res) => res.data,
  async (error) => {
    if (error?.code === prototypeWriteBlockedCode) {
      return Promise.reject(error)
    }
    if (error.response?.status === 401) {
      const auth = useAuthStore()
      auth.clearSession()
      if (!error.config?.url?.endsWith('/auth/me')) {
        await router.push({ name: 'login' })
      }
    }
    return Promise.reject(error.response?.data?.detail ?? error.message)
  },
)

export default http
