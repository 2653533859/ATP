import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DeviceMirrorModal from './DeviceMirrorModal.vue'

const {
  screenshotMock,
  keyeventMock,
  inputTextMock,
  messageWarning,
  tapMock,
  uiTargetMock,
} = vi.hoisted(() => ({
  screenshotMock: vi.fn(),
  keyeventMock: vi.fn(),
  inputTextMock: vi.fn(),
  messageWarning: vi.fn(),
  tapMock: vi.fn(),
  uiTargetMock: vi.fn(),
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
    tap: tapMock,
    swipe: vi.fn(),
    uiTarget: uiTargetMock,
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

function mountModal(props: { open: boolean; device: any; recordable?: boolean }) {
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
    tapMock.mockResolvedValue({})
    uiTargetMock.mockResolvedValue({ target: { resourceId: 'com.example:id/login' } })
  })

  it('records a successful mirror tap as an editable locator step', async () => {
    const device = { id: 1, serial: 'DEV-1', brand: 'Google', model: 'Pixel', resolution: '1080x1920', status: 'online' }
    const wrapper = mountModal({ open: true, device, recordable: true })
    await flushPromises()
    const vm = wrapper.vm as unknown as { refreshMirror: () => Promise<void>; startRecording: () => void; finishRecording: () => void }
    await vm.refreshMirror()
    await flushPromises()
    const image = wrapper.find('.mirror-img')
    expect(image.exists()).toBe(true)
    Object.defineProperty(image.element, 'naturalWidth', { value: 1080 })
    Object.defineProperty(image.element, 'naturalHeight', { value: 1920 })
    image.element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 540, height: 960, right: 540, bottom: 960 } as DOMRect)

    vm.startRecording()
    await image.trigger('mousedown', { clientX: 100, clientY: 200 })
    await image.trigger('mouseup', { clientX: 100, clientY: 200 })
    await flushPromises()
    vm.finishRecording()

    expect(uiTargetMock).toHaveBeenCalledWith(1, { x: 200, y: 400 })
    expect(tapMock).toHaveBeenCalledWith(1, { x: 200, y: 400 })
    expect(wrapper.emitted('recorded')?.[0]?.[0]).toEqual([{
      action: 'click', name: '镜像点击',
      params: expect.objectContaining({ x: 200, y: 400, resourceId: 'com.example:id/login' }),
    }])
    wrapper.unmount()
  })

  it('keeps failed mirror actions out of the recorded draft', async () => {
    const device = { id: 1, serial: 'DEV-1', brand: 'Google', model: 'Pixel', resolution: '1080x1920', status: 'online' }
    tapMock.mockRejectedValueOnce(new Error('device disconnected'))
    const wrapper = mountModal({ open: true, device, recordable: true })
    await flushPromises()
    const vm = wrapper.vm as unknown as { refreshMirror: () => Promise<void>; startRecording: () => void; finishRecording: () => void }
    await vm.refreshMirror()
    await flushPromises()
    const image = wrapper.find('.mirror-img')
    image.element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 540, height: 960, right: 540, bottom: 960 } as DOMRect)
    vm.startRecording()
    await image.trigger('mousedown', { clientX: 100, clientY: 200 })
    await image.trigger('mouseup', { clientX: 100, clientY: 200 })
    await flushPromises()
    vm.finishRecording()

    expect(wrapper.emitted('recorded')).toBeUndefined()
    wrapper.unmount()
  })

  it('maps live canvas positions to device coordinates and screen size', async () => {
    const device = { id: 1, serial: 'DEV-1', brand: 'Google', model: 'Pixel', resolution: '1080x1920', status: 'online' }
    const wrapper = mountModal({ open: true, device })
    await flushPromises()
    const canvas = wrapper.find('.mirror-canvas').element as HTMLCanvasElement
    canvas.width = 1080
    canvas.height = 1920
    canvas.getBoundingClientRect = () => ({ left: 10, top: 20, width: 540, height: 960, right: 550, bottom: 980 } as DOMRect)
    const vm = wrapper.vm as unknown as { getCanvasCoords: (event: MouseEvent) => Record<string, number> }

    expect(vm.getCanvasCoords(new MouseEvent('mousedown', { clientX: 110, clientY: 220 })))
      .toEqual({ x: 200, y: 400, w: 1080, h: 1920 })
    wrapper.unmount()
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
