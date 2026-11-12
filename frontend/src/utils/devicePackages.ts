import { deviceApi, type DevicePackagesResult } from '@/api'

export const PACKAGE_POLL_INTERVAL_MS = 800
export const PACKAGE_POLL_MAX_ATTEMPTS = 20

/**
 * 读取设备包名：优先用快照缓存；没有快照或快照过期时触发后台任务并轮询。
 * 读取动作全部在服务端异步执行，页面只等快照出现。
 */
export async function loadDevicePackagesAsync(
  deviceId: number,
  options: { force?: boolean } = {},
): Promise<DevicePackagesResult> {
  let snapshot = await deviceApi.packages(deviceId)
  if (!options.force && !snapshot.stale && snapshot.packages.length) {
    return snapshot
  }

  try {
    await deviceApi.refreshPackages(deviceId)
  } catch {
    return snapshot
  }

  const previousReadAt = snapshot.read_at
  for (let attempt = 0; attempt < PACKAGE_POLL_MAX_ATTEMPTS; attempt += 1) {
    const { promise, resolve } = Promise.withResolvers<void>()
    setTimeout(resolve, PACKAGE_POLL_INTERVAL_MS)
    await promise
    try {
      snapshot = await deviceApi.packages(deviceId)
    } catch {
      continue
    }
    if (snapshot.read_at && snapshot.read_at !== previousReadAt) {
      return snapshot
    }
    if (!snapshot.stale && snapshot.packages.length) {
      return snapshot
    }
  }
  return snapshot
}
