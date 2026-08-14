import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import WebCaseDrawer from './WebCaseDrawer.vue'
import CaseDatasetBinding from '@/components/common/CaseDatasetBinding.vue'
import type { CaseSummaryItem } from '@/api'

const { caseCreate, caseGet, caseUpdate, assetList, pageObjectList, datasetList, versionList, warning, success } = vi.hoisted(() => ({
  caseCreate: vi.fn(),
  caseGet: vi.fn(),
  caseUpdate: vi.fn(),
  assetList: vi.fn(),
  pageObjectList: vi.fn(),
  datasetList: vi.fn(),
  versionList: vi.fn(),
  warning: vi.fn(),
  success: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: { warning, success, error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/api', () => ({
  caseApi: { create: caseCreate, get: caseGet, update: caseUpdate },
  datasetApi: { list: datasetList, listVersions: versionList },
  scriptApi: { get: vi.fn(), upload: vi.fn(), saveContent: vi.fn() },
  webAssetsApi: { listElements: assetList, listPageObjects: pageObjectList },
}))

vi.mock('@/components/common/LowcodeStepEditor.vue', () => ({
  default: defineComponent({
    name: 'LowcodeStepEditor',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    setup(_props, { emit }) {
      return () => h('button', {
        'data-test': 'add-web-step',
        onClick: () => emit('update:modelValue', [{
          action: 'goto',
          name: '打开登录页',
          params: { url: 'https://example.test/login' },
        }]),
      }, 'add web step')
    },
  }),
}))

vi.mock('@/components/common/WebRecorderModal.vue', () => ({ default: defineComponent({ name: 'WebRecorderModal', setup: () => () => h('div') }) }))
vi.mock('@/components/common/GeneratedScriptModal.vue', () => ({ default: defineComponent({ name: 'GeneratedScriptModal', setup: () => () => h('div') }) }))
vi.mock('@/components/common/MonacoEditor.vue', () => ({ default: defineComponent({ name: 'MonacoEditor', setup: () => () => h('div') }) }))

const passthrough = (name: string) => defineComponent({
  name,
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const buttonStub = defineComponent({
  name: 'AButton',
  props: ['disabled'],
  emits: ['click'],
  setup(props, { slots, emit }) {
    return () => h('button', {
      disabled: props.disabled,
      onClick: () => emit('click'),
    }, slots.default?.())
  },
})

const drawerStub = defineComponent({
  name: 'ADrawer',
  setup(_props, { slots }) {
    return () => h('section', [slots.default?.(), slots.footer?.()])
  },
})

const formStub = defineComponent({
  name: 'AForm',
  setup(_props, { slots, expose }) {
    expose({ validate: vi.fn().mockResolvedValue(undefined) })
    return () => h('form', slots.default?.())
  },
})

function mountDrawer(editCase: { id: number } | null = null) {
  return mount(WebCaseDrawer, {
    props: { open: true, moduleId: 7, projectId: 11, editCase: editCase as CaseSummaryItem | null },
    global: {
      stubs: {
        AButton: buttonStub,
        ACheckbox: passthrough('ACheckbox'),
        ADrawer: drawerStub,
        AForm: formStub,
        AFormItem: passthrough('AFormItem'),
        AAlert: passthrough('AAlert'),
        ACol: passthrough('ACol'),
        ADivider: passthrough('ADivider'),
        AInput: passthrough('AInput'),
        AInputNumber: passthrough('AInputNumber'),
        ARadioButton: passthrough('ARadioButton'),
        ARadioGroup: passthrough('ARadioGroup'),
        ARow: passthrough('ARow'),
        ASelect: passthrough('ASelect'),
        ASelectOption: passthrough('ASelectOption'),
        ASpace: passthrough('ASpace'),
        ASwitch: passthrough('ASwitch'),
        ATag: passthrough('ATag'),
        ATextarea: passthrough('ATextarea'),
        ATooltip: passthrough('ATooltip'),
        AUpload: passthrough('AUpload'),
        ASpin: passthrough('ASpin'),
        CheckCircleOutlined: true,
        CodeOutlined: true,
        UploadOutlined: true,
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  assetList.mockResolvedValue([])
  pageObjectList.mockResolvedValue([])
  datasetList.mockResolvedValue([])
  versionList.mockResolvedValue([
    { version: 3, row_count: 3 },
    { version: 2, row_count: 2 },
  ])
  caseCreate.mockResolvedValue({ id: 101 })
  caseUpdate.mockResolvedValue({})
})

describe('WebCaseDrawer low-code flow', () => {
  it('creates a web case with the steps emitted by the low-code editor', async () => {
    const wrapper = mountDrawer()
    await flushPromises()

    wrapper.findComponent(CaseDatasetBinding).vm.$emit('update:modelValue', {
      datasetId: 31,
      datasetVersion: 2,
      strictSchema: true,
      strategy: 'fixed_count',
      fixedCount: 3,
      seed: 7,
      maxIterations: 10,
      combinationFields: [],
      redactFields: ['token'],
    })

    await wrapper.find('[data-test="add-web-step"]').trigger('click')
    await wrapper.findAll('button').find((button) => button.text() === 'case.drawer.create_case')?.trigger('click')
    await flushPromises()

    expect(caseCreate).toHaveBeenCalledWith(expect.objectContaining({
      case_type: 'web',
      module_id: 7,
      dataset_id: 31,
      dataset_version: 2,
      config: expect.objectContaining({
        dataset_strict_schema: true,
        dataset_strategy: 'fixed_count',
        dataset_fixed_count: 3,
        dataset_seed: 7,
        dataset_max_iterations: 10,
        dataset_redact_fields: ['token'],
        browser: 'chromium',
        steps: [{
          action: 'goto',
          name: '打开登录页',
          params: { url: 'https://example.test/login' },
        }],
      }),
    }))
    expect(wrapper.emitted('saved')).toHaveLength(1)
    expect(warning).not.toHaveBeenCalled()
  })

  it('loads existing low-code steps and persists them when editing', async () => {
    caseGet.mockResolvedValue({
      id: 101,
      name: '登录冒烟',
      description: '',
      tags: [],
      priority: 'P1',
      case_level: 'smoke',
      config: {
        browser: 'firefox',
        headless: false,
        steps: [{ action: 'assert_text', name: '校验标题', params: { text: 'Welcome' } }],
      },
    })

    const wrapper = mountDrawer({ id: 101 })
    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'case.drawer.save_config')?.trigger('click')
    await flushPromises()

    expect(caseUpdate).toHaveBeenCalledWith(101, expect.objectContaining({
      priority: 'P1',
      case_level: 'smoke',
      config: expect.objectContaining({
        browser: 'firefox',
        headless: false,
        steps: [{ action: 'assert_text', name: '校验标题', params: { text: 'Welcome' } }],
      }),
    }))
    expect(wrapper.emitted('saved')).toHaveLength(1)
  })

  it('preserves a dataset binding when editing a web case', async () => {
    caseGet.mockResolvedValue({
      id: 101,
      name: 'dataset case',
      description: '',
      tags: [],
      priority: 'P1',
      case_level: 'smoke',
      dataset_id: 31,
      dataset_version: 2,
      config: { steps: [{ action: 'goto', name: 'open', params: { url: 'https://example.test' } }], dataset_strategy: 'random' },
    })
    const wrapper = mountDrawer({ id: 101 })
    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'case.drawer.save_config')?.trigger('click')
    await flushPromises()

    expect(caseUpdate).toHaveBeenCalledWith(101, expect.objectContaining({
      dataset_id: 31,
      dataset_version: 2,
      config: expect.objectContaining({ dataset_strategy: 'random' }),
    }))
  })
})
