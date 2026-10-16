import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import EphemeralTestEnvDashboardView from './EphemeralTestEnvDashboardView.vue'
import { ephemeralTestEnvApi } from '@/api/cloudNativeCluster'

const mockEnv = {
  env_id: 'eph_pr_1024_abc123',
  env_name: '沙箱测试环境 [pr-1024-checkout]',
  namespace: 'atp-eph-pr-1024-checkout-abc123',
  branch_or_pr: 'pr-1024-checkout',
  creator: 'tester',
  services: ['order-service', 'pay-service'],
  cpu_limit_cores: 2.0,
  memory_limit_gib: 4.0,
  status: 'READY' as const,
  ttl_seconds: 3600,
  remaining_ttl_seconds: 3500,
  is_expired: false,
  created_at: '2026-10-17T12:00:00Z',
  expires_at: '2026-10-17T13:00:00Z',
}

vi.mock('@/api/cloudNativeCluster', () => ({
  ephemeralTestEnvApi: {
    listEnvs: vi.fn(),
    provision: vi.fn(),
    extendLease: vi.fn(),
    teardown: vi.fn(),
    reclaimExpired: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  ClusterOutlined: { template: '<span>Cluster</span>' },
  PlusOutlined: { template: '<span>Plus</span>' },
  ClearOutlined: { template: '<span>Clear</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  ApartmentOutlined: { template: '<span>Apartment</span>' },
}))

describe('EphemeralTestEnvDashboardView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ephemeralTestEnvApi.listEnvs).mockResolvedValue({
      total: 1,
      environments: [mockEnv as any],
    })
    vi.mocked(ephemeralTestEnvApi.provision).mockResolvedValue({
      message: '沙箱测试环境已成功拉起',
      env: mockEnv as any,
    })
    vi.mocked(ephemeralTestEnvApi.extendLease).mockResolvedValue({
      message: '租约已成功延长',
      env: mockEnv as any,
    })
    vi.mocked(ephemeralTestEnvApi.teardown).mockResolvedValue({
      success: true,
      message: '沙箱环境已安全优雅销毁',
    })
    vi.mocked(ephemeralTestEnvApi.reclaimExpired).mockResolvedValue({
      message: '已完成超期孤儿测试环境清理',
      result: { reclaimed_count: 0 },
    })
  })

  it('renders header, KPI summary, and environment table', async () => {
    const wrapper = mount(EphemeralTestEnvDashboardView, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
        },
      },
    })

    await flushPromises()

    expect(ephemeralTestEnvApi.listEnvs).toHaveBeenCalled()
    expect(wrapper.text()).toContain('临时沙箱测试环境生命周期拓扑与原子回收全景大盘')
    expect(wrapper.text()).toContain('1 个')
    expect(wrapper.text()).toContain('2 Cores')
    expect(wrapper.text()).toContain('4 GiB')

    // 测试生命周期操作
    const vm = wrapper.vm as any
    await vm.handleExtendLease('eph_pr_1024_abc123')
    expect(ephemeralTestEnvApi.extendLease).toHaveBeenCalledWith('eph_pr_1024_abc123', { extra_seconds: 1800 })

    await vm.handleTeardown('eph_pr_1024_abc123')
    expect(ephemeralTestEnvApi.teardown).toHaveBeenCalledWith('eph_pr_1024_abc123')

    await vm.handleReclaimExpired()
    expect(ephemeralTestEnvApi.reclaimExpired).toHaveBeenCalled()
  })
})
