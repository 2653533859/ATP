import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChaosRtoTimeline from './ChaosRtoTimeline.vue'

const mockCreateChaosPlan = vi.fn().mockResolvedValue({
  run_id: 101,
  plan_id: 'chaos_plan_9999',
  fault_type: 'service_unavailable',
  target_service: 'order-downstream-api',
  start_delay_seconds: 10,
  duration_seconds: 20,
  fault_params: {},
  status: 'scheduled',
  created_at: '2026-10-16T12:00:00Z',
})

const mockEvaluateChaosRto = vi.fn().mockResolvedValue({
  recovered: true,
  rto_seconds: 1.85,
  recovered_at_offset: 31.85,
  fault_start_offset: 10.0,
  fault_end_offset: 30.0,
  baseline_metrics: { rps: 1200.0, p95_ms: 45.0, error_rate: 0.0 },
  in_fault_metrics: { min_rps: 150.0, max_p95_ms: 380.0, max_error_rate: 0.25, rps_drop_pct: 87.5 },
  recovery_targets: { target_rps: 1020.0, target_p95_ms: 58.5, target_error_rate: 0.03, sustain_seconds: 3.0 },
  resilience_score: 96.0,
  resilience_grade: 'A',
  recommendation: '极速自愈恢复优良',
})

vi.mock('@/api', () => ({
  performanceApi: {
    createChaosPlan: (runId: number, body: unknown) => mockCreateChaosPlan(runId, body),
    evaluateChaosRto: (runId: number, body: unknown) => mockEvaluateChaosRto(runId, body),
  },
}))

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="echarts-stub" />' },
}))

describe('ChaosRtoTimeline', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders initial sample chaos timeline and RTO metrics', async () => {
    const wrapper = mount(ChaosRtoTimeline, {
      props: { runId: 101 },
      global: {
        stubs: {
          'a-input-number': true,
          'a-select': true,
          'a-select-option': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
        },
      },
    })

    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('自愈恢复时长 (RTO)')
    expect(wrapper.text()).toContain('2.50 秒')
    expect(wrapper.text()).toContain('Grade A')
    expect(wrapper.text()).toContain('94.0 分')

    const vm = wrapper.vm as unknown as {
      rtoData: { rto_seconds: number; resilience_grade: string } | null
    }

    expect(vm.rtoData?.rto_seconds).toBe(2.5)
    expect(vm.rtoData?.resilience_grade).toBe('A')
  })

  it('creates chaos plan on button click', async () => {
    const wrapper = mount(ChaosRtoTimeline, {
      props: { runId: 101 },
      global: {
        stubs: {
          'a-input-number': true,
          'a-select': true,
          'a-select-option': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      createPlan: () => Promise<void>
      currentRunId: number
    }

    vm.currentRunId = 101
    await vm.createPlan()

    expect(mockCreateChaosPlan).toHaveBeenCalledWith(
      101,
      expect.objectContaining({ fault_type: 'service_unavailable' }),
    )
  })

  it('evaluates chaos RTO on button click', async () => {
    const wrapper = mount(ChaosRtoTimeline, {
      props: { runId: 101 },
      global: {
        stubs: {
          'a-input-number': true,
          'a-select': true,
          'a-select-option': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      evaluateRto: () => Promise<void>
      currentRunId: number
      rtoData: { rto_seconds: number; resilience_grade: string } | null
    }

    vm.currentRunId = 101
    await vm.evaluateRto()

    expect(mockEvaluateChaosRto).toHaveBeenCalledWith(
      101,
      expect.objectContaining({ fault_start_offset: 10 }),
    )
    expect(vm.rtoData?.rto_seconds).toBe(1.85)
    expect(vm.rtoData?.resilience_grade).toBe('A')
  })
})
