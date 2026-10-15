import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import BaselineDriftMonitor from './BaselineDriftMonitor.vue'

const mockGetDriftAlert = vi.fn().mockResolvedValue({
  is_drifted: false,
  should_alert: false,
  severity: 'none',
  alert_reasons: [],
  deltas: {
    rps_delta_pct: 3.5,
    p95_delta_pct: -4.2,
    error_rate_delta_pct: 0.0,
  },
  baseline_summary: { rps: 1000.0, p95_ms: 50.0, error_rate: 0.001 },
  current_summary: { rps: 1035.0, p95_ms: 47.9, error_rate: 0.001 },
})

const mockAlignBaseline = vi.fn().mockResolvedValue({
  eligible: true,
  is_first_baseline: false,
  reasons: ['吞吐量提升 3.5% 且延迟优化，晋升为新基准'],
  promoted: true,
  new_baseline_run_id: 101,
  candidate_run_id: 101,
})

vi.mock('@/api', () => ({
  performanceApi: {
    getDriftAlert: (runId: number) => mockGetDriftAlert(runId),
    alignBaseline: (testId: number, autoPromote: boolean) => mockAlignBaseline(testId, autoPromote),
  },
}))

describe('BaselineDriftMonitor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders initial sample drift data on mount', async () => {
    const wrapper = mount(BaselineDriftMonitor, {
      props: { testId: 5, runId: 88 },
      global: {
        stubs: {
          'a-input-number': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-card': { template: '<div><slot /></div>' },
        },
      },
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('性能基准 Baseline 漂移监控与智能晋升')
    expect(wrapper.text()).toContain('吞吐量 (RPS) 较基线严重下跌')
    expect(wrapper.text()).toContain('P95 响应延迟较基线恶化')

    const vm = wrapper.vm as unknown as {
      driftData: { severity: string; deltas: { rps_delta_pct: number } } | null
    }

    expect(vm.driftData?.severity).toBe('critical')
    expect(vm.driftData?.deltas.rps_delta_pct).toBe(-24.5)
  })

  it('triggers live drift alert check on button click', async () => {
    const wrapper = mount(BaselineDriftMonitor, {
      props: { testId: 5, runId: 88 },
      global: {
        stubs: {
          'a-input-number': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-card': { template: '<div><slot /></div>' },
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      fetchDriftAlert: () => Promise<void>
      currentRunId: number
      driftData: { severity: string } | null
    }

    vm.currentRunId = 88
    await vm.fetchDriftAlert()

    expect(mockGetDriftAlert).toHaveBeenCalledWith(88)
    expect(vm.driftData?.severity).toBe('none')
    expect(wrapper.text()).toContain('各项性能指标稳定')
  })

  it('triggers baseline auto promote', async () => {
    const wrapper = mount(BaselineDriftMonitor, {
      props: { testId: 5, runId: 88 },
      global: {
        stubs: {
          'a-input-number': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-card': { template: '<div><slot /></div>' },
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      runAutoPromote: () => Promise<void>
      currentTestId: number
      promotionResult: { promoted: boolean; new_baseline_run_id: number } | null
    }

    vm.currentTestId = 5
    await vm.runAutoPromote()

    expect(mockAlignBaseline).toHaveBeenCalledWith(5, true)
    expect(vm.promotionResult?.promoted).toBe(true)
    expect(vm.promotionResult?.new_baseline_run_id).toBe(101)
  })
})
