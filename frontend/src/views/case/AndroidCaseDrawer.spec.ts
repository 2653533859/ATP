import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AndroidCaseDrawer from './AndroidCaseDrawer.vue'
import CaseDatasetBinding from '@/components/common/CaseDatasetBinding.vue'

const { caseCreate, caseGet, caseUpdate, deviceList, apkList, datasetList, versionList } = vi.hoisted(() => ({
  caseCreate: vi.fn(),
  caseGet: vi.fn(),
  caseUpdate: vi.fn(),
  deviceList: vi.fn(),
  apkList: vi.fn(),
  datasetList: vi.fn(),
  versionList: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {}, query: {} }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('ant-design-vue', () => ({
  message: { warning: vi.fn(), success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/api', () => ({
  apkApi: { list: apkList },
  caseApi: { create: caseCreate, get: caseGet, update: caseUpdate },
  deviceApi: { list: deviceList },
  datasetApi: { list: datasetList, listVersions: versionList },
  scriptApi: { get: vi.fn(), upload: vi.fn(), saveContent: vi.fn() },
}))

vi.mock('@/components/common/AndroidStepEditor.vue', () => ({
  default: defineComponent({
    name: 'AndroidStepEditor',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    setup(_props, { emit }) {
      return () => h('button', {
        'data-test': 'add-android-step',
        onClick: () => emit('update:modelValue', [{
          action: 'start_app',
          name: '启动应用',
          params: { package: 'com.example.app' },
        }]),
      }, 'add android step')
    },
  }),
}))

vi.mock('@/components/case/CaseStepEditor.vue', () => ({
  default: defineComponent({ name: 'CaseStepEditor', setup: () => () => h('div') }),
}))
vi.mock('@/components/common/GeneratedScriptModal.vue', () => ({ default: defineComponent({ name: 'GeneratedScriptModal', setup: () => () => h('div') }) }))
vi.mock('@/components/common/MonacoEditor.vue', () => ({ default: defineComponent({ name: 'MonacoEditor', setup: () => () => h('div') }) }))

vi.mock('@/utils/androidStandardSteps', () => ({
  buildAndroidStandardSteps: () => [{
    step_order: 1,
    action: 'start_app',
    description: '启动应用',
    expected_result: '应用已启动',
  }],
}))

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
  return mount(AndroidCaseDrawer, {
    props: { open: true, moduleId: 7, projectId: 11, editCase },
    global: {
      stubs: {
        AButton: buttonStub,
        ACheckbox: passthrough('ACheckbox'),
        ADrawer: drawerStub,
        AForm: formStub,
        AFormItem: passthrough('AFormItem'),
        AAlert: passthrough('AAlert'),
        ABadge: passthrough('ABadge'),
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
        ASpin: passthrough('ASpin'),
        ASwitch: passthrough('ASwitch'),
        ATag: passthrough('ATag'),
        ATextarea: passthrough('ATextarea'),
        AUpload: passthrough('AUpload'),
        CheckCircleOutlined: true,
        CodeOutlined: true,
        UploadOutlined: true,
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  deviceList.mockResolvedValue([])
  apkList.mockResolvedValue([])
  datasetList.mockResolvedValue([])
  versionList.mockResolvedValue([
    { version: 3, row_count: 3 },
    { version: 2, row_count: 2 },
  ])
  caseCreate.mockResolvedValue({ id: 201 })
  caseUpdate.mockResolvedValue({})
})

describe('AndroidCaseDrawer low-code flow', () => {
  it('creates an Android case with low-code and generated standard steps', async () => {
    const wrapper = mountDrawer()
    await flushPromises()

    wrapper.findComponent(CaseDatasetBinding).vm.$emit('update:modelValue', {
      datasetId: 41,
      datasetVersion: 3,
      strictSchema: false,
      strategy: 'sequential',
      fixedCount: null,
      seed: null,
      maxIterations: 1000,
      combinationFields: [],
      redactFields: [],
    })

    await wrapper.find('[data-test="add-android-step"]').trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'case.drawer.create_case')?.trigger('click')
    await flushPromises()

    expect(caseCreate).toHaveBeenCalledWith(expect.objectContaining({
      case_type: 'android',
      module_id: 7,
      dataset_id: 41,
      dataset_version: 3,
      steps: [{
        step_order: 1,
        action: 'start_app',
        description: '启动应用',
        expected_result: '应用已启动',
      }],
      config: expect.objectContaining({
        dataset_strategy: 'sequential',
        steps: [{
          action: 'start_app',
          name: '启动应用',
          params: { package: 'com.example.app' },
        }],
      }),
    }))
    expect(wrapper.emitted('saved')).toHaveLength(1)
  })

  it('preserves a dataset binding when editing an Android case', async () => {
    caseGet.mockResolvedValue({
      id: 201,
      name: 'dataset case',
      summary: 'dataset case',
      description: '',
      tags: [],
      priority: 'P1',
      case_level: 'smoke',
      automation_status: 'auto',
      preconditions: [],
      postconditions: [],
      steps: [{ step_order: 1, action: 'start_app', description: 'start', expected_result: 'started' }],
      dataset_id: 41,
      dataset_version: 3,
      config: {
        steps: [{ action: 'start_app', name: 'start', params: { package: 'com.example.app' } }],
        dataset_strategy: 'pairwise',
      },
    })
    const wrapper = mountDrawer({ id: 201 })
    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'case.drawer.save_config')?.trigger('click')
    await flushPromises()

    expect(caseUpdate).toHaveBeenCalledWith(201, expect.objectContaining({
      dataset_id: 41,
      dataset_version: 3,
      config: expect.objectContaining({ dataset_strategy: 'pairwise' }),
    }))
  })

  it('preserves an existing device and low-code configuration when editing', async () => {
    caseGet.mockResolvedValue({
      id: 201,
      name: '启动冒烟',
      summary: '启动冒烟',
      description: '',
      tags: [],
      priority: 'P1',
      case_level: 'smoke',
      automation_status: 'auto',
      steps: [{ step_order: 1, action: 'start_app', description: '启动应用', expected_result: '应用已启动' }],
      config: {
        device_serial: 'emulator-5554',
        timeout: 180,
        steps: [{ action: 'start_app', name: '启动应用', params: { package: 'com.example.app' } }],
      },
    })

    const wrapper = mountDrawer({ id: 201 })
    await wrapper.setProps({ open: false })
    await wrapper.setProps({ open: true })
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'case.drawer.save_config')?.trigger('click')
    await flushPromises()

    expect(caseUpdate).toHaveBeenCalledWith(201, expect.objectContaining({
      priority: 'P1',
      case_level: 'smoke',
      config: expect.objectContaining({
        device_serial: 'emulator-5554',
        timeout: 180,
        steps: [{ action: 'start_app', name: '启动应用', params: { package: 'com.example.app' } }],
      }),
    }))
    expect(wrapper.emitted('saved')).toHaveLength(1)
  })
})
