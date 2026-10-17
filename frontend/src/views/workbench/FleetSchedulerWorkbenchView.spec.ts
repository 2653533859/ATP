import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import FleetSchedulerWorkbenchView from './FleetSchedulerWorkbenchView.vue'
import { fleetSchedulerApi } from '@/api/fleetScheduler'

const mockDevices = [
  {
    device_id: '00008101-IPHONE-REAL-01',
    platform: 'ios' as const,
    battery_temperature_c: 32.5,
    battery_level_percent: 88,
    battery_state: 'CHARGING' as const,
    cpu_usage_percent: 22.0,
    memory_free_mb: 1800,
    current_concurrency: 1,
    max_concurrency: 2,
    tunnel_rtt_ms: 12.0,
    health_status: 'HEALTHY' as const,
    health_score: 96.0,
    recorded_at: '2026-10-17 12:00:00',
  },
]

const mockHistory = [
  {
    decision_id: 'route_checkout_001',
    task_id: 'task_e2e_hybrid_101',
    target_platform: 'ios',
    status: 'ROUTED' as const,
    selected_device_id: '00008101-IPHONE-REAL-01',
    fitness_score: 95.5,
    candidate_evaluations: [],
    routing_reason: '全局最优匹配: 综合适应度得分 95.5 分',
    allocated_at: '2026-10-17 12:00:00',
  },
]

const mockBpStatus = {
  snapshot_id: 'snap_bp_test',
  current_window_size: 14,
  queue_depth: 4,
  total_fleet_capacity: 16,
  used_concurrency: 4,
  saturation_ratio: 0.25,
  average_wait_latency_ms: 50.0,
  level: 'NORMAL' as const,
  action_description: '集群算力健康充裕',
  timestamp: '2026-10-17 12:00:00',
}

const stubs = {
  'a-button': { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  'a-card': { template: '<div class="ant-card"><slot /></div>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-space': { template: '<div class="ant-space"><slot /></div>' },
  'a-tabs': { template: '<div class="ant-tabs"><slot /></div>' },
  'a-tab-pane': { template: '<div class="ant-tab-pane"><slot /></div>' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-input-search': {
    template: '<input class="ant-input-search" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'a-table': {
    template: `
      <div class="ant-table">
        <div v-for="item in dataSource" :key="item.device_id || item.decision_id" class="table-row">
          <span>{{ item.device_id || item.decision_id }}</span>
          <span>{{ item.task_id || item.health_status }}</span>
          <button class="action-btn" @click="$parent.$emit('action', item)">操作</button>
        </div>
      </div>
    `,
    props: ['dataSource', 'columns'],
  },
  DeviceFleetHealthDrawer: {
    template: '<div v-if="open" class="device-fleet-health-drawer-stub" />',
    props: ['open', 'selectedDeviceId'],
  },
  SchedulerTopologyModal: {
    template: '<div v-if="open" class="scheduler-topology-modal-stub" />',
    props: ['open'],
  },
}

describe('FleetSchedulerWorkbenchView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(fleetSchedulerApi, 'listDevicesTelemetry').mockResolvedValue({
      total: 1,
      devices: mockDevices,
    })
    vi.spyOn(fleetSchedulerApi, 'listRoutingHistory').mockResolvedValue({
      total: 1,
      history: mockHistory,
    })
    vi.spyOn(fleetSchedulerApi, 'getBackpressureStatus').mockResolvedValue({
      status: mockBpStatus,
    })
  })

  function createWrapper() {
    return mount(FleetSchedulerWorkbenchView, {
      global: { stubs },
    })
  }

  it('renders workbench title and 4 Bento KPI cards', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('物理真机集群自适应并发调度与算力拓扑中台')
    expect(wrapper.text()).toContain('真机集群健康在线率')
    expect(wrapper.text()).toContain('96.8%')
    expect(wrapper.text()).toContain('纳管在线物理真机')
    expect(wrapper.text()).toContain('自适应路由秒级派发率')
    expect(wrapper.text()).toContain('99.4%')
    expect(wrapper.text()).toContain('故障热漂移自愈成功率')
  })

  it('loads devices list and routing history on mount', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(fleetSchedulerApi.listDevicesTelemetry).toHaveBeenCalled()
    expect(fleetSchedulerApi.listRoutingHistory).toHaveBeenCalled()

    expect(wrapper.text()).toContain('00008101-IPHONE-REAL-01')
    expect(wrapper.text()).toContain('HEALTHY')
  })

  it('opens DeviceFleetHealthDrawer when clicking 设备集群热力透视', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const heatBtn = wrapper.findAll('header button').find((b) => b.text().includes('设备集群热力透视'))
    expect(heatBtn).toBeDefined()
    await heatBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.device-fleet-health-drawer-stub').exists()).toBe(true)
  })

  it('opens SchedulerTopologyModal when clicking 模拟任务调度演练', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const topoBtn = wrapper.findAll('header button').find((b) => b.text().includes('模拟任务调度演练'))
    expect(topoBtn).toBeDefined()
    await topoBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.scheduler-topology-modal-stub').exists()).toBe(true)
  })

  it('opens DeviceFleetHealthDrawer with deviceId when calling viewDeviceHealth', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.viewDeviceHealth('00008101-IPHONE-REAL-01')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.device-fleet-health-drawer-stub').exists()).toBe(true)
    expect(vm.selectedDeviceId).toBe('00008101-IPHONE-REAL-01')
  })
})
