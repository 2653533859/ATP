import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import KvEditor from './KvEditor.vue'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const inputStub = (className: string) =>
  defineComponent({
    name: className,
    props: ['value', 'placeholder'],
    emits: ['update:value', 'change'],
    setup(props, { emit }) {
      return () =>
        h('input', {
          class: className,
          value: props.value ?? '',
          placeholder: props.placeholder,
          onInput: (e: Event) => {
            const next = (e.target as HTMLInputElement).value
            emit('update:value', next)
            emit('change', next)
          },
        })
    },
  })

const buttonStub = defineComponent({
  name: 'AButton',
  emits: ['click'],
  setup: (_props, { slots, emit, attrs }) => () =>
    h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.()),
})

describe('KvEditor', () => {
  it('keeps value-first input and blank rows intact when parent value prop syncs', async () => {
    const parentValue = { existing: '1' }
    const wrapper = mount(KvEditor, {
      props: { value: parentValue, presetKind: 'none' },
      global: {
        stubs: {
          AAutoComplete: inputStub('kv-input'),
          AInput: inputStub('kv-input'),
          AButton: buttonStub,
          ADropdown: passthrough('ADropdown'),
          AMenu: passthrough('AMenu'),
          AMenuItem: passthrough('AMenuItem'),
          PlusOutlined: true,
          DeleteOutlined: true,
          ThunderboltOutlined: true,
          DownOutlined: true,
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      rows: Array<{ key: string; value: string }>
      addRow: () => void
    }

    // Add two blank rows and verify parent watcher does not collapse them
    vm.addRow()
    vm.addRow()
    await flushPromises()
    expect(vm.rows).toHaveLength(3)

    // Enter value before key on row 1 through DOM input event
    let inputs = wrapper.findAll('input.kv-input')
    await inputs[3].setValue('value-first')
    await wrapper.setProps({ value: { ...parentValue } })
    await flushPromises()

    expect(vm.rows[1].value).toBe('value-first')
    expect(vm.rows).toHaveLength(3)

    // Complete key on row 1 and verify update:value emits both pairs
    inputs = wrapper.findAll('input.kv-input')
    await inputs[2].setValue('Authorization')
    await flushPromises()

    const emitted = wrapper.emitted('update:value')
    expect(emitted).toBeTruthy()
    expect(emitted![emitted!.length - 1]?.[0]).toEqual({ existing: '1', Authorization: 'value-first' })
    wrapper.unmount()
  })
})
