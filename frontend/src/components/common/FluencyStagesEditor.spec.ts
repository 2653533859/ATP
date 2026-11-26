import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import FluencyStagesEditor from './FluencyStagesEditor.vue'

const { messageWarning } = vi.hoisted(() => ({ messageWarning: vi.fn() }))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({ message: { warning: messageWarning } }))
vi.mock('@ant-design/icons-vue', () => ({ MinusCircleOutlined: true, PlusOutlined: true }))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

function mountEditor(props: Record<string, unknown> = {}) {
  return mount(FluencyStagesEditor, {
    props,
    global: {
      stubs: {
        AButton: passthrough('AButton'),
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

describe('FluencyStagesEditor', () => {
  it('adds preset swipe/tap stages visually and emits backend-compatible stage JSON', async () => {
    const wrapper = mountEditor({ value: '' })
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.mode).toBe('visual')
    vm.addPreset('swipe_up')
    vm.addPreset('tap_center')

    const emitted = wrapper.emitted('update:value')!
    const parsed = JSON.parse(emitted[emitted.length - 1][0] as string)
    expect(parsed).toHaveLength(2)
    expect(parsed[0].action).toBe('swipe')
    expect(parsed[1].action).toBe('tap')
  })

  it('keeps malformed JSON in raw mode and warns on invalid visual switch', async () => {
    const wrapper = mountEditor({ value: '{bad' })
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.mode).toBe('raw')
    expect(vm.rawText).toBe('{bad')
    vm.switchMode('visual')
    expect(vm.mode).toBe('raw')
    expect(messageWarning).toHaveBeenCalledWith('fluency_editor.invalid_json_hint')
  })
})
