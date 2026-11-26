import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { API_BODY_TEMPLATES } from '@/utils/smartJson'
import SmartJsonEditor from './SmartJsonEditor.vue'

const { messageWarning, messageSuccess, messageInfo } = vi.hoisted(() => ({
  messageWarning: vi.fn(),
  messageSuccess: vi.fn(),
  messageInfo: vi.fn(),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({
  message: { warning: messageWarning, success: messageSuccess, info: messageInfo },
}))
vi.mock('@ant-design/icons-vue', () => ({
  PlusOutlined: true,
  MinusCircleOutlined: true,
  FormatPainterOutlined: true,
  ThunderboltOutlined: true,
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const inputStub = defineComponent({
  name: 'AInput',
  props: ['value', 'placeholder', 'disabled'],
  emits: ['update:value', 'change'],
  setup: (props, { emit }) => () => h('input', {
    value: props.value,
    placeholder: props.placeholder,
    disabled: props.disabled,
    onInput: (e: Event) => {
      const val = (e.target as HTMLInputElement).value
      emit('update:value', val)
      emit('change')
    },
  }),
})

function mountEditor(props: Record<string, unknown> = {}) {
  return mount(SmartJsonEditor, {
    props,
    global: {
      stubs: {
        AAutoComplete: inputStub,
        AButton: defineComponent({
          name: 'AButton',
          emits: ['click'],
          setup: (_p, { slots, emit }) => () => h('button', { type: 'button', onClick: () => emit('click') }, slots.default?.()),
        }),
        ADropdown: passthrough('ADropdown'),
        AInput: inputStub,
        AMenu: passthrough('AMenu'),
        AMenuDivider: passthrough('AMenuDivider'),
        AMenuItem: passthrough('AMenuItem'),
        APopover: passthrough('APopover'),
        ASelect: passthrough('ASelect'),
        ASelectOption: passthrough('ASelectOption'),
        ATextarea: defineComponent({
          name: 'ATextarea',
          props: ['value'],
          emits: ['update:value', 'change'],
          setup: (p, { emit }) => () => h('textarea', {
            value: p.value,
            onInput: (e: Event) => {
              const val = (e.target as HTMLTextAreaElement).value
              emit('update:value', val)
              emit('change')
            },
          }),
        }),
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('SmartJsonEditor', () => {
  it('renders visual form rows for valid JSON objects and emits typed JSON on edits', async () => {
    const wrapper = mountEditor({ value: '{"count": 2, "enabled": true}' })
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.mode).toBe('visual')
    expect(vm.rows).toEqual([
      { key: 'count', type: 'number', value: '2' },
      { key: 'enabled', type: 'boolean', value: 'true' },
    ])

    vm.addRow()
    vm.rows[2].key = 'tag'
    vm.rows[2].value = 'smoke'
    vm.handleRowsChange()

    const emitted = wrapper.emitted('update:value')
    expect(emitted).toBeTruthy()
    const latest = emitted![emitted!.length - 1][0] as string
    expect(JSON.parse(latest)).toEqual({ count: 2, enabled: true, tag: 'smoke' })
  })

  it('switches automatically to raw mode without mutating arrays, templates, or invalid JSON', async () => {
    const arrayWrapper = mountEditor({ value: '[{"id": 1}]' })
    expect((arrayWrapper.vm as any).mode).toBe('raw')
    expect((arrayWrapper.vm as any).rawText).toBe('[{"id": 1}]')

    ;(arrayWrapper.vm as any).switchMode('visual')
    expect((arrayWrapper.vm as any).mode).toBe('raw')
    expect(messageWarning).toHaveBeenCalledWith('smart_json.visual_unavailable_array')

    const tplWrapper = mountEditor({ value: '{"id": {{user_id}}}', allowTemplates: true })
    expect((tplWrapper.vm as any).mode).toBe('raw')
    ;(tplWrapper.vm as any).switchMode('visual')
    expect(messageWarning).toHaveBeenCalledWith('smart_json.visual_unavailable_template')

    const invalidWrapper = mountEditor({ value: '{broken' })
    expect((invalidWrapper.vm as any).mode).toBe('raw')
    expect((invalidWrapper.vm as any).rawText).toBe('{broken')
  })

  it('applies templates and formats raw JSON safely', async () => {
    const wrapper = mountEditor({ value: '', templates: API_BODY_TEMPLATES })
    const vm = wrapper.vm as any

    vm.handleSelectTemplate({ key: 'pagination' })
    const emitted = wrapper.emitted('update:value')!
    expect(JSON.parse(emitted[emitted.length - 1][0] as string)).toEqual({
      page: 1,
      page_size: 20,
      keyword: '',
    })

    vm.switchMode('raw')
    vm.rawText = '{"a":1}'
    vm.formatRaw()
    expect(vm.rawText).toBe('{\n  "a": 1\n}')
  })

  it('allows switching to raw mode in readonly mode, warns on duplicate keys, and syncs external changes', async () => {
    const wrapper = mountEditor({ value: '{}', disabled: true })
    await flushPromises()
    const vm = wrapper.vm as any

    vm.switchMode('raw')
    expect(vm.mode).toBe('raw')

    await wrapper.setProps({ disabled: false, value: '{"k":"1"}' })
    expect(vm.mode).toBe('visual')
    expect(vm.rows).toEqual([{ key: 'k', type: 'string', value: '1' }])

    // Clear with empty key emits same '{}' value, then external update must still sync
    vm.rows[0].key = ''
    vm.handleRowsChange()
    await wrapper.setProps({ value: '{"next": 42}' })
    expect(vm.rows).toEqual([{ key: 'next', type: 'number', value: '42' }])

    vm.addRow()
    vm.rows[1].key = 'next'
    expect(vm.duplicateKeys).toEqual(['next'])
  })

  it('inserts dynamic variable presets in both visual and raw modes', async () => {
    const wrapper = mountEditor({ value: '{}', showDynamicVars: true })
    await flushPromises()
    const vm = wrapper.vm as any

    vm.handleInsertDynamicVar({ key: 'uuid' })
    expect(vm.rows).toEqual([{ key: 'request_id', type: 'string', value: '{{$uuid}}' }])
    expect(messageSuccess).toHaveBeenCalledTimes(1)
    const emitted = wrapper.emitted('update:value')!
    expect(JSON.parse(emitted[emitted.length - 1][0] as string)).toEqual({ request_id: '{{$uuid}}' })

    vm.switchMode('raw')
    vm.handleInsertDynamicVar({ key: 'timestamp' })
    expect(messageSuccess).toHaveBeenCalledTimes(2)
    expect(JSON.parse(vm.rawText)).toEqual({
      request_id: '{{$uuid}}',
      timestamp: '{{$timestamp}}',
    })
  })

  it('groups schema/contract derived templates separately from built-in templates and applies them', async () => {
    const schemaTpl = {
      id: 'schema_asset_1',
      label: 'Schema · CreateOrder',
      preview: '{"order_no":"sample"}',
      value: JSON.stringify({ order_no: 'ORD_{{$random_str(6)}}', amount: 10 }, null, 2),
      group: 'schema' as const,
    }
    const wrapper = mountEditor({
      value: '{}',
      templates: [...API_BODY_TEMPLATES, schemaTpl],
    })
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.builtinTemplates.length).toBe(API_BODY_TEMPLATES.length)
    expect(vm.derivedTemplates).toEqual([schemaTpl])

    vm.handleSelectTemplate({ key: 'schema_asset_1' })
    const emitted = wrapper.emitted('update:value')!
    expect(JSON.parse(emitted[emitted.length - 1][0] as string)).toEqual({
      order_no: 'ORD_{{$random_str(6)}}',
      amount: 10,
    })
  })
})
