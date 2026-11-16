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
    // 不使用 Promise.withResolvers：它需要较新的浏览器（2024 年起才普遍支持），普通 Promise 没有兼容性限制。
    await new Promise<void>((resolve) => {
      setTimeout(resolve, PACKAGE_POLL_INTERVAL_MS)
    })
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
