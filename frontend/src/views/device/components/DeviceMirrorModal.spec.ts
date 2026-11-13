import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import DeviceMirrorModal from './DeviceMirrorModal.vue'
import { isWebCodecsSupported } from '@/composables/useWebCodecsDecoder'

const {
  screenshotMock,
  keyeventMock,
  inputTextMock,
  messageWarning,
  messageSuccess,
  tapMock,
  uiTargetMock,
  uiAnchorsMock,
  acquireLeaseMock,
  heartbeatLeaseMock,
  releaseLeaseMock,
} = vi.hoisted(() => ({
  screenshotMock: vi.fn(),
  keyeventMock: vi.fn(),
  inputTextMock: vi.fn(),
  messageWarning: vi.fn(),
  messageSuccess: vi.fn(),
  tapMock: vi.fn(),
  uiTargetMock: vi.fn(),
  uiAnchorsMock: vi.fn(),
  acquireLeaseMock: vi.fn(),
  heartbeatLeaseMock: vi.fn(),
  releaseLeaseMock: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }),
}))

vi.mock('ant-design-vue', () => ({
  message: { warning: messageWarning, success: messageSuccess },
}))

vi.mock('@/api', () => ({
  deviceApi: {
    screenshot: screenshotMock,
    keyevent: keyeventMock,
    inputText: inputTextMock,
    tap: tapMock,
    swipe: vi.fn(),
    uiTarget: uiTargetMock,
    uiAnchors: uiAnchorsMock,
    acquireLease: acquireLeaseMock,
    heartbeatLease: heartbeatLeaseMock,
    releaseLease: releaseLeaseMock,
  },
}))

vi.mock('@/composables/useWebCodecsDecoder', () => ({
  isWebCodecsSupported: vi.fn(() => true),
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
            h('div', { class: 'ant-modal-title' }, slots.title ? slots.title() : props.title),
            h('button', { class: 'modal-close', onClick: () => emit('cancel') }, 'close'),
            slots.default?.(),
          ])
        : null
  },
})

const alertStub = defineComponent({
  name: 'AAlert',
  props: ['message', 'description', 'type'],
  setup: (props, { slots }) => () =>
    h('div', { class: 'alert-stub' }, [props.message, props.description, slots.action?.()]),
})

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

function mountModal(props: { open: boolean; device: any; recordable?: boolean; leaseToken?: string }) {
  return mount(DeviceMirrorModal, {
    props,
    global: {
      stubs: {
        AModal: modalStub,
        ATooltip: passthrough('ATooltip'),
        ASpin: passthrough('ASpin'),
        ASwitch: defineComponent({
          name: 'ASwitch',
          props: ['checked', 'disabled'],
          emits: ['update:checked'],
          setup(props, { emit }) {
            return () =>
              h('input', {
                type: 'checkbox',
                class: 'auto-assert-switch',
                checked: props.checked,
                disabled: props.disabled,
                onChange: (e: Event) => emit('update:checked', (e.target as HTMLInputElement).checked),
              })
          },
        }),
        ARadioGroup: passthrough('ARadioGroup'),
        ARadioButton: passthrough('ARadioButton'),
        ATag: passthrough('ATag'),
        ASpace: passthrough('ASpace'),
        ACheckbox: defineComponent({
          name: 'ACheckbox',
          props: ['checked', 'disabled'],
          emits: ['update:checked'],
          setup(props, { emit, slots }) {
            return () =>
              h('label', [
                h('input', {
                  type: 'checkbox',
                  class: 'mirror-sensitive-checkbox',
                  checked: props.checked,
                  disabled: props.disabled,
                  onChange: (e: Event) => emit('update:checked', (e.target as HTMLInputElement).checked),
                }),
                slots.default?.(),
              ])
          },
        }),
        AAlert: alertStub,
        AInput: defineComponent({
          name: 'AInput',
          props: ['value', 'type', 'disabled'],
          emits: ['update:value', 'pressEnter'],
          setup: (p, { emit }) => () =>
            h('input', {
              class: 'quick-input',
              type: p.type || 'text',
              value: p.value,
              disabled: p.disabled,
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
    vi.mocked(isWebCodecsSupported).mockReturnValue(true)
    screenshotMock.mockResolvedValue(new Blob(['img'], { type: 'image/jpeg' }))
    tapMock.mockResolvedValue({})
    uiTargetMock.mockResolvedValue({ target: { resourceId: 'com.example:id/login' } })
    uiAnchorsMock.mockResolvedValue({ anchors: null })
    acquireLeaseMock.mockResolvedValue({ lease_token: 'auto-test-lease', ttl_seconds: 600 })
    heartbeatLeaseMock.mockResolvedValue({ lease_token: 'auto-test-lease' })
    releaseLeaseMock.mockResolvedValue(true)
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('records a successful mirror tap as an editable locator step', async () => {
    const device = { id: 1, serial: 'DEV-1', brand: 'Google', model: 'Pixel', resolution: '1080x1920', status: 'online' }
    const wrapper = mountModal({ open: true, device, recordable: true, leaseToken: 'device-lease' })
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      refreshMirror: () => Promise<void>
      startRecording: () => void
      finishRecording: () => Promise<void>
    }
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
    await vm.finishRecording()

    expect(uiTargetMock).toHaveBeenCalledWith(1, { x: 200, y: 400 })
    expect(tapMock).toHaveBeenCalledWith(1, { x: 200, y: 400 }, 'device-lease')
    expect(wrapper.emitted('recorded')?.[0]?.[0]).toEqual([{
      action: 'click', name: '镜像点击',
      params: expect.objectContaining({ x: 200, y: 400, resourceId: 'com.example:id/login' }),
    }])
    wrapper.unmount()
  })

  it('auto-appends screen assertions when finishing recording and degrades cleanly if uiAnchors fails', async () => {
    const device = { id: 1, serial: 'DEV-1', brand: 'Google', model: 'Pixel', resolution: '1080x1920', status: 'online' }
    uiAnchorsMock.mockResolvedValueOnce({
      anchors: { text: '工作台', resourceId: 'com.example:id/home', packageName: 'com.example' },
    })
    const wrapper = mountModal({ open: true, device, recordable: true, leaseToken: 'device-lease' })
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      refreshMirror: () => Promise<void>
      startRecording: () => void
      finishRecording: () => Promise<void>
      autoAssert: boolean
    }
    await vm.refreshMirror()
    await flushPromises()
    const image = wrapper.find('.mirror-img')
    Object.defineProperty(image.element, 'naturalWidth', { value: 1080 })
    Object.defineProperty(image.element, 'naturalHeight', { value: 1920 })
    image.element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 540, height: 960, right: 540, bottom: 960 } as DOMRect)

    vm.startRecording()
    await image.trigger('mousedown', { clientX: 100, clientY: 200 })
    await image.trigger('mouseup', { clientX: 100, clientY: 200 })
    await flushPromises()
    await vm.finishRecording()

    expect(uiAnchorsMock).toHaveBeenCalledWith(1)
    expect(wrapper.emitted('recorded')?.[0]?.[0]).toEqual([
      expect.objectContaining({ action: 'click' }),
      { action: 'assert_element', name: '断言元素 com.example:id/home', params: { resourceId: 'com.example:id/home' } },
      { action: 'assert_text', name: '断言文本 工作台', params: { text: '工作台' } },
    ])
    wrapper.unmount()

    // 即使 uiAnchors 请求异常也不阻断保存录制步骤
    uiAnchorsMock.mockRejectedValueOnce(new Error('timeout'))
    const fallbackWrapper = mountModal({ open: true, device, recordable: true, leaseToken: 'device-lease' })
    await flushPromises()
    const fallbackVm = fallbackWrapper.vm as unknown as {
      refreshMirror: () => Promise<void>
      startRecording: () => void
      finishRecording: () => Promise<void>
    }
    await fallbackVm.refreshMirror()
    await flushPromises()
    const fallbackImg = fallbackWrapper.find('.mirror-img')
    Object.defineProperty(fallbackImg.element, 'naturalWidth', { value: 1080 })
    Object.defineProperty(fallbackImg.element, 'naturalHeight', { value: 1920 })
    fallbackImg.element.getBoundingClientRect = () =>
      ({ left: 0, top: 0, width: 540, height: 960, right: 540, bottom: 960 } as DOMRect)

    fallbackVm.startRecording()
    await fallbackImg.trigger('mousedown', { clientX: 50, clientY: 100 })
    await fallbackImg.trigger('mouseup', { clientX: 50, clientY: 100 })
    await flushPromises()
    await fallbackVm.finishRecording()

    expect(fallbackWrapper.emitted('recorded')?.[0]?.[0]).toEqual([expect.objectContaining({ action: 'click' })])
    fallbackWrapper.unmount()
  })

  it('picks assertions on screen without tapping device when pickAssertMode is enabled', async () => {
    const device = { id: 1, serial: 'DEV-1', brand: 'Google', model: 'Pixel', resolution: '1080x1920', status: 'online' }
    uiTargetMock.mockResolvedValueOnce({ target: { text: '登录成功', resourceId: 'com.example:id/welcome' } })
    const wrapper = mountModal({ open: true, device, recordable: true, leaseToken: 'device-lease' })
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      refreshMirror: () => Promise<void>
      startRecording: () => void
      finishRecording: () => Promise<void>
      autoAssert: boolean
    }
    await vm.refreshMirror()
    await flushPromises()
    const image = wrapper.find('.mirror-img')
    Object.defineProperty(image.element, 'naturalWidth', { value: 1080 })
    Object.defineProperty(image.element, 'naturalHeight', { value: 1920 })
    image.element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 540, height: 960, right: 540, bottom: 960 } as DOMRect)

    vm.autoAssert = false
    vm.startRecording()
    await wrapper.vm.$nextTick()
    await wrapper.find('.pick-assert-btn').trigger('click')
    await image.trigger('mousedown', { clientX: 120, clientY: 220 })
    await image.trigger('mouseup', { clientX: 120, clientY: 220 })
    await flushPromises()
    await vm.finishRecording()

    expect(tapMock).not.toHaveBeenCalled()
    expect(uiTargetMock).toHaveBeenCalledWith(1, { x: 240, y: 440 })
    expect(uiAnchorsMock).not.toHaveBeenCalled()
    expect(wrapper.emitted('recorded')?.[0]?.[0]).toEqual([
      { action: 'assert_text', name: '断言文本 登录成功', params: { text: '登录成功' } },
    ])
    wrapper.unmount()
  })

  it('keeps failed mirror actions out of the recorded draft', async () => {
    const device = { id: 1, serial: 'DEV-1', brand: 'Google', model: 'Pixel', resolution: '1080x1920', status: 'online' }
    tapMock.mockRejectedValueOnce(new Error('device disconnected'))
    const wrapper = mountModal({ open: true, device, recordable: true })
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      refreshMirror: () => Promise<void>
      startRecording: () => void
      finishRecording: () => Promise<void>
    }
    await vm.refreshMirror()
    await flushPromises()
    const image = wrapper.find('.mirror-img')
    image.element.getBoundingClientRect = () => ({ left: 0, top: 0, width: 540, height: 960, right: 540, bottom: 960 } as DOMRect)
    vm.startRecording()
    await image.trigger('mousedown', { clientX: 100, clientY: 200 })
    await image.trigger('mouseup', { clientX: 100, clientY: 200 })
    await flushPromises()
    await vm.finishRecording()

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
    expect(wrapper.find('.ant-modal-title').text()).toContain('rk3588')
    expect(wrapper.find('.header-status-tag').text()).toBe('在线')

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

    const wrapper = mountModal({ open: true, device, leaseToken: 'device-lease' })
    await flushPromises()

    const navButtons = wrapper.findAll('.nav-key-btn')
    // Click Home button (index 1, keycode 3)
    await navButtons[1].trigger('click')
    await flushPromises()

    expect(keyeventMock).toHaveBeenCalledWith(2, 3, 'device-lease')

    wrapper.unmount()
  })

  it('auto-acquires interactive lease when opened without leaseToken and releases on close', async () => {
    const device = {
      id: 5,
      serial: 'b01ac8cb',
      brand: 'OPPO',
      model: 'OPPO R11',
      resolution: '1080x1920',
      status: 'online',
    }

    const wrapper = mountModal({ open: true, device })
    await flushPromises()

    expect(acquireLeaseMock).toHaveBeenCalledTimes(1)
    expect(acquireLeaseMock).toHaveBeenCalledWith(5, {
      ttl_seconds: 90,
      owner_label: '投屏控制',
    })
    expect(wrapper.find('.ant-modal-title').text()).toContain('设备投屏 · OPPO R11')
    expect(wrapper.find('.header-lease-tag').text()).toContain('控制权已生效')

    const navButtons = wrapper.findAll('.nav-key-btn')
    await navButtons[0].trigger('click')
    await flushPromises()

    expect(keyeventMock).toHaveBeenCalledWith(5, 4, 'auto-test-lease')

    await wrapper.find('.modal-close').trigger('click')
    await flushPromises()

    expect(releaseLeaseMock).toHaveBeenCalledWith(5, 'auto-test-lease')
    wrapper.unmount()
  })

  it('shows the lease conflict reason inline instead of only a toast', async () => {
    const device = { id: 6, serial: 'DEV-6', brand: 'OPPO', model: 'OPPO R11', status: 'online' }
    // http 拦截器把 409 的 detail 作为字符串拒绝，而不是 axios 错误对象。
    acquireLeaseMock.mockRejectedValueOnce('设备已被“自动化用例执行”占用，预计 1 分 30 秒 后释放')

    const wrapper = mountModal({ open: true, device })
    await flushPromises()

    const alert = wrapper.find('.mirror-lease-alert')
    expect(alert.exists()).toBe(true)
    expect(alert.text()).toContain('自动化用例执行')
    expect(alert.text()).toContain('1 分 30 秒')
    expect(wrapper.find('.header-lease-tag').text()).toContain('只读模式')
    wrapper.unmount()
  })

  it('offers to take over the caller’s own leftover lease', async () => {
    const device = { id: 7, serial: 'DEV-7', brand: 'OPPO', model: 'OPPO R11', status: 'busy' }
    acquireLeaseMock.mockRejectedValueOnce('设备已被“android-case-editor”占用，预计 1 分 20 秒后释放')

    const wrapper = mountModal({ open: true, device })
    await flushPromises()

    const takeover = wrapper
      .findAll('.mirror-lease-alert button')
      .find((button) => button.text().includes('接管我自己的租约'))
    expect(takeover).toBeTruthy()

    await takeover!.trigger('click')
    await flushPromises()

    expect(acquireLeaseMock).toHaveBeenLastCalledWith(7, {
      ttl_seconds: 90,
      owner_label: '投屏控制',
      takeover_own: true,
    })
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

  it('shows a failed screenshot and retries only when requested', async () => {
    vi.useFakeTimers()
    const device = { id: 1, serial: 'DEV-1', status: 'online' }
    screenshotMock.mockRejectedValueOnce(new Error('unavailable'))
    const wrapper = mountModal({ open: true, device })
    const vm = wrapper.vm as unknown as { closeScrcpyStream: () => void; startMirrorPolling: () => void; refreshMirror: () => Promise<boolean>; retryScreenshot: () => Promise<void> }
    vm.closeScrcpyStream()
    vm.startMirrorPolling()
    await vm.refreshMirror()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[role="alert"]').text()).toContain('无法获取设备画面')
    await vi.advanceTimersByTimeAsync(2000)
    expect(screenshotMock).toHaveBeenCalledTimes(1)
    await vm.retryScreenshot()
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.find('.mirror-img').exists()).toBe(true)
    expect(screenshotMock).toHaveBeenCalledTimes(2)
    wrapper.unmount()
    vi.useRealTimers()
  })

  it('explains that the live stream needs a secure origin when WebCodecs is unavailable', async () => {
    vi.mocked(isWebCodecsSupported).mockReturnValue(false)
    const device = { id: 1, serial: 'DEV-1', brand: 'OPPO', model: 'OPPO R11', resolution: '1080x1920', status: 'online' }
    const wrapper = mountModal({ open: true, device, leaseToken: 'device-lease' })
    await flushPromises()
    const vm = wrapper.vm as unknown as { refreshMirror: () => Promise<void> }
    await vm.refreshMirror()
    await flushPromises()

    const pill = wrapper.find('.stream-status-pill')
    await vi.waitFor(() => expect(pill.text()).toContain('实时流需 HTTPS 或 localhost 访问'))
    expect(pill.text()).toContain('截图降级模式')
    wrapper.unmount()
  })

  it('sends a keepalive DELETE lease request on pagehide and skips duplicate unmount release', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)
    try {
      const device = { id: 9, serial: 'DEV-9', status: 'online' }
      const wrapper = mountModal({ open: true, device })
      await flushPromises()

      expect(acquireLeaseMock).toHaveBeenCalledTimes(1)
      window.dispatchEvent(new Event('pagehide'))

      expect(fetchMock).toHaveBeenCalledWith(
        '/api/v1/devices/9/lease',
        expect.objectContaining({
          method: 'DELETE',
          keepalive: true,
          credentials: 'include',
          body: JSON.stringify({ lease_token: 'auto-test-lease' }),
        }),
      )

      wrapper.unmount()
      expect(releaseLeaseMock).not.toHaveBeenCalled()
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('emits draft-captured when closing while recording steps, but not after explicit discard', async () => {
    const device = { id: 2, serial: 'DEV-DRAFT', brand: 'Pixel', model: '8', status: 'online' }
    const wrapper = mountModal({ open: true, device, recordable: true, leaseToken: 'lease-1' })
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      startRecording: () => void
      discardRecording: () => void
      handleClose: () => void
      recordedSteps: Array<{ action: string; name: string; params: Record<string, unknown> }>
    }

    vm.startRecording()
    vm.recordedSteps.push({ action: 'tap', name: '点击登录', params: { x: 10, y: 20 } })
    vm.handleClose()

    expect(wrapper.emitted('draft-captured')?.[0]?.[0]).toEqual([
      { action: 'tap', name: '点击登录', params: { x: 10, y: 20 } },
    ])
    expect(wrapper.emitted('draft-captured')?.[0]?.[1]).toEqual(device)

    vm.startRecording()
    vm.recordedSteps.push({ action: 'tap', name: '被丢弃步骤', params: { x: 1, y: 2 } })
    vm.discardRecording()
    vm.handleClose()

    expect(wrapper.emitted('draft-captured')).toHaveLength(1)
    wrapper.unmount()
  })

  it('masks sensitive quick text in recorded draft while sending plaintext to device and resets on discard', async () => {
    inputTextMock.mockResolvedValue({ ok: true })
    const device = { id: 2, serial: 'DEV-SEC', brand: 'Pixel', model: '8', status: 'online' }
    const wrapper = mountModal({ open: true, device, recordable: true, leaseToken: 'lease-sec' })
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      startRecording: () => void
      discardRecording: () => void
      recordedSteps: Array<{ action: string; name: string; params: Record<string, unknown> }>
    }

    vm.startRecording()
    const checkbox = wrapper.find('.mirror-sensitive-checkbox')
    const input = wrapper.find('.quick-input')
    expect(input.attributes('type')).toBe('text')

    await checkbox.setValue(true)
    expect(input.attributes('type')).toBe('password')

    await input.setValue('MySecretPwd!99')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(inputTextMock).toHaveBeenCalledWith(2, 'MySecretPwd!99', 'lease-sec')
    expect(vm.recordedSteps).toEqual([
      { action: 'input', name: '输入敏感值（请手动填写）', params: { text: '', sensitive: true } },
    ])

    vm.discardRecording()
    await wrapper.vm.$nextTick()
    expect((checkbox.element as HTMLInputElement).checked).toBe(false)
    expect(input.attributes('type')).toBe('text')
    wrapper.unmount()
  })
})
