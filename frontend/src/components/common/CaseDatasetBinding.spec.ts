import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CaseDatasetBinding from './CaseDatasetBinding.vue'

const { datasetList, versionList } = vi.hoisted(() => ({
  datasetList: vi.fn(),
  versionList: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/api', () => ({
  datasetApi: { list: datasetList, listVersions: versionList },
}))

const passthrough = (name: string) => defineComponent({
  name,
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const selectStub = defineComponent({
  name: 'ASelect',
  inheritAttrs: false,
  props: {
    value: { type: [String, Number], default: undefined },
    loading: { type: Boolean, default: false },
    options: { type: Array, default: () => [] },
  },
  emits: ['change', 'update:value'],
  setup(props, { attrs, emit }) {
    return () => h('select', {
      ...attrs,
      'data-loading': String(props.loading),
      value: props.value == null ? '' : String(props.value),
      onChange: (event: Event) => emit('change', (event.target as HTMLSelectElement).value),
    })
  },
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((next) => { resolve = next })
  return { promise, resolve }
}

function mountBinding(projectId: number | null, datasetId: number | null = null) {
  return mount(CaseDatasetBinding, {
    props: {
      projectId,
      modelValue: {
        datasetId,
        datasetVersion: datasetId == null ? null : 1,
        strictSchema: false,
        strategy: 'sequential',
        fixedCount: null,
        seed: null,
        maxIterations: 1000,
        combinationFields: [],
        redactFields: [],
      },
    },
    global: {
      stubs: {
        ACheckbox: passthrough('ACheckbox'),
        ACol: passthrough('ACol'),
        ADivider: passthrough('ADivider'),
        AFormItem: passthrough('AFormItem'),
        AInputNumber: passthrough('AInputNumber'),
        ARow: passthrough('ARow'),
        ASelect: selectStub,
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  datasetList.mockResolvedValue([])
  versionList.mockResolvedValue([])
})

describe('CaseDatasetBinding request lifecycle', () => {
  it('clears dataset loading when the project is removed during an in-flight request', async () => {
    const request = deferred<[]>()
    datasetList.mockReturnValue(request.promise)
    const wrapper = mountBinding(11)
    await nextTick()
    expect(wrapper.get('[data-test="dataset-select"]').attributes('data-loading')).toBe('true')

    await wrapper.setProps({ projectId: null })
    await nextTick()
    expect(wrapper.get('[data-test="dataset-select"]').attributes('data-loading')).toBe('false')

    request.resolve([])
    await flushPromises()
    wrapper.unmount()
  })

  it('clears version loading when the dataset binding is removed during an in-flight request', async () => {
    const request = deferred<[]>()
    versionList.mockReturnValue(request.promise)
    const wrapper = mountBinding(11, 31)
    await nextTick()
    expect(wrapper.get('[data-test="dataset-version-select"]').attributes('data-loading')).toBe('true')

    await wrapper.setProps({
      modelValue: {
        datasetId: null,
        datasetVersion: null,
        strictSchema: false,
        strategy: 'sequential',
        fixedCount: null,
        seed: null,
        maxIterations: 1000,
        combinationFields: [],
        redactFields: [],
      },
    })
    await nextTick()
    expect((wrapper.vm as unknown as { versionsLoading: boolean }).versionsLoading).toBe(false)

    request.resolve([])
    await flushPromises()
    wrapper.unmount()
  })
})
