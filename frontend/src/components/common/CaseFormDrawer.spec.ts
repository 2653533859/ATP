import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CaseFormDrawer from './CaseFormDrawer.vue'

const { caseUpdate, caseCreate, datasetList, projectList, schemaList } = vi.hoisted(() => ({
  caseUpdate: vi.fn().mockResolvedValue({ id: 55 }),
  caseCreate: vi.fn().mockResolvedValue({ id: 56 }),
  datasetList: vi.fn().mockResolvedValue([]),
  projectList: vi.fn().mockResolvedValue([]),
  schemaList: vi.fn().mockResolvedValue([]),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@ant-design/icons-vue', () => ({
  PlusOutlined: true,
  MinusCircleOutlined: true,
  FormatPainterOutlined: true,
  ThunderboltOutlined: true,
  ReloadOutlined: true,
  ApiOutlined: true,
  DownOutlined: true,
}))
vi.mock('@/runtimeMode', () => ({
  getRuntimeMode: () => 'server',
}))
vi.mock('@/api', () => ({
  caseApi: {
    create: caseCreate,
    update: caseUpdate,
    previewRequest: vi.fn(),
    suggestAssertions: vi.fn(),
    generateGrpcProto: vi.fn(),
    introspectGraphql: vi.fn(),
  },
  datasetApi: { list: datasetList, listVersions: vi.fn().mockResolvedValue([]) },
  projectApi: { list: projectList },
  apiSchemaAssetApi: { list: schemaList },
}))
vi.mock('@/components/common/ApiLibraryPickerDrawer.vue', () => ({
  default: defineComponent({ name: 'ApiLibraryPickerDrawer', setup: () => () => h('div') }),
}))
vi.mock('@/components/common/ApiScenarioPipeline.vue', () => ({
  default: defineComponent({ name: 'ApiScenarioPipeline', setup: () => () => h('div') }),
}))
vi.mock('@/components/common/KvEditor.vue', () => ({
  default: defineComponent({ name: 'KvEditor', setup: () => () => h('div') }),
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const formStub = defineComponent({
  name: 'AForm',
  setup(_props, { slots, expose }) {
    expose({ validate: () => Promise.resolve() })
    return () => h('form', slots.default?.())
  },
})

const globalStubs = {
  AAlert: passthrough('AAlert'),
  AButton: passthrough('AButton'),
  ACheckbox: passthrough('ACheckbox'),
  ACol: passthrough('ACol'),
  ADivider: passthrough('ADivider'),
  ADrawer: passthrough('ADrawer'),
  ADropdown: passthrough('ADropdown'),
  AForm: formStub,
  AFormItem: passthrough('AFormItem'),
  AInput: passthrough('AInput'),
  AInputNumber: passthrough('AInputNumber'),
  AInputPassword: passthrough('AInputPassword'),
  AMenu: passthrough('AMenu'),
  AMenuItem: passthrough('AMenuItem'),
  AModal: passthrough('AModal'),
  ARadioButton: passthrough('ARadioButton'),
  ARadioGroup: passthrough('ARadioGroup'),
  ARow: passthrough('ARow'),
  ASelect: passthrough('ASelect'),
  ASelectOption: passthrough('ASelectOption'),
  ASpace: passthrough('ASpace'),
  ATabPane: passthrough('ATabPane'),
  ATabs: passthrough('ATabs'),
  ATag: passthrough('ATag'),
  ATextarea: passthrough('ATextarea'),
  AUpload: passthrough('AUpload'),
  DownOutlined: true,
  PlusOutlined: true,
  MinusCircleOutlined: true,
  FormatPainterOutlined: true,
  ThunderboltOutlined: true,
  ReloadOutlined: true,
  ApiOutlined: true,
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('CaseFormDrawer', () => {
  it('saves single-step edits in cfg instead of discarding them to stale apiScenarioSteps', async () => {
    const wrapper = mount(CaseFormDrawer, {
      props: {
        open: false,
        moduleId: 7,
        projectId: 1,
        editCase: {
          id: 55,
          name: '登录接口',
          case_type: 'api',
          priority: 'P1',
          case_level: 'core',
          tags: [],
          config: {
            steps: [
              {
                name: '登录',
                method: 'GET',
                url: 'https://old.example/login',
                headers: { Accept: 'application/json' },
                params: {},
                cookies: {},
                body_type: 'none',
                assertions: [],
              },
            ],
          },
        },
      },
      global: { stubs: globalStubs },
    })
    await wrapper.setProps({ open: true })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      cfg: { method: string; url: string }
      apiConfigTab: string
      handleSave: () => Promise<void>
    }

    expect(vm.apiConfigTab).toBe('request')
    expect(vm.cfg.url).toBe('https://old.example/login')

    vm.cfg.method = 'POST'
    vm.cfg.url = 'https://updated.example/v2'
    await vm.handleSave()

    expect(caseUpdate).toHaveBeenCalledTimes(1)
    const [updatedId, payload] = caseUpdate.mock.calls[0]
    expect(updatedId).toBe(55)
    expect(payload.config.steps).toHaveLength(1)
    expect(payload.config.steps[0]).toMatchObject({
      method: 'POST',
      url: 'https://updated.example/v2',
    })
    wrapper.unmount()
  })
})
