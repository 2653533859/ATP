import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LowcodeStepEditor from './LowcodeStepEditor.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { warning: vi.fn(), success: vi.fn(), error: vi.fn() },
}))
vi.mock('@/api', () => ({
  environmentApi: { list: vi.fn().mockResolvedValue([]), getVariables: vi.fn().mockResolvedValue([]) },
  webAssetsApi: { listElements: vi.fn().mockResolvedValue([]), listPageObjects: vi.fn().mockResolvedValue([]) },
  webFilesApi: { upload: vi.fn() },
  webVisualApi: { listBaselines: vi.fn().mockResolvedValue([]) },
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

const globalStubs = {
  draggable: draggableStub,
  VariableReferenceInput: passthrough('VariableReferenceInput'),
  AButton: defineComponent({
    name: 'AButton',
    emits: ['click'],
    setup: (_props, { slots, emit, attrs }) => () =>
      h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.()),
  }),
  ACard: defineComponent({
    name: 'ACard',
    setup: (_props, { slots, attrs }) => () =>
      h('div', { class: attrs.class }, [slots.title?.(), slots.default?.()]),
  }),
  ADropdown: defineComponent({
    name: 'ADropdown',
    setup: (_props, { slots }) => () => h('div', { class: 'dropdown-stub' }, [slots.default?.(), slots.overlay?.()]),
  }),
  AMenu: defineComponent({
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
  }),
  AMenuItem: passthrough('AMenuItem'),
  AEmpty: passthrough('AEmpty'),
  AFormItem: passthrough('AFormItem'),
  AInput: passthrough('AInput'),
  AInputNumber: passthrough('AInputNumber'),
  ARow: passthrough('ARow'),
  ACol: passthrough('ACol'),
  ASelect: passthrough('ASelect'),
  ASelectOption: passthrough('ASelectOption'),
  ATag: passthrough('ATag'),
  ATooltip: passthrough('ATooltip'),
  AUpload: passthrough('AUpload'),
}

describe('LowcodeStepEditor assertions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('supports adding assertions from toolbar and inserting after any step with selector carry-over', async () => {
    const wrapper = mount(LowcodeStepEditor, {
      props: {
        projectId: 1,
        modelValue: [
          {
            action: 'fill',
            name: '输入用户名',
            params: { selector: '#username', value: 'alice', element_asset_id: 12 },
          },
          {
            action: 'click',
            name: '点击登录',
            params: { selector: 'button[type=submit]' },
          },
        ],
      },
      global: { stubs: globalStubs },
    })
    await flushPromises()

    await wrapper.find('.add-assert-text-btn').trigger('click')
    await wrapper.find('.add-assert-visible-btn').trigger('click')

    let emitted = wrapper.emitted('update:modelValue') as Array<[Array<Record<string, unknown>>]>
    expect(emitted[0][0][2]).toEqual({
      action: 'assert_text',
      name: 'case.lowcode_editor.actions.assert_text',
      params: { text: '' },
    })
    expect(emitted[1][0][3]).toEqual({
      action: 'assert_visible',
      name: 'case.lowcode_editor.actions.assert_visible',
      params: { selector: '' },
    })

    // 在第 1 个 fill 步骤后插入 assert_visible，自动带入 selector 和 element_asset_id
    const firstCardMenu = wrapper.findAll('.step-card')[0].findAll('.menu-stub > div')
    await firstCardMenu[1].trigger('click')
    emitted = wrapper.emitted('update:modelValue') as Array<[Array<Record<string, unknown>>]>
    const afterInsert = emitted[emitted.length - 1][0]
    expect(afterInsert[1]).toEqual({
      action: 'assert_visible',
      name: 'case.lowcode_editor.actions.assert_visible',
      params: { selector: '#username', element_asset_id: 12 },
    })

    // 断言步骤卡片带高亮标识 class
    expect(wrapper.findAll('.step-card.is-assertion').length).toBeGreaterThanOrEqual(3)
    wrapper.unmount()
  })
})
