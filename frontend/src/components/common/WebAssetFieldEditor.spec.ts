import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import WebAssetFieldEditor, { type WebAssetFieldKind } from './WebAssetFieldEditor.vue'

const { messageWarning } = vi.hoisted(() => ({ messageWarning: vi.fn() }))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({ message: { warning: messageWarning } }))
vi.mock('@ant-design/icons-vue', () => ({ MinusCircleOutlined: true, PlusOutlined: true }))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

function mountEditor(props: {
  kind: WebAssetFieldKind
  value?: string
  elements?: Array<{ id: number; name: string }>
  elementRefsText?: string
  disabled?: boolean
}) {
  return mount(WebAssetFieldEditor, {
    props,
    global: {
      stubs: {
        AAutoComplete: passthrough('AAutoComplete'),
        AButton: passthrough('AButton'),
        ACheckbox: passthrough('ACheckbox'),
        AInput: passthrough('AInput'),
        AInputNumber: passthrough('AInputNumber'),
        ASelect: passthrough('ASelect'),
        ASelectOption: passthrough('ASelectOption'),
        ATextarea: passthrough('ATextarea'),
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('WebAssetFieldEditor', () => {
  it('supports locator, element_refs, recorded actions with params, and ignore_regions', async () => {
    const refWrapper = mountEditor({
      kind: 'element_refs',
      value: '[]',
      elements: [{ id: 12, name: 'SubmitBtn' }],
    })
    await flushPromises()
    const refVm = refWrapper.vm as any
    refVm.addElementRef()
    refVm.elementRefRows[0].asset_id = 12
    refVm.onSelectElementRef(refVm.elementRefRows[0])
    let emitted = refWrapper.emitted('update:value')!
    expect(JSON.parse(emitted[emitted.length - 1][0] as string)).toEqual([{ asset_id: 12, alias: 'SubmitBtn' }])

    const actionWrapper = mountEditor({
      kind: 'actions',
      value: JSON.stringify([{ name: 'input_user', step: 'fill', alias: 'UserInput', params: { text: 'alice' } }]),
      elementRefsText: '[{"asset_id":1,"alias":"UserInput"}]',
    })
    await flushPromises()
    const actionVm = actionWrapper.vm as any
    expect(actionVm.actionRows[0].value).toBe('alice')
    actionVm.actionRows[0].value = 'bob'
    actionVm.emitActions()
    emitted = actionWrapper.emitted('update:value')!
    expect(JSON.parse(emitted[emitted.length - 1][0] as string)).toEqual([
      { name: 'input_user', step: 'fill', alias: 'UserInput', params: { text: 'bob' } },
    ])

    const regionWrapper = mountEditor({
      kind: 'ignore_regions',
      value: '[{"x":10,"y":20,"width":80,"height":30}]',
    })
    await flushPromises()
    expect((regionWrapper.vm as any).ignoreRegionRows[0]).toMatchObject({ mode: 'box', width: 80 })
  })

  it('allows switching to raw mode even when disabled and does not emit empty rows on add', async () => {
    const wrapper = mountEditor({
      kind: 'fallbacks',
      value: '[]',
      disabled: true,
    })
    await flushPromises()
    const vm = wrapper.vm as any
    vm.switchMode('raw')
    expect(vm.mode).toBe('raw')

    await wrapper.setProps({ disabled: false })
    vm.switchMode('visual')
    vm.addFallback()
    expect(wrapper.emitted('update:value')).toBeUndefined()
  })

  it('syncs cleanly when external props.value changes after a same-value visual emit', async () => {
    const wrapper = mountEditor({ kind: 'locator', value: '{"strategy":"css","value":"#old"}' })
    await flushPromises()
    const vm = wrapper.vm as any
    await wrapper.setProps({ value: '{"strategy":"xpath","value":"//button"}' })
    expect(vm.locatorRow.strategy).toBe('xpath')
    expect(vm.locatorRow.value).toBe('//button')
  })
})
