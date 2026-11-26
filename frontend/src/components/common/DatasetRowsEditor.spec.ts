import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DatasetRowsEditor from './DatasetRowsEditor.vue'

const { messageWarning, messageSuccess } = vi.hoisted(() => ({
  messageWarning: vi.fn(),
  messageSuccess: vi.fn(),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({ message: { warning: messageWarning, success: messageSuccess } }))
vi.mock('@ant-design/icons-vue', () => ({ DeleteOutlined: true, PlusOutlined: true }))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

function mountEditor(props: Record<string, unknown> = {}) {
  return mount(DatasetRowsEditor, {
    props,
    global: {
      stubs: {
        AButton: passthrough('AButton'),
        AInput: passthrough('AInput'),
        ATextarea: passthrough('ATextarea'),
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('DatasetRowsEditor', () => {
  it('supports adding columns, adding rows, editing cells, and pasting Excel/CSV rows', async () => {
    const wrapper = mountEditor({
      value: '[{"username":"alice","age":20}]',
      schemaFields: [{ name: 'username', type: 'string' }, { name: 'age', type: 'integer' }],
    })
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.mode).toBe('table')
    expect(vm.columns).toEqual(['username', 'age'])

    vm.updateCell(0, 'age', '25')
    let emitted = wrapper.emitted('update:value')!
    expect(JSON.parse(emitted[emitted.length - 1][0] as string)).toEqual([{ username: 'alice', age: 25 }])

    vm.newColumnName = 'role'
    vm.addColumn()
    expect(vm.columns).toEqual(['username', 'age', 'role'])

    vm.pasteText = 'username\tage\nbob\t31'
    vm.importPastedRows(true)
    emitted = wrapper.emitted('update:value')!
    expect(JSON.parse(emitted[emitted.length - 1][0] as string)).toEqual([
      { username: 'alice', age: 25, role: '' },
      { username: 'bob', age: 31 },
    ])
    expect(messageSuccess).toHaveBeenCalledWith('dataset_table_editor.paste_success')
  })

  it('keeps malformed JSON in raw mode and prevents broken table switching', async () => {
    const wrapper = mountEditor({ value: '{broken' })
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.mode).toBe('raw')
    expect(vm.rawText).toBe('{broken')
    vm.switchMode('table')
    expect(vm.mode).toBe('raw')
    expect(messageWarning).toHaveBeenCalledWith('dataset_table_editor.invalid_json_hint')
  })

  it('resets temporary columns and paste box when switching to another dataset', async () => {
    const wrapper = mountEditor({ value: '[{"a":1}]' })
    await flushPromises()
    const vm = wrapper.vm as any

    vm.newColumnName = 'temp_col'
    vm.addColumn()
    vm.pasteOpen = true
    vm.pasteText = 'x\n1'
    expect(vm.columns).toEqual(['a', 'temp_col'])

    await wrapper.setProps({ value: '[{"b":2}]' })
    expect(vm.columns).toEqual(['b'])
    expect(vm.pasteOpen).toBe(false)
    expect(vm.pasteText).toBe('')
  })
})
