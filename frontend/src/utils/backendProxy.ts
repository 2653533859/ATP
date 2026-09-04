export const DEFAULT_BACKEND_ORIGIN = 'http://127.0.0.1:8000'

export function resolveBackendOrigin(env: { VITE_BACKEND_ORIGIN?: string }) {
  return (env.VITE_BACKEND_ORIGIN?.trim() || DEFAULT_BACKEND_ORIGIN).replace(/\/+$/, '')
}

export function createBackendProxy(backendOrigin: string) {
  const normalizedOrigin = backendOrigin.replace(/\/+$/, '')
  const websocketOrigin = normalizedOrigin.replace(/^http/, 'ws')

  return {
    '/api': {
      target: normalizedOrigin,
      changeOrigin: true,
    },
    '/ws': {
      target: websocketOrigin,
      changeOrigin: true,
      ws: true,
    },
  }
}
