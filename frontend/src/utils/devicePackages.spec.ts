import { beforeEach, describe, expect, it, vi } from 'vitest'

import { loadDevicePackagesAsync } from './devicePackages'

const { packages, refreshPackages } = vi.hoisted(() => ({
  packages: vi.fn(),
  refreshPackages: vi.fn(),
}))

vi.mock('@/api', () => ({ deviceApi: { packages, refreshPackages } }))

function snapshot(overrides: Record<string, unknown> = {}) {
  return {
    device_id: 5,
    serial: '172.16.101.11:5555',
    current_package: 'com.hopesen.aiphytraining',
    current_activity: '.MainActivity',
    packages: ['com.hopesen.aiphytraining'],
    read_at: '2026-11-12T09:30:00Z',
    stale: false,
    source: 'refresh',
    ...overrides,
  }
}

describe('loadDevicePackagesAsync', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  it('快照新鲜时直接返回缓存，不触发后台读取', async () => {
    packages.mockResolvedValue(snapshot())

    const result = await loadDevicePackagesAsync(5)

    expect(result.current_package).toBe('com.hopesen.aiphytraining')
    expect(refreshPackages).not.toHaveBeenCalled()
  })

  it('快照缺失或过期时触发刷新并轮询到新的读取结果', async () => {
    vi.useFakeTimers()
    packages
      .mockResolvedValueOnce(snapshot({ packages: [], read_at: null, stale: true }))
      .mockResolvedValueOnce(snapshot({ read_at: '2026-11-12T09:40:00Z' }))
    refreshPackages.mockResolvedValue({ status: 'queued', device_id: 5, serial: 'x' })

    const pending = loadDevicePackagesAsync(5, { force: true })
    await vi.advanceTimersByTimeAsync(900)
    const result = await pending

    expect(refreshPackages).toHaveBeenCalledWith(5)
    expect(result.read_at).toBe('2026-11-12T09:40:00Z')
    vi.useRealTimers()
  })

  it('刷新请求失败时回退到已有快照', async () => {
    packages.mockResolvedValue(snapshot({ stale: true }))
    refreshPackages.mockRejectedValue(new Error('device offline'))

    const result = await loadDevicePackagesAsync(5)

    expect(result.stale).toBe(true)
    expect(result.packages).toEqual(['com.hopesen.aiphytraining'])
  })

  it('轮询期间接口报错不会中断后续尝试', async () => {
    vi.useFakeTimers()
    packages
      .mockResolvedValueOnce(snapshot({ packages: [], read_at: null, stale: true }))
      .mockRejectedValueOnce(new Error('temporary'))
      .mockResolvedValueOnce(snapshot({ read_at: '2026-11-12T09:45:00Z' }))
    refreshPackages.mockResolvedValue({ status: 'queued', device_id: 5, serial: 'x' })

    const pending = loadDevicePackagesAsync(5, { force: true })
    await vi.advanceTimersByTimeAsync(900)
    await vi.advanceTimersByTimeAsync(900)
    const result = await pending

    expect(result.read_at).toBe('2026-11-12T09:45:00Z')
    vi.useRealTimers()
  })
})
