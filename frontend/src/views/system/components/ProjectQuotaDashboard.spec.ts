import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ProjectQuotaDashboard from './ProjectQuotaDashboard.vue'

const mockGetQuota = vi.fn().mockResolvedValue({
  id: 1,
  project_id: 10,
  max_concurrent_runs: 5,
  daily_duration_limit_seconds: 28800,
  max_single_run_timeout_seconds: 3600,
  over_quota_policy: 'reject',
  is_enabled: true,
  description: '核心测试配额',
})

const mockEvaluateQuota = vi.fn().mockResolvedValue({
  allowed: true,
  should_queue: false,
  reason: 'within_quota',
  current_active_runs: 2,
  max_concurrent_runs: 5,
  daily_duration_seconds: 7200,
  daily_duration_limit_seconds: 28800,
  policy: 'reject',
  details: { message: '当前活跃任务未超限' },
})

const mockUpdateQuota = vi.fn().mockResolvedValue({
  id: 1,
  project_id: 10,
  max_concurrent_runs: 8,
  daily_duration_limit_seconds: 14400,
  max_single_run_timeout_seconds: 1800,
  over_quota_policy: 'queue',
  is_enabled: true,
})

const mockReapTimeouts = vi.fn().mockResolvedValue({
  project_id: 10,
  reaped_count: 2,
  reaped_runs: [
    {
      run_type: 'suite_run',
      run_id: 99,
      project_id: 10,
      timeout_limit_seconds: 3600,
      reason: 'execution_hard_timeout_exceeded',
    },
  ],
})

vi.mock('@/api', () => ({
  projectApi: {
    getQuota: (pid: number) => mockGetQuota(pid),
    evaluateQuota: (pid: number) => mockEvaluateQuota(pid),
    updateQuota: (pid: number, data: unknown) => mockUpdateQuota(pid, data),
    reapTimeouts: (pid: number) => mockReapTimeouts(pid),
  },
}))

describe('ProjectQuotaDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads quota and evaluation data on mount and renders watermarks', async () => {
    const wrapper = mount(ProjectQuotaDashboard, {
      props: { projectId: 10 },
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-progress': true,
          'a-spin': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-input-number': true,
          'a-radio-group': true,
          'a-radio-button': true,
          'a-switch': true,
          'a-input': true,
        },
      },
    })

    await flushPromises()

    expect(mockGetQuota).toHaveBeenCalledWith(10)
    expect(mockEvaluateQuota).toHaveBeenCalledWith(10)
    expect(wrapper.text()).toContain('项目资源配额与并发硬限制仪表板')
    expect(wrapper.text()).toContain('2 / 5 任务')
    expect(wrapper.text()).toContain('立即准入')

    const vm = wrapper.vm as unknown as {
      quotaForm: { max_concurrent_runs: number }
      saveQuota: () => Promise<void>
    }

    expect(vm.quotaForm.max_concurrent_runs).toBe(5)

    // Save quota
    vm.quotaForm.max_concurrent_runs = 8
    await vm.saveQuota()
    expect(mockUpdateQuota).toHaveBeenCalledWith(10, expect.objectContaining({ max_concurrent_runs: 8 }))
  })

  it('triggers zombie run reap on button click', async () => {
    const wrapper = mount(ProjectQuotaDashboard, {
      props: { projectId: 10 },
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-progress': true,
          'a-spin': { template: '<div><slot /></div>' },
          'a-form': true,
          'a-form-item': true,
          'a-row': true,
          'a-col': true,
          'a-input-number': true,
          'a-radio-group': true,
          'a-radio-button': true,
          'a-switch': true,
          'a-input': true,
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      runReapTimeouts: () => Promise<void>
      reapSummary: { reaped_count: number } | null
    }

    await vm.runReapTimeouts()

    expect(mockReapTimeouts).toHaveBeenCalledWith(10)
    expect(vm.reapSummary?.reaped_count).toBe(2)
    expect(wrapper.text()).toContain('共收割并释放 2 个超时僵尸任务')
  })
})
