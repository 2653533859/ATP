import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import IosDeviceCenterView from './IosDeviceCenterView.vue'
import { iosTunnelApi } from '@/api/iosTunnel'

const mockDevices = [
  {
    udid: '00008101-001122334455667E',
    device_name: 'iPhone 15 Pro Max',
    model: 'iPhone16,2',
    ios_version: '17.4.1',
    agent_id: 'agent_mac_m2_rack_a',
    agent_name: 'Mac-Mini-M2-01',
    remote_wda_port: 8100,
    local_tunnel_port: 8201,
    status: 'CONNECTED',
    battery_level: 96,
    temperature_celsius: 28.5,
    wda_alive: true,
    health_status: 'ONLINE',
    connected_at: '2026-10-17 10:00:00',
    last_activity_at: '2026-10-17 12:00:00',
  },
  {
    udid: '00008101-009988776655443E',
    device_name: 'iPhone 14 Plus',
    model: 'iPhone15,3',
    ios_version: '16.6.1',
    agent_id: 'agent_mac_studio_lab',
    agent_name: 'Mac-Studio-Rack-B',
    remote_wda_port: 8100,
    local_tunnel_port: 8202,
    status: 'BUSY',
    battery_level: 85,
    temperature_celsius: 29.8,
    wda_alive: true,
    health_status: 'BUSY',
    connected_at: '2026-10-17 09:30:00',
    last_activity_at: '2026-10-17 11:45:00',
  },
]

vi.mock('@/api/iosTunnel', () => ({
  iosTunnelApi: {
    listDevices: vi.fn(),
    listLeases: vi.fn(),
    acquireLease: vi.fn(),
    releaseLease: vi.fn(),
    sweepHeartbeats: vi.fn(),
    allocateDevice: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, fallback?: string) => fallback || key,
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

describe('IosDeviceCenterView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(iosTunnelApi.listDevices).mockResolvedValue({
      total: 2,
      devices: mockDevices,
    })
    vi.mocked(iosTunnelApi.listLeases).mockResolvedValue({
      total: 1,
      leases: [
        {
          lease_token: 'lease_token_test',
          udid: '00008101-009988776655443E',
          owner_id: '1',
          owner_label: 'QA-Alice',
          purpose: 'test',
          ttl_seconds: 300,
          acquired_at: '',
          heartbeat_at: '',
          expires_at: '',
          is_active: true,
        },
      ],
    })
    vi.mocked(iosTunnelApi.allocateDevice).mockResolvedValue({
      message: '调度成功',
      device: {
        unified_id: 'ios:00008101-001122334455667E',
        raw_id: '00008101-001122334455667E',
        platform: 'ios',
        name: 'iPhone 15 Pro Max',
        model: 'iPhone16,2',
        brand: 'Apple',
        os_version: '17.4.1',
        status: 'BUSY',
        tunnel_port: 8201,
        battery_level: 96,
        is_charging: true,
        temperature_celsius: 28.5,
        lease_token: 'auto_token_123',
      },
    })
  })

  function createWrapper() {
    return mount(IosDeviceCenterView, {
      global: {
        stubs: {
          'a-button': {
            template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
            props: ['type', 'loading', 'disabled'],
          },
          'a-card': {
            template: '<div class="ant-card"><slot /><slot name="extra" /></div>',
          },
          'a-tag': {
            template: '<span class="ant-tag"><slot /></span>',
          },
          'a-space': {
            template: '<div class="ant-space"><slot /></div>',
          },
          'a-radio-group': {
            template: '<div class="ant-radio-group"><slot /></div>',
            props: ['value'],
          },
          'a-radio-button': {
            template: '<button type="button" class="ant-radio-button" @click="$parent.$emit(\'update:value\', value)"><slot /></button>',
            props: ['value'],
          },
          'a-input-search': {
            template: '<input class="ant-input-search" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['value'],
          },
          'a-spin': {
            template: '<div class="ant-spin"><slot /></div>',
            props: ['spinning'],
          },
          'a-empty': {
            template: '<div class="ant-empty"><slot /></div>',
          },
          'a-modal': {
            template: '<div v-if="open" class="ant-modal"><slot /></div>',
            props: ['open', 'title'],
          },
          'a-descriptions': {
            template: '<div class="ant-descriptions"><slot /></div>',
          },
          'a-descriptions-item': {
            template: '<div class="ant-descriptions-item"><slot /></div>',
          },
          'a-form': {
            template: '<form class="ant-form"><slot /></form>',
          },
          'a-form-item': {
            template: '<div class="ant-form-item"><slot /></div>',
            props: ['label'],
          },
          'a-input': {
            template: '<input class="ant-input" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
            props: ['value'],
          },
          'a-select': {
            template: '<div class="ant-select"><slot /></div>',
            props: ['value'],
          },
          'a-select-option': {
            template: '<div class="ant-select-option"><slot /></div>',
            props: ['value'],
          },
          'a-table': {
            template: '<div class="ant-table" />',
            props: ['dataSource', 'columns'],
          },
          IosDevicePoolCard: {
            template: `
              <div class="ios-device-pool-card-stub" :data-udid="device.udid">
                <span class="card-name">{{ device.device_name }}</span>
                <button class="open-mirror-btn" @click="$emit('open-mirror', device)">投屏</button>
                <button class="acquire-btn" @click="$emit('acquire-lease', device)">租用</button>
                <button class="release-btn" @click="$emit('release-lease', device)">归还</button>
              </div>
            `,
            props: ['device', 'leaseInfo'],
          },
          IosScreenMirrorModal: {
            template: '<div v-if="open" class="ios-screen-mirror-modal-stub" :data-udid="udid" />',
            props: ['open', 'udid'],
          },
        },
      },
    })
  }

  it('renders iOS center title and 4 KPI cards', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('iOS 物理真机资产池与远程调度中心')
    expect(wrapper.text()).toContain('纳管物理 iPhone 总数')
    expect(wrapper.text()).toContain('空闲可用机位数')
    expect(wrapper.text()).toContain('排他租约占用率')
    expect(wrapper.text()).toContain('WDA 隧道健康率')
  })

  it('renders device cards and allows opening mirror modal', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const cards = wrapper.findAll('.ios-device-pool-card-stub')
    expect(cards.length).toBe(2)
    expect(wrapper.text()).toContain('iPhone 15 Pro Max')
    expect(wrapper.text()).toContain('iPhone 14 Plus')

    // 点击投屏按钮
    const mirrorBtn = wrapper.find('.open-mirror-btn')
    await mirrorBtn.trigger('click')
    await flushPromises()

    expect(wrapper.find('.ios-screen-mirror-modal-stub').exists()).toBe(true)
  })

  it('triggers auto allocate modal and dispatches allocation', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    // 触发智能分配
    await (wrapper.vm as any).confirmAutoAllocate()
    await flushPromises()

    expect(iosTunnelApi.allocateDevice).toHaveBeenCalledWith(
      expect.objectContaining({
        platform: 'ios',
        auto_lease: true,
      })
    )
  })
})
