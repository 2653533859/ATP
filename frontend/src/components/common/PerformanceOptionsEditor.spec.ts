import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import PerformanceOptionsEditor from './PerformanceOptionsEditor.vue'

const { messageWarning } = vi.hoisted(() => ({ messageWarning: vi.fn() }))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({ message: { warning: messageWarning } }))
vi.mock('@/components/common/KvEditor.vue', () => ({
  default: defineComponent({ name: 'KvEditor', setup: () => () => h('div', 'kv') }),
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

function mountEditor(props: Record<string, unknown> = {}) {
  return mount(PerformanceOptionsEditor, {
    props,
    global: {
      stubs: {
        ACol: passthrough('ACol'),
        AInput: passthrough('AInput'),
        AInputNumber: passthrough('AInputNumber'),
        ARow: passthrough('ARow'),
        ATextarea: passthrough('ATextarea'),
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('PerformanceOptionsEditor', () => {
  it('loads JSON options into visual fields and emits merged JSON preserving extra keys', async () => {
    const wrapper = mountEditor({
      value: JSON.stringify({ vus: 15, duration: '30s', atp_scenario: { steps: [] } }),
      executor: 'k6',
    })
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.mode).toBe('visual')
    expect(vm.form.vus).toBe(15)
    expect(vm.form.duration).toBe('30s')
    expect(vm.form.extraKeys).toEqual(['atp_scenario'])

    vm.form.vus = 50
    vm.form.max_p95_ms = 400
    vm.syncFormToRaw()

    const emitted = wrapper.emitted('update:value')!
    expect(JSON.parse(emitted[emitted.length - 1][0] as string)).toEqual({
      atp_scenario: { steps: [] },
      vus: 50,
      duration: '30s',
      thresholds: { max_p95_ms: 400 },
    })
  })

  it('stays in raw mode without mutating malformed JSON', async () => {
    const wrapper = mountEditor({ value: '{bad json' })
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.mode).toBe('raw')
    expect(vm.rawText).toBe('{bad json')

    vm.switchMode('visual')
    expect(vm.mode).toBe('raw')
    expect(messageWarning).toHaveBeenCalledWith('perf_options_editor.invalid_json_hint')
  })

  it('converts vus/duration keys automatically when switching executor', async () => {
    const wrapper = mountEditor({
      value: JSON.stringify({ vus: 25, duration: '45s' }),
      executor: 'k6',
    })
    await flushPromises()

    await wrapper.setProps({ executor: 'locust' })
    const emitted = wrapper.emitted('update:value')!
    expect(JSON.parse(emitted[emitted.length - 1][0] as string)).toEqual({
      users: 25,
      run_time: '45s',
    })
  })
})
