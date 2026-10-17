import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DeviceFleetHealthDrawer from './DeviceFleetHealthDrawer.vue'
import { fleetSchedulerApi } from '@/api/fleetScheduler'

const mockDevices = [
  {
    device_id: '00008101-IPHONE-REAL-01',
    platform: 'ios' as const,
    battery_temperature_c: 32.4,
    battery_level_percent: 88,
    battery_state: 'CHARGING' as const,
    cpu_usage_percent: 18.0,
    memory_free_mb: 1850,
    current_concurrency: 1,
    max_concurrency: 2,
    tunnel_rtt_ms: 12.5,
    health_status: 'HEALTHY' as const,
    health_score: 96.5,
    recorded_at: '2026-10-17 12:00:00',
  },
  {
    device_id: '127.0.0.1:5555',
    platform: 'android' as const,
    battery_temperature_c: 31.0,
    battery_level_percent: 92,
    battery_state: 'FULL' as const,
    cpu_usage_percent: 12.0,
    memory_free_mb: 2400,
    current_concurrency: 0,
    max_concurrency: 2,
    tunnel_rtt_ms: 8.0,
    health_status: 'HEALTHY' as const,
    health_score: 98.0,
    recorded_at: '2026-10-17 12:00:00',
  },
  {
    device_id: '127.0.0.1:5557',
    platform: 'android' as const,
    battery_temperature_c: 43.1,
    battery_level_percent: 68,
    battery_state: 'CHARGING' as const,
    cpu_usage_percent: 75.0,
    memory_free_mb: 450,
    current_concurrency: 0,
    max_concurrency: 2,
    tunnel_rtt_ms: 32.0,
    health_status: 'OVERHEATED' as const,
    health_score: 52.0,
    recorded_at: '2026-10-17 12:00:00',
  },
]

const mockCapacity = {
  total_devices: 3,
  healthy_count: 2,
  warming_count: 0,
  overheated_count: 1,
  low_battery_count: 0,
  offline_count: 0,
  total_capacity: 6,
  used_concurrency: 1,
  available_capacity: 5,
  cluster_averages: {
    avg_temperature_c: 35.5,
    avg_battery_percent: 82.7,
    avg_tunnel_rtt_ms: 17.5,
  },
}

const stubs = {
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-radio-group': { template: '<div><slot /></div>' },
  'a-radio-button': { template: '<button class="platform-btn"><slot /></button>' },
  'a-input-search': {
    template: '<input class="ant-input-search" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
}

describe('DeviceFleetHealthDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(fleetSchedulerApi, 'listDevicesTelemetry').mockResolvedValue({
      total: 3,
      devices: mockDevices,
    })
    vi.spyOn(fleetSchedulerApi, 'getCapacitySummary').mockResolvedValue(mockCapacity)
  })

  it('renders drawer header, average temperature, and capacity metrics when open', async () => {
    const wrapper = mount(DeviceFleetHealthDrawer, {
      props: {
        open: true,
      },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('物理真机在线集群拓扑')
    expect(wrapper.text()).toContain('35.5°C')
    expect(wrapper.text()).toContain('全集群平均温度')
    expect(wrapper.text()).toContain('健康在线:')
    expect(wrapper.text()).toContain('2 台')
    expect(wrapper.text()).toContain('过热冷却:')
    expect(wrapper.text()).toContain('1 台')
  })

  it('renders device health cards with metrics', async () => {
    const wrapper = mount(DeviceFleetHealthDrawer, {
      props: {
        open: true,
      },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('00008101-IPHONE-REAL-01')
    expect(wrapper.text()).toContain('32.4°C')
    expect(wrapper.text()).toContain('127.0.0.1:5555')
    expect(wrapper.text()).toContain('98 分')
    expect(wrapper.text()).toContain('127.0.0.1:5557')
    expect(wrapper.text()).toContain('OVERHEATED')
  })

  it('filters device cards by platform', async () => {
    const wrapper = mount(DeviceFleetHealthDrawer, {
      props: {
        open: true,
      },
      global: { stubs },
    })
    await flushPromises()

    const vm = wrapper.vm as any
    vm.selectedPlatformFilter = 'ios'
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('00008101-IPHONE-REAL-01')
    expect(wrapper.text()).not.toContain('127.0.0.1:5555')
  })

  it('emits selected event when device card is clicked', async () => {
    const wrapper = mount(DeviceFleetHealthDrawer, {
      props: {
        open: true,
      },
      global: { stubs },
    })
    await flushPromises()

    const cards = wrapper.findAll('.device-health-card')
    expect(cards.length).toBe(3)
    await cards[0].trigger('click')

    expect(wrapper.emitted('selected')).toBeDefined()
    expect(wrapper.emitted('selected')![0]).toEqual(['00008101-IPHONE-REAL-01'])
  })
})
