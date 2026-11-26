import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import FixtureActionsEditor from './FixtureActionsEditor.vue'

const { messageWarning } = vi.hoisted(() => ({ messageWarning: vi.fn() }))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({ message: { warning: messageWarning } }))
vi.mock('@ant-design/icons-vue', () => ({ MinusCircleOutlined: true, PlusOutlined: true }))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

function mountEditor(props: Record<string, unknown> = {}) {
  return mount(FixtureActionsEditor, {
    props,
    global: {
      stubs: {
        AButton: passthrough('AButton'),
        AInput: passthrough('AInput'),
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

describe('FixtureActionsEditor', () => {
  it('loads valid fixture actions visually and emits updated JSON array', async () => {
    const wrapper = mountEditor({
      value: JSON.stringify([{ action: 'set_variable', variable: 'token', value: 'demo' }]),
    })
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.mode).toBe('visual')
    expect(vm.rows).toHaveLength(1)

    vm.addRow()
    expect(wrapper.emitted('update:value')).toBeUndefined()
    vm.rows[1].action = 'delete_variable'
    vm.rows[1].variable = 'token'
    vm.emitRows()

    const emitted = wrapper.emitted('update:value')!
    expect(JSON.parse(emitted[emitted.length - 1][0] as string)).toEqual([
      { action: 'set_variable', variable: 'token', value: 'demo' },
      { action: 'delete_variable', variable: 'token' },
    ])
  })

  it('keeps malformed JSON in raw mode and blocks broken visual switch', async () => {
    const wrapper = mountEditor({ value: '{bad' })
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.mode).toBe('raw')
    expect(vm.rawText).toBe('{bad')
    vm.switchMode('visual')
    expect(vm.mode).toBe('raw')
    expect(messageWarning).toHaveBeenCalledWith('fixture_editor.invalid_json_hint')
  })
})
