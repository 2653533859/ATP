import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ExplorationCircuitBreakerCard from './ExplorationCircuitBreakerCard.vue'

const mockEvaluateBreaker = vi.fn().mockResolvedValue({
  is_tripped: true,
  trip_reason: '连续 3 步屏幕无任何可交互元素（黑屏/白屏/崩溃），触发熔断保护',
  trip_category: 'black_screen_detected',
  consecutive_zero_elements: 3,
  consecutive_failures: 0,
  oscillation_count: 0,
  step_count: 15,
  status: 'tripped',
})

vi.mock('@/api/exploration', () => ({
  explorationApi: {
    evaluateCircuitBreaker: (payload: unknown) => mockEvaluateBreaker(payload),
    step: vi.fn(),
    getSession: vi.fn(),
    synthesizeCase: vi.fn(),
  },
}))

describe('ExplorationCircuitBreakerCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders initial healthy normal state and probes', () => {
    const wrapper = mount(ExplorationCircuitBreakerCard, {
      global: {
        stubs: {
          'a-tag': { template: '<span><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-progress': true,
        },
      },
    })

    expect(wrapper.text()).toContain('探索健康监控与熔断保护中')
    expect(wrapper.text()).toContain('正常探索中')
    expect(wrapper.text()).toContain('黑屏/假死探针')
    expect(wrapper.text()).toContain('动作失败探针')
    expect(wrapper.text()).toContain('死循环振荡探针')
  })

  it('simulates black screen crash and triggers circuit breaker trip', async () => {
    const wrapper = mount(ExplorationCircuitBreakerCard, {
      global: {
        stubs: {
          'a-tag': { template: '<span><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-progress': true,
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      simulateBlackScreen: () => Promise<void>
      statusData: { is_tripped: boolean; trip_category: string | null }
      resetCircuitBreaker: () => void
    }

    await vm.simulateBlackScreen()
    await wrapper.vm.$nextTick()

    expect(vm.statusData.is_tripped).toBe(true)
    expect(vm.statusData.trip_category).toBe('black_screen_detected')
    expect(wrapper.text()).toContain('已触发自动熔断保护并终止会话')
    expect(wrapper.text()).toContain('黑屏假死/页面崩溃')
    expect(wrapper.text()).toContain('事故终止快照归档')

    // Reset breaker
    vm.resetCircuitBreaker()
    await wrapper.vm.$nextTick()
    expect(vm.statusData.is_tripped).toBe(false)
    expect(wrapper.text()).toContain('正常探索中')
  })

  it('simulates oscillation and action failure trips', async () => {
    const wrapper = mount(ExplorationCircuitBreakerCard, {
      global: {
        stubs: {
          'a-tag': { template: '<span><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-progress': true,
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      simulateOscillation: () => Promise<void>
      simulateActionFailure: () => Promise<void>
      statusData: { is_tripped: boolean; trip_category: string | null }
    }

    // 1. Oscillation
    await vm.simulateOscillation()
    await wrapper.vm.$nextTick()
    expect(vm.statusData.is_tripped).toBe(true)
    expect(vm.statusData.trip_category).toBe('infinite_loop_oscillation')
    expect(wrapper.text()).toContain('乒乓死循环振荡')

    // 2. Action failure
    await vm.simulateActionFailure()
    await wrapper.vm.$nextTick()
    expect(vm.statusData.is_tripped).toBe(true)
    expect(vm.statusData.trip_category).toBe('consecutive_action_failures')
    expect(wrapper.text()).toContain('驱动/无障碍服务失联')
  })
})
