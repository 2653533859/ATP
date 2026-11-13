import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AndroidStepEditor from './AndroidStepEditor.vue'

const {
  packages,
  refreshPackages,
  screenshot,
  tap,
  uiTarget,
  uiAnchors,
  messageWarning,
  messageSuccess,
} = vi.hoisted(() => ({
  packages: vi.fn(),
  refreshPackages: vi.fn(),
  screenshot: vi.fn(),
  tap: vi.fn(),
  uiTarget: vi.fn(),
  uiAnchors: vi.fn(),
  messageWarning: vi.fn(),
  messageSuccess: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { warning: messageWarning, success: messageSuccess, error: vi.fn() },
}))
vi.mock('@/api', () => ({
  deviceApi: { packages, refreshPackages, screenshot, tap, uiTarget, uiAnchors },
}))

const draggableStub = defineComponent({
  name: 'draggable',
  props: ['modelValue'],
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        (props.modelValue as Array<Record<string, unknown>>).map((element, index) =>
          slots.item?.({ element, index }),
        ),
      )
  },
})

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const cardStub = defineComponent({
  name: 'ACard',
  setup: (_props, { slots }) => () =>
    h('div', { class: 'a-card-stub' }, [slots.title?.(), slots.extra?.(), slots.default?.()]),
})

const dropdownStub = defineComponent({
  name: 'ADropdown',
  setup: (_props, { slots }) => () => h('div', { class: 'dropdown-stub' }, [slots.default?.(), slots.overlay?.()]),
})

const menuStub = defineComponent({
  name: 'AMenu',
  emits: ['click'],
  setup: (_props, { slots, emit }) => () =>
    h(
      'div',
      { class: 'menu-stub' },
      slots.default?.().map((vnode) =>
        h(vnode, {
          onClick: () => emit('click', { key: vnode.key ?? (vnode.props as Record<string, unknown> | null)?.key }),
        }),
      ),
    ),
})

const radioGroupStub = defineComponent({
  name: 'ARadioGroup',
  props: ['value', 'disabled'],
  emits: ['update:value'],
  setup: (_props, { slots, emit }) => () =>
    h(
      'div',
      { class: 'radio-group-stub' },
      slots.default?.().map((vnode) => {
        const value = (vnode.props as Record<string, unknown> | null)?.value
        return h(vnode, {
          onClick: () => emit('update:value', value),
        })
      }),
    ),
})

const globalStubs = {
  draggable: draggableStub,
  AAutoComplete: passthrough('AAutoComplete'),
  AAlert: passthrough('AAlert'),
  AButton: defineComponent({
    name: 'AButton',
    emits: ['click'],
    setup: (_props, { slots, emit, attrs }) => () =>
      h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.()),
  }),
  ACard: cardStub,
  ADropdown: dropdownStub,
  AEmpty: passthrough('AEmpty'),
  AFormItem: passthrough('AFormItem'),
  AInput: passthrough('AInput'),
  AInputNumber: passthrough('AInputNumber'),
  AMenu: menuStub,
  AMenuItem: passthrough('AMenuItem'),
  ARadioButton: defineComponent({
    name: 'ARadioButton',
    props: ['value'],
    setup: (props, { slots }) => () =>
      h('button', { type: 'button', 'data-radio-value': props.value }, slots.default?.()),
  }),
  ARadioGroup: radioGroupStub,
  ARow: passthrough('ARow'),
  ACol: passthrough('ACol'),
  ASelect: passthrough('ASelect'),
  ASelectOption: passthrough('ASelectOption'),
  ASpace: passthrough('ASpace'),
  ASpin: passthrough('ASpin'),
  ATag: passthrough('ATag'),
}

function mountEditor(deviceId: number | null = 5) {
  return mount(AndroidStepEditor, {
    props: {
      modelValue: [{ action: 'start_app', name: '启动应用', params: { package: '' } }],
      deviceId,
    },
    global: { stubs: globalStubs },
  })
}

describe('AndroidStepEditor package suggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    packages.mockResolvedValue({
      device_id: 5,
      serial: '172.16.101.11:5555',
      current_package: 'com.hopesen.aiphytraining',
      current_activity: '.view.list.ExaminationListActivity',
      packages: ['com.hopesen.aiphytraining', 'com.mgtv.tv'],
      read_at: '2026-11-12T09:30:00Z',
      stale: false,
      source: 'refresh',
    })
  })

  it('合入当前选择设备的已安装包名，并标记前台应用', async () => {
    const wrapper = mountEditor(5)
    await flushPromises()

    expect(packages).toHaveBeenCalledWith(5)
    const options = wrapper.vm.packageOptions
    expect(options.map((option) => option.value)).toEqual(['com.hopesen.aiphytraining', 'com.mgtv.tv'])
    expect(options[0].label).toContain('case.android_editor.device_foreground_tag')
    wrapper.unmount()
  })

  it('未选择设备时不请求包名，读取失败时静默降级', async () => {
    const withoutDevice = mountEditor(null)
    await flushPromises()
    expect(packages).not.toHaveBeenCalled()
    withoutDevice.unmount()

    packages.mockRejectedValue(new Error('device offline'))
    const failed = mountEditor(5)
    await flushPromises()
    expect(failed.vm.devicePackages).toEqual([])
    expect(failed.find('.step-card').exists()).toBe(true)
    failed.unmount()
  })

  it('支持工具栏新增断言、按步骤插入断言及可视化点选/整屏采集断言', async () => {
    screenshot.mockResolvedValue(new Blob(['img'], { type: 'image/png' }))
    uiAnchors.mockResolvedValue({
      anchors: { text: '课程详情', resourceId: 'com.demo:id/course_title' },
    })
    uiTarget.mockResolvedValue({
      target: { text: '立即报名', resourceId: 'com.demo:id/enroll_btn' },
    })

    const wrapper = mountEditor(5)
    await flushPromises()

    await wrapper.find('.add-assert-text-btn').trigger('click')
    await wrapper.find('.add-assert-element-btn').trigger('click')
    let emitted = wrapper.emitted('update:modelValue') as Array<[Array<Record<string, unknown>>]>
    expect(emitted[0][0]).toHaveLength(2)
    expect(emitted[0][0][1]).toEqual({
      action: 'assert_text',
      name: 'case.android_editor.actions.assert_text',
      params: { text: '' },
    })
    expect(emitted[1][0][2]).toEqual({
      action: 'assert_element',
      name: 'case.android_editor.actions.assert_element',
      params: { resourceId: '' },
    })

    // 从第 1 步后方直接插入断言元素（位置 index + 1）
    const firstCardMenu = wrapper.findAll('.step-card')[0].findAll('.menu-stub > div')
    await firstCardMenu[1].trigger('click')
    emitted = wrapper.emitted('update:modelValue') as Array<[Array<Record<string, unknown>>]>
    const insertedList = emitted[emitted.length - 1][0]
    expect(insertedList[1]).toEqual({
      action: 'assert_element',
      name: 'case.android_editor.actions.assert_element',
      params: { resourceId: '' },
    })

    // 整屏采集当前屏断言
    await wrapper.find('.capture-screen-assert-btn').trigger('click')
    await flushPromises()
    expect(uiAnchors).toHaveBeenCalledWith(5)
    emitted = wrapper.emitted('update:modelValue') as Array<[Array<Record<string, unknown>>]>
    const afterAnchorCapture = emitted[emitted.length - 1][0]
    expect(afterAnchorCapture.slice(-2)).toEqual([
      {
        action: 'assert_element',
        name: '断言元素 com.demo:id/course_title',
        params: { resourceId: 'com.demo:id/course_title' },
      },
      {
        action: 'assert_text',
        name: '断言文本 课程详情',
        params: { text: '课程详情' },
      },
    ])

    // 切换为点选文本断言模式后点击截图，不触发真实 tap，仅添加 assert_text
    const originalCreateObjectUrl = URL.createObjectURL
    URL.createObjectURL = vi.fn(() => 'blob:mock-screen')
    try {
      await wrapper.setProps({ modelValue: [{ action: 'click', name: '点击', params: {} }] })
      await wrapper.vm.$nextTick()
      const screenVm = wrapper.vm as unknown as {
        refreshScreenshot: () => Promise<void>
      }
      await screenVm.refreshScreenshot()
      await flushPromises()

      const img = wrapper.find('.screen-canvas img').element as HTMLImageElement
      Object.defineProperty(img, 'naturalWidth', { value: 1080 })
      Object.defineProperty(img, 'naturalHeight', { value: 1920 })
      img.getBoundingClientRect = () =>
        ({ left: 0, top: 0, width: 540, height: 960, right: 540, bottom: 960 }) as DOMRect

      await wrapper.find('[data-radio-value="assert_text"]').trigger('click')
      const canvas = wrapper.find('.screen-canvas')
      canvas.element.dispatchEvent(new MouseEvent('pointerdown', { clientX: 100, clientY: 200, bubbles: true }))
      canvas.element.dispatchEvent(new MouseEvent('pointerup', { clientX: 100, clientY: 200, bubbles: true }))
      await flushPromises()

      expect(tap).not.toHaveBeenCalled()
      expect(uiTarget).toHaveBeenCalledWith(5, { x: 200, y: 400 })
      const latest = wrapper.emitted('update:modelValue')!
      expect(latest[latest.length - 1][0]).toEqual([
        { action: 'click', name: '点击', params: {} },
        { action: 'assert_text', name: '断言文本 立即报名', params: { text: '立即报名' } },
      ])
    } finally {
      URL.createObjectURL = originalCreateObjectUrl
    }

    wrapper.unmount()
  })
})
