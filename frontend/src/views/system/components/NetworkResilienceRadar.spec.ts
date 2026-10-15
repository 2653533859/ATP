import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import NetworkResilienceRadar from './NetworkResilienceRadar.vue'

const mockEvaluateFault = vi.fn().mockResolvedValue({
  fault_injected: true,
  action: 'dns_spoofing',
  target_url: 'http://127.0.0.1:9999/downstream-sink',
  details: {
    policy_action: 'dns_spoofing',
    matched_pattern: '.*pay.*',
  },
})

vi.mock('@/api/networkSimulation', () => ({
  networkSimulationApi: {
    evaluateFaultInjection: (payload: unknown) => mockEvaluateFault(payload),
  },
}))

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="echarts-stub" />' },
}))

describe('NetworkResilienceRadar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders resilience score badge and radar chart properly', () => {
    const wrapper = mount(NetworkResilienceRadar, {
      props: {
        profileName: '4G (LTE 城市)',
        metrics: {
          resilience_score: 92.4,
          resilience_rating: 'A',
          avg_latency_ms: 65.0,
          p95_latency_ms: 120.0,
          error_rate: 0.01,
          retry_rate: 0.02,
        },
      },
      global: {
        stubs: {
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': true,
          'a-input-number': true,
          'a-select': true,
          'a-select-option': true,
          'a-button': { template: '<button><slot /></button>' },
        },
      },
    })

    expect(wrapper.text()).toContain('92.4')
    expect(wrapper.text()).toContain('等级 A')
    expect(wrapper.text()).toContain('4G (LTE 城市)')

    const vm = wrapper.vm as unknown as {
      radarScores: number[]
      metricsSummary: { resilience_score: number; resilience_rating: string }
    }

    expect(vm.metricsSummary.resilience_score).toBe(92.4)
    expect(vm.metricsSummary.resilience_rating).toBe('A')
    expect(vm.radarScores.length).toBe(5)
  })

  it('triggers fault evaluation and displays result panel', async () => {
    const wrapper = mount(NetworkResilienceRadar, {
      props: {
        profileName: '2G (EDGE 良好)',
      },
      global: {
        stubs: {
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': true,
          'a-input-number': true,
          'a-select': true,
          'a-select-option': true,
          'a-button': { template: '<button><slot /></button>' },
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      runFaultEvaluation: () => Promise<void>
      faultResult: { fault_injected: boolean; action: string } | null
    }

    await vm.runFaultEvaluation()

    expect(mockEvaluateFault).toHaveBeenCalled()
    expect(vm.faultResult).toBeTruthy()
    expect(vm.faultResult?.fault_injected).toBe(true)
    expect(vm.faultResult?.action).toBe('dns_spoofing')
  })
})
