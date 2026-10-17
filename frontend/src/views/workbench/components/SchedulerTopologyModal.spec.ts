import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SchedulerTopologyModal from './SchedulerTopologyModal.vue'
import { fleetSchedulerApi } from '@/api/fleetScheduler'

const mockDecision = {
  decision_id: 'route_test_101',
  task_id: 'task_sim_001',
  target_platform: 'ios',
  status: 'ROUTED' as const,
  selected_device_id: '00008101-IPHONE-REAL-01',
  fitness_score: 95.5,
  candidate_evaluations: [
    {
      device_id: '00008101-IPHONE-REAL-01',
      platform: 'ios',
      eligible: true,
      disqualify_reason: '',
      health_score: 96.5,
      load_margin_score: 100.0,
      latency_score: 100.0,
      affinity_score: 50.0,
      composite_fitness: 95.5,
    },
    {
      device_id: '00008101-IPHONE-HOT-02',
      platform: 'ios',
      eligible: false,
      disqualify_reason: '设备过热 (43.5°C)',
      health_score: 52.0,
      load_margin_score: 0.0,
      latency_score: 80.0,
      affinity_score: 50.0,
      composite_fitness: 0.0,
    },
  ],
  routing_reason: '全局最优匹配: 综合适应度得分 95.5 分',
  allocated_at: '2026-10-17 12:00:00',
}

const stubs = {
  'a-modal': { template: '<div class="ant-modal-stub"><slot /></div>' },
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-radio-group': { template: '<div><slot /></div>' },
  'a-radio-button': { template: '<button><slot /></button>' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-input': {
    template: '<input :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'a-input-number': {
    template: '<input type="number" :value="value" @input="$emit(\'update:value\', Number($event.target.value))" />',
    props: ['value'],
  },
  'a-table': {
    template: `
      <div class="ant-table-stub">
        <div v-for="item in dataSource" :key="item.device_id" class="table-row">
          <span>{{ item.device_id }}</span>
          <span>{{ item.composite_fitness }}</span>
        </div>
      </div>
    `,
    props: ['dataSource', 'columns'],
  },
}

describe('SchedulerTopologyModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(fleetSchedulerApi, 'dispatchTask').mockResolvedValue({
      message: '调度成功',
      decision: mockDecision,
      is_allocated: true,
    })
  })

  it('renders modal banner, platform radios, and simulate button when open', () => {
    const wrapper = mount(SchedulerTopologyModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    expect(wrapper.text()).toContain('Dynamic Concurrency Router & Topology Simulator')
    expect(wrapper.text()).toContain('目标终端平台:')
    expect(wrapper.text()).toContain('任务优先级:')
    expect(wrapper.text()).toContain('执行自适应路由演算')
  })

  it('triggers dispatchTask API and renders routing decision result and candidates table', async () => {
    const wrapper = mount(SchedulerTopologyModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    const simulateBtn = wrapper.findAll('button').find((b) => b.text().includes('执行自适应路由演算'))
    expect(simulateBtn).toBeDefined()
    await simulateBtn!.trigger('click')
    await flushPromises()

    expect(fleetSchedulerApi.dispatchTask).toHaveBeenCalled()

    // 查验渲染结果
    expect(wrapper.text()).toContain('ROUTED')
    expect(wrapper.text()).toContain('00008101-IPHONE-REAL-01')
    expect(wrapper.text()).toContain('95.5 分')
    expect(wrapper.text()).toContain('全局最优匹配')
    expect(wrapper.text()).toContain('00008101-IPHONE-HOT-02')
  })

  it('emits dispatched event and closes modal when confirming dispatch', async () => {
    const wrapper = mount(SchedulerTopologyModal, {
      props: {
        open: true,
      },
      global: { stubs },
    })

    // 先执行演算
    const simulateBtn = wrapper.findAll('button').find((b) => b.text().includes('执行自适应路由演算'))
    await simulateBtn!.trigger('click')
    await flushPromises()

    // 点击确认派发
    const confirmBtn = wrapper.findAll('button').find((b) => b.text().includes('确认派发并锁定真机租约'))
    expect(confirmBtn).toBeDefined()
    await confirmBtn!.trigger('click')

    expect(wrapper.emitted('dispatched')).toBeDefined()
    expect(wrapper.emitted('dispatched')![0][0]).toEqual(mockDecision)
    expect(wrapper.emitted('update:open')![0]).toEqual([false])
  })
})
