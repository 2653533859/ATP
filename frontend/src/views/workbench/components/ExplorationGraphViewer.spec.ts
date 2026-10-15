import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ExplorationGraphViewer from './ExplorationGraphViewer.vue'

const mockGetSession = vi.fn().mockResolvedValue({
  total_states: 3,
  total_actions_discovered: 10,
  total_actions_visited: 8,
  coverage_percent: 80.0,
  total_transitions: 4,
  current_state_id: 'live_state_12345',
  nodes: [
    { id: 'live_state_12345', name: 'Live Screen A', depth: 0, actions_count: 5, visited_count: 4 },
    { id: 'live_state_67890', name: 'Live Screen B', depth: 1, actions_count: 5, visited_count: 4 },
  ],
  links: [
    { from: 'live_state_12345', to: 'live_state_67890', action: 'click' },
  ],
})

vi.mock('@/api/exploration', () => ({
  explorationApi: {
    getSession: (sid: string) => mockGetSession(sid),
    step: vi.fn(),
    synthesizeCase: vi.fn(),
    evaluateCircuitBreaker: vi.fn(),
  },
}))

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="echarts-stub" />' },
}))

describe('ExplorationGraphViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders initial demo graph and displays coverage metrics', async () => {
    const wrapper = mount(ExplorationGraphViewer, {
      global: {
        stubs: {
          'a-progress': true,
          'a-input': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-divider': true,
          'a-empty': { template: '<div class="empty-stub"><slot /></div>' },
        },
      },
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('已发现页面状态 (States)')
    expect(wrapper.text()).toContain('交互动作覆盖率 (Actions)')
    expect(wrapper.text()).toContain('83.3%')

    const vm = wrapper.vm as unknown as {
      metrics: { total_states: number; coverage_percent: number }
      selectedNode: { name: string; id: string } | null
    }

    expect(vm.metrics.total_states).toBe(5)
    expect(vm.selectedNode?.id).toBe('e5f6000000000005')
  })

  it('fetches live session graph when session ID is submitted', async () => {
    const wrapper = mount(ExplorationGraphViewer, {
      global: {
        stubs: {
          'a-progress': true,
          'a-input': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-divider': true,
          'a-empty': true,
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      sessionIdInput: string
      fetchSessionGraph: () => Promise<void>
      metrics: { current_state_id: string | null; total_states: number }
    }

    vm.sessionIdInput = 'exp_test_session_01'
    await vm.fetchSessionGraph()

    expect(mockGetSession).toHaveBeenCalledWith('exp_test_session_01')
    expect(vm.metrics.current_state_id).toBe('live_state_12345')
    expect(vm.metrics.total_states).toBe(3)
  })
})
