import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
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

// 请求拦截：自动携带 Token
http.interceptors.request.use((config) => {
  const auth = useAuthStore()
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
      auth.logout()
      await router.push({ name: 'login' })
    }
    return Promise.reject(error.response?.data?.detail ?? error.message)
  },
)

export default http
