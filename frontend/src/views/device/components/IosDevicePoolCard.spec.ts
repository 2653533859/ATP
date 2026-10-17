import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import IosDevicePoolCard from './IosDevicePoolCard.vue'
import type { IosTunnelDeviceItem } from '@/api/iosTunnel'

const mockDevice: IosTunnelDeviceItem = {
  udid: '00008101-001122334455667E',
  device_name: 'iPhone 15 Pro',
  model: 'iPhone16,1',
  ios_version: '17.4.1',
  agent_id: 'mac_agent_01',
  agent_name: 'Mac-Mini-M2',
  remote_wda_port: 8100,
  local_tunnel_port: 8201,
  status: 'CONNECTED',
  battery_level: 95,
  temperature_celsius: 29.0,
  wda_alive: true,
  health_status: 'ONLINE',
  connected_at: '2026-10-17T12:00:00Z',
  last_activity_at: '2026-10-17T12:00:00Z',
}

describe('IosDevicePoolCard.vue', () => {
  function createWrapper(props = {}) {
    return mount(IosDevicePoolCard, {
      props: {
        device: mockDevice,
        ...props,
      },
      global: {
        stubs: {
          'a-button': {
            template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
            props: ['disabled', 'type'],
          },
          'a-tag': {
            template: '<span class="ant-tag"><slot /></span>',
          },
          'a-space': {
            template: '<div class="ant-space"><slot /></div>',
          },
        },
      },
    })
  }

  it('renders device title, model, battery and wda port', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('iPhone 15 Pro')
    expect(wrapper.text()).toContain('iPhone16,1')
    expect(wrapper.text()).toContain('iOS 17.4.1')
    expect(wrapper.text()).toContain('95%')
    expect(wrapper.text()).toContain(':8201')
    expect(wrapper.text()).toContain('在线空闲')
  })

  it('emits open-mirror event when clicking mirror button', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const buttons = wrapper.findAll('button')
    // 第一个按钮是投屏控制
    await buttons[0].trigger('click')
    await flushPromises()

    expect(wrapper.emitted('open-mirror')).toBeTruthy()
    expect(wrapper.emitted('open-mirror')![0][0]).toEqual(mockDevice)
  })

  it('emits acquire-lease event when clicking acquire button on idle device', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const buttons = wrapper.findAll('button')
    // 第二个按钮是申领租约
    await buttons[1].trigger('click')
    await flushPromises()

    expect(wrapper.emitted('acquire-lease')).toBeTruthy()
  })

  it('renders busy status and emits release-lease when device is leased', async () => {
    const wrapper = createWrapper({
      device: { ...mockDevice, status: 'BUSY' },
      leaseInfo: {
        lease_token: 'token_123',
        udid: mockDevice.udid,
        owner_id: '1',
        owner_label: 'QA-Engineer',
        purpose: 'debug',
        ttl_seconds: 300,
        acquired_at: '',
        heartbeat_at: '',
        expires_at: '',
        is_active: true,
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('租用占用')
    expect(wrapper.text()).toContain('QA-Engineer')

    const buttons = wrapper.findAll('button')
    // 归还租约按钮
    await buttons[1].trigger('click')
    await flushPromises()

    expect(wrapper.emitted('release-lease')).toBeTruthy()
  })
})
