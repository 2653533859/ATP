import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import IosScreenMirrorModal from './IosScreenMirrorModal.vue'
import { iosTunnelApi } from '@/api/iosTunnel'

vi.mock('@/api/iosTunnel', () => ({
  iosTunnelApi: {
    warmupWdaSession: vi.fn(),
    getScreenshot: vi.fn(),
    dispatchGesture: vi.fn(),
    healWda: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
  },
}))

describe('IosScreenMirrorModal.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(iosTunnelApi.warmupWdaSession).mockResolvedValue({
      message: '预热成功',
      session: {
        session_id: 'wda_test_sess_01',
        udid: '00008101-TEST',
        lease_token: 'lease_token_123',
        bundle_id: 'com.apple.Preferences',
        capabilities: {},
        status: 'ACTIVE',
        created_at: '2026-10-17T12:00:00Z',
        last_ping_at: '2026-10-17T12:00:00Z',
      },
    })
    vi.mocked(iosTunnelApi.getScreenshot).mockResolvedValue({
      udid: '00008101-TEST',
      session_id: 'wda_test_sess_01',
      screenshot_base64: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
    })
    vi.mocked(iosTunnelApi.dispatchGesture).mockResolvedValue({
      message: '手势执行成功',
      result: { action: 'tap', status: 'SUCCESS' },
    })
    vi.mocked(iosTunnelApi.healWda).mockResolvedValue({
      result: 'SUCCESS',
      message: '已自愈',
    })
  })

  function createWrapper(props = {}) {
    return mount(IosScreenMirrorModal, {
      props: {
        open: true,
        udid: '00008101-TEST',
        deviceName: 'iPhone 15 Pro Max',
        model: 'iPhone16,2',
        iosVersion: '17.5.1',
        batteryLevel: 95,
        leaseToken: 'lease_token_123',
        ...props,
      },
      global: {
        stubs: {
          'a-modal': {
            template: '<div v-if="open" class="ant-modal"><slot /></div>',
            props: ['open', 'title'],
          },
          'a-button': {
            template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
          },
          'a-tag': {
            template: '<span class="ant-tag"><slot /></span>',
          },
          'a-tooltip': {
            template: '<div class="ant-tooltip"><slot /></div>',
            props: ['title'],
          },
          'a-spin': {
            template: '<div class="ant-spin"><slot /></div>',
          },
          'a-space': {
            template: '<div class="ant-space"><slot /></div>',
          },
        },
      },
    })
  }

  it('renders device title, tags and dynamic island', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('iPhone 15 Pro Max')
    expect(wrapper.text()).toContain('iOS 17.5.1')
    expect(wrapper.text()).toContain('95% 电量')
    expect(wrapper.find('.dynamic-island').exists()).toBe(true)
  })

  it('fetches screenshot and displays rendered image', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const img = wrapper.find('.screen-render-img')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toContain('data:image/png;base64')
  })

  it('dispatches tap gesture on screen mousedown and mouseup', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const screen = wrapper.find('.iphone-screen')
    await screen.trigger('mousedown', { clientX: 100, clientY: 200 })
    await screen.trigger('mouseup', { clientX: 100, clientY: 200 })
    await flushPromises()

    expect(iosTunnelApi.dispatchGesture).toHaveBeenCalledWith(
      expect.objectContaining({
        udid: '00008101-TEST',
        action: 'tap',
      })
    )
  })

  it('dispatches home action when home button is clicked', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const homeBtn = wrapper.find('.key-btn-primary')
    await homeBtn.trigger('click')
    await flushPromises()

    expect(iosTunnelApi.dispatchGesture).toHaveBeenCalledWith(
      expect.objectContaining({
        udid: '00008101-TEST',
        action: 'home',
      })
    )
  })
})
