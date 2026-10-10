export interface RuntimeMode {
  mode: 'local' | 'server'
  database: 'sqlite' | 'postgresql'
  storage: 'filesystem' | 'minio'
  execution: 'local' | 'celery'
  features?: string[]
}

let runtimeMode: RuntimeMode | null = null

export function getRuntimeMode(): RuntimeMode | null {
  return runtimeMode
}

export async function verifyRuntimeMode(): Promise<void> {
  const expectsLocal = import.meta.env.VITE_ATP_LOCAL_MODE === 'true'
  const response = await fetch('/api/v1/runtime', { credentials: 'include', cache: 'no-store' })
  if (response.status === 404 && !expectsLocal) {
    // Deployed server releases predating the runtime endpoint remain usable.
    const legacyAuth = await fetch('/api/v1/auth/me', { credentials: 'include', cache: 'no-store' })
    if (![200, 401].includes(legacyAuth.status)) {
      throw new Error('无法确认旧版服务器 API，请检查服务器页面地址。')
    }
    runtimeMode = { mode: 'server', database: 'postgresql', storage: 'minio', execution: 'celery' }
    return
  }
  if (!response.ok) throw new Error('无法读取后端运行模式，请检查服务连接。')
  const info = await response.json() as RuntimeMode
  if (info.mode !== (expectsLocal ? 'local' : 'server') ||
      info.database !== (expectsLocal ? 'sqlite' : 'postgresql') ||
      info.storage !== (expectsLocal ? 'filesystem' : 'minio')) {
    throw new Error('页面和后端运行模式不一致，请打开正确的本地或服务器入口。')
  }
  runtimeMode = info
  if (expectsLocal) {
    const capabilitiesResponse = await fetch('/api/v1/runtime/capabilities', { credentials: 'include', cache: 'no-store' })
    if (!capabilitiesResponse.ok) throw new Error('无法读取本地功能清单，请更新并重启服务。')
    const capabilities = await capabilitiesResponse.json() as { features: string[] }
    runtimeMode.features = capabilities.features
  }
}

export function supportsFeature(feature: string): boolean {
  return runtimeMode?.mode !== 'local' || Boolean(runtimeMode.features?.includes(feature))
}
