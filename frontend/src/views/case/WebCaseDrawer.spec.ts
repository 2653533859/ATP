import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import WebCaseDrawer from './WebCaseDrawer.vue'
import CaseDatasetBinding from '@/components/common/CaseDatasetBinding.vue'
import type { CaseSummaryItem } from '@/api'

const {
  caseCreate,
  caseGet,
  caseUpdate,
  assetList,
  pageObjectList,
  datasetList,
  recordingRecordCreate,
  recordingRecordUpdate,
  versionList,
  warning,
  success,
} = vi.hoisted(() => ({
  caseCreate: vi.fn(),
  caseGet: vi.fn(),
  caseUpdate: vi.fn(),
  assetList: vi.fn(),
  pageObjectList: vi.fn(),
  datasetList: vi.fn(),
  recordingRecordCreate: vi.fn(),
  recordingRecordUpdate: vi.fn(),
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
  recordingRecordApi: { create: recordingRecordCreate, update: recordingRecordUpdate },
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

vi.mock('@/components/common/RecordingHistoryDrawer.vue', () => ({
  default: defineComponent({
    name: 'RecordingHistoryDrawer',
    props: ['open'],
    emits: ['update:open', 'restore'],
    setup(_props, { emit }) {
      return () =>
        h(
          'button',
          {
            'data-test': 'import-web-history',
            onClick: () =>
              emit('restore', {
                id: 99,
                project_id: 11,
                owner_id: 1,
                kind: 'web',
                source: 'workbench',
                session_id: 'sess-99',
                title: '导入的登录草稿',
                status: 'draft',
                target_url: 'https://example.test/login',
                browser: 'chromium',
                case_id: null,
                steps: [
                  { action: 'goto', name: '打开登录页', params: { url: 'https://example.test/login' } },
                  { action: 'assert_text_contains', name: '断言标题', params: { expected: '登录' } },
                ],
                asset_ids: [15],
                steps_count: 2,
                assertion_count: 1,
                artifacts: {},
                summary: {},
                created_at: '',
                updated_at: '',
              }),
          },
          'import web history',
        )
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

function mountDrawer(editCase: { id: number } | null = null, draft: Record<string, unknown> = {}) {
  return mount(WebCaseDrawer, {
    props: { open: true, moduleId: 7, projectId: 11, editCase: editCase as CaseSummaryItem | null, ...draft },
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
        HistoryOutlined: true,
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
  localStorage.clear()
  recordingRecordCreate.mockResolvedValue({ id: 901 })
  recordingRecordUpdate.mockResolvedValue({ id: 901 })
})

describe('WebCaseDrawer low-code flow', () => {
  it('hydrates a recorded draft into a new web case', async () => {
    const wrapper = mountDrawer(null, {
      initialName: '录制登录流程',
      initialDescription: '由浏览器录制生成',
      initialSteps: [{ action: 'goto', name: '打开登录页', params: { url: 'https://example.test/login' } }],
    })
    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'case.drawer.create_case')?.trigger('click')
    await flushPromises()

    expect(caseCreate).toHaveBeenCalledWith(expect.objectContaining({
      name: '录制登录流程',
      description: '由浏览器录制生成',
      config: expect.objectContaining({
        steps: [{ action: 'goto', name: '打开登录页', params: { url: 'https://example.test/login' } }],
      }),
    }))
  })

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

  it('imports steps from RecordingHistoryDrawer and marks the linked record saved on case creation', async () => {
    const wrapper = mountDrawer(null)
    await flushPromises()

    await wrapper.get('[data-test="import-web-history"]').trigger('click')
    await flushPromises()

    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('case.drawer.create_case'))
    await saveBtn?.trigger('click')
    await flushPromises()

    expect(caseCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        name: '导入的登录草稿',
        config: expect.objectContaining({
          steps: expect.arrayContaining([
            expect.objectContaining({ action: 'goto' }),
            expect.objectContaining({ action: 'assert_text_contains' }),
          ]),
        }),
      }),
    )
    expect(recordingRecordUpdate).toHaveBeenCalledWith(99, { status: 'saved', case_id: 101 })
  })

  it('preserves unsaved steps as a backend and local draft when closing without saving', async () => {
    const wrapper = mountDrawer(null)
    await flushPromises()

    await wrapper.get('[data-test="add-web-step"]').trigger('click')
    await flushPromises()

    const cancelBtn = wrapper.findAll('button').find((b) => b.text().includes('common.cancel'))
    await cancelBtn?.trigger('click')
    await flushPromises()

    expect(caseCreate).not.toHaveBeenCalled()
    expect(recordingRecordCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        project_id: 11,
        kind: 'web',
        source: 'case_drawer',
        status: 'draft',
        steps: [expect.objectContaining({ action: 'goto' })],
      }),
    )
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('imports a saved case-linked history record without mutating or hijacking it on cancel, edit+close, or save', async () => {
    const savedRecord = {
      id: 555,
      project_id: 11,
      kind: 'web',
      source: 'workbench',
      session_id: 'saved-555',
      title: '已保存历史录制',
      status: 'saved',
      target_url: 'https://example.test/home',
      browser: 'chromium',
      case_id: 42,
      steps: [
        { action: 'goto', name: '打开首页', params: { url: 'https://example.test/home' } },
        { action: 'assert_text_contains', name: '断言首页', params: { expected: '首页' } },
      ],
      asset_ids: [15],
      steps_count: 2,
      assertion_count: 1,
      artifacts: {},
      summary: {},
      created_at: '',
      updated_at: '',
    }

    const wrapper1 = mountDrawer(null)
    await flushPromises()
    wrapper1.findComponent({ name: 'RecordingHistoryDrawer' }).vm.$emit('restore', savedRecord)
    await flushPromises()

    const cancelBtn1 = wrapper1.findAll('button').find((b) => b.text().includes('common.cancel'))
    await cancelBtn1?.trigger('click')
    await flushPromises()
    expect(recordingRecordUpdate).not.toHaveBeenCalled()
    expect(recordingRecordCreate).not.toHaveBeenCalled()

    await wrapper1.get('[data-test="add-web-step"]').trigger('click')
    await cancelBtn1?.trigger('click')
    await flushPromises()
    expect(recordingRecordUpdate).not.toHaveBeenCalled()
    expect(recordingRecordCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        project_id: 11,
        kind: 'web',
        status: 'draft',
      }),
    )
    wrapper1.unmount()

    vi.clearAllMocks()
    const wrapper2 = mountDrawer(null)
    await flushPromises()
    wrapper2.findComponent({ name: 'RecordingHistoryDrawer' }).vm.$emit('restore', savedRecord)
    await flushPromises()

    const createBtn = wrapper2.findAll('button').find((b) => b.text() === 'case.drawer.create_case')
    await createBtn?.trigger('click')
    await flushPromises()
    expect(caseCreate).toHaveBeenCalled()
    expect(recordingRecordUpdate).not.toHaveBeenCalled()
    wrapper2.unmount()
  })
})
