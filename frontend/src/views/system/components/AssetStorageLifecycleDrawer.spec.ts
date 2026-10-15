import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AssetStorageLifecycleDrawer from './AssetStorageLifecycleDrawer.vue'

const mockScanLifecycle = vi.fn().mockResolvedValue({
  dry_run: true,
  scanned_at: '2026-10-16T12:00:00Z',
  total_scanned_count: 50,
  total_expired_count: 15,
  total_reclaimable_bytes: 104857600, // 100 MB
  total_reclaimable_mb: 100.0,
  total_reclaimable_gb: 0.098,
  deleted_count: 0,
  deletion_errors_count: 0,
  db_cleanup_summary: {},
  categories: [
    {
      category: 'videos',
      prefix: 'videos/',
      retention_days: 7,
      scanned_count: 10,
      expired_count: 4,
      reclaimable_bytes: 52428800,
      reclaimable_mb: 50.0,
      sample_expired_files: ['videos/run_1.mp4', 'videos/run_2.mp4'],
    },
    {
      category: 'screenshots',
      prefix: 'screenshots/',
      retention_days: 14,
      scanned_count: 40,
      expired_count: 11,
      reclaimable_bytes: 52428800,
      reclaimable_mb: 50.0,
      sample_expired_files: ['screenshots/step_1.png'],
    },
  ],
})

const mockExecuteLifecycle = vi.fn().mockResolvedValue({
  dry_run: false,
  scanned_at: '2026-10-16T12:00:00Z',
  total_scanned_count: 50,
  total_expired_count: 15,
  total_reclaimable_bytes: 104857600,
  total_reclaimable_mb: 100.0,
  total_reclaimable_gb: 0.098,
  deleted_count: 15,
  deletion_errors_count: 0,
  db_cleanup_summary: {
    step_results_cleared: 8,
    mobile_incidents_cleared: 3,
    mobile_artifacts_cleared: 4,
  },
  categories: [],
})

vi.mock('@/api', () => ({
  storageApi: {
    scanLifecycle: (data: unknown) => mockScanLifecycle(data),
    executeLifecycleCleanup: (data: unknown) => mockExecuteLifecycle(data),
  },
}))

describe('AssetStorageLifecycleDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('runs dry-run scan on mount and renders reclaimable space', async () => {
    const wrapper = mount(AssetStorageLifecycleDrawer, {
      props: { visible: true },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-input-number': true,
        },
      },
    })

    await flushPromises()

    expect(mockScanLifecycle).toHaveBeenCalled()
    expect(wrapper.text()).toContain('分级资产保留策略与待清理明细')
    expect(wrapper.text()).toContain('100.0')
    expect(wrapper.text()).toContain('MB 待释放')
    expect(wrapper.text()).toContain('15 个过期对象可安全清理')

    const vm = wrapper.vm as unknown as {
      scanReport: { total_reclaimable_mb: number } | null
    }

    expect(vm.scanReport?.total_reclaimable_mb).toBe(100.0)
  })

  it('executes cleanup and renders deletion summary', async () => {
    const wrapper = mount(AssetStorageLifecycleDrawer, {
      props: { visible: true },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-input-number': true,
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      runScan: (dryRun?: boolean) => Promise<void>
      cleanupResult: { deleted_count: number } | null
    }

    await vm.runScan(false)
    await flushPromises()

    expect(mockExecuteLifecycle).toHaveBeenCalled()
    expect(vm.cleanupResult?.deleted_count).toBe(15)
    expect(wrapper.text()).toContain('已物理删除 15 个对象')
    expect(wrapper.text()).toContain('用例截图: 8 处')
  })
})
