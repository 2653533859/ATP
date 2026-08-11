import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  withCredentials: true,
})

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
