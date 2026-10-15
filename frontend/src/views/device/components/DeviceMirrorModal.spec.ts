import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DeviceMirrorModal from './DeviceMirrorModal.vue'

const {
  screenshotMock,
  keyeventMock,
  inputTextMock,
  messageWarning,
} = vi.hoisted(() => ({
  screenshotMock: vi.fn(),
  keyeventMock: vi.fn(),
  inputTextMock: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }),
}))

vi.mock('ant-design-vue', () => ({
  message: { warning: messageWarning },
}))

vi.mock('@/api', () => ({
  deviceApi: {
    screenshot: screenshotMock,
    keyevent: keyeventMock,
    inputText: inputTextMock,
    tap: vi.fn(),
    swipe: vi.fn(),
  },
}))

vi.mock('@/composables/useWebCodecsDecoder', () => ({
  isWebCodecsSupported: () => true,
  useWebCodecsDecoder: vi.fn(() => ({
    push: vi.fn(),
    destroy: vi.fn(),
  })),
}))

const modalStub = defineComponent({
  name: 'AModal',
  props: ['open', 'title', 'width'],
  emits: ['cancel', 'update:open'],
  setup(props, { slots, emit }) {
    return () =>
      props.open
        ? h('div', { class: 'ant-modal', 'data-title': props.title, 'data-width': props.width }, [
            h('button', { class: 'modal-close', onClick: () => emit('cancel') }, 'close'),
            slots.default?.(),
          ])
        : null
  },
})

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

function mountModal(props: { open: boolean; device: any }) {
  return mount(DeviceMirrorModal, {
    props,
    global: {
      stubs: {
        AModal: modalStub,
        ATooltip: passthrough('ATooltip'),
        ASpin: passthrough('ASpin'),
        ARadioGroup: passthrough('ARadioGroup'),
        ARadioButton: passthrough('ARadioButton'),
        AInput: defineComponent({
          name: 'AInput',
          props: ['value'],
          emits: ['update:value', 'pressEnter'],
          setup: (p, { emit }) => () =>
            h('input', {
              class: 'quick-input',
              value: p.value,
              onInput: (e: any) => emit('update:value', e.target.value),
              onKeydown: (e: KeyboardEvent) => {
                if (e.key === 'Enter') emit('pressEnter')
              },
            }),
        }),
        AButton: defineComponent({
          name: 'AButton',
          emits: ['click'],
          setup: (_p, { slots, emit }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()),
        }),
      },
    },
  })
}

describe('DeviceMirrorModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    screenshotMock.mockResolvedValue(new Blob(['img'], { type: 'image/jpeg' }))
  })

  it('renders modal with device title and navigation controls', async () => {
    const device = {
      id: 1,
      serial: '172.16.102.167:5555',
      brand: 'rockchip',
      model: 'rk3588',
      name: 'rk3588',
      resolution: '2160x3840',
      status: 'online',
    }

    const wrapper = mountModal({ open: true, device })
    await flushPromises()

    const modal = wrapper.find('.ant-modal')
    expect(modal.exists()).toBe(true)
    expect(modal.attributes('data-title')).toContain('rk3588')

    // 检查快捷导航栏按钮（Back, Home, Recents, Power, Vol+, Vol-）
    const navButtons = wrapper.findAll('.nav-key-btn')
    expect(navButtons.length).toBe(6)

    wrapper.unmount()
  })

  it('sends keyevent when navigation button is clicked', async () => {
    const device = {
      id: 2,
      serial: 'SN123456',
      brand: 'HUAWEI',
      model: 'BZH5-W00',
      name: 'BZH5-W00',
      resolution: '2560x1600',
      status: 'online',
    }

    const wrapper = mountModal({ open: true, device })
    await flushPromises()

    const navButtons = wrapper.findAll('.nav-key-btn')
    // Click Home button (index 1, keycode 3)
    await navButtons[1].trigger('click')
    await flushPromises()

    expect(keyeventMock).toHaveBeenCalledWith(2, 3)

    wrapper.unmount()
  })

  it('emits update:open false and close event when cancelled', async () => {
    const device = {
      id: 1,
      serial: 'DEV-1',
      brand: 'Google',
      model: 'Pixel',
      status: 'online',
    }

    const wrapper = mountModal({ open: true, device })
    await flushPromises()

    await wrapper.find('.modal-close').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('update:open')).toBeTruthy()
    expect(wrapper.emitted('update:open')![0]).toEqual([false])
    expect(wrapper.emitted('close')).toBeTruthy()

    wrapper.unmount()
  })
})
