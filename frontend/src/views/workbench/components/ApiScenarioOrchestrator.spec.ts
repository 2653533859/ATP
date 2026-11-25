import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ApiScenarioOrchestrator from './ApiScenarioOrchestrator.vue'

const {
  getVariables,
  previewRequest,
  apiScenarioCreate,
  apiScenarioUpdate,
  apiScenarioRecordRun,
} = vi.hoisted(() => ({
  getVariables: vi.fn(),
  previewRequest: vi.fn(),
  apiScenarioCreate: vi.fn().mockResolvedValue({ id: 90, name: '新场景', steps: [] }),
  apiScenarioUpdate: vi.fn().mockResolvedValue({ id: 90, name: '新场景', steps: [] }),
  apiScenarioRecordRun: vi.fn().mockResolvedValue({}),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@ant-design/icons-vue', () => ({
  ApiOutlined: true,
  FileAddOutlined: true,
  FilterOutlined: true,
  MinusCircleOutlined: true,
  PlayCircleOutlined: true,
  PlusOutlined: true,
  ReloadOutlined: true,
  SendOutlined: true,
  ThunderboltOutlined: true,
  ClusterOutlined: true,
  DownOutlined: true,
  FormatPainterOutlined: true,
  CopyOutlined: true,
  ArrowUpOutlined: true,
  ArrowDownOutlined: true,
  DeleteOutlined: true,
  MoreOutlined: true,
  HolderOutlined: true,
  CheckCircleOutlined: true,
  CloseCircleOutlined: true,
  SaveOutlined: true,
}))
vi.mock('vuedraggable', () => ({
  default: defineComponent({
    name: 'draggable',
    props: ['modelValue'],
    setup: () => () => h('div'),
  }),
}))
vi.mock('@/api', () => ({
  apiScenarioApi: {
    create: apiScenarioCreate,
    update: apiScenarioUpdate,
    recordRun: apiScenarioRecordRun,
    executeDag: vi.fn(),
  },
  caseApi: {
    previewRequest,
    suggestAssertions: vi.fn(),
  },
  environmentApi: {
    getVariables,
  },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const globalStubs = {
  AAlert: passthrough('AAlert'),
  AButton: passthrough('AButton'),
  ACheckbox: passthrough('ACheckbox'),
  ACol: passthrough('ACol'),
  ADivider: passthrough('ADivider'),
  ADrawer: passthrough('ADrawer'),
  ADropdown: passthrough('ADropdown'),
  AEmpty: passthrough('AEmpty'),
  AForm: passthrough('AForm'),
  AFormItem: passthrough('AFormItem'),
  AInput: passthrough('AInput'),
  AInputNumber: passthrough('AInputNumber'),
  AInputPassword: passthrough('AInputPassword'),
  AInputSearch: passthrough('AInputSearch'),
  AMenu: passthrough('AMenu'),
  AMenuDivider: passthrough('AMenuDivider'),
  AMenuItem: passthrough('AMenuItem'),
  AModal: passthrough('AModal'),
  ARadioButton: passthrough('ARadioButton'),
  ARadioGroup: passthrough('ARadioGroup'),
  ARow: passthrough('ARow'),
  ASelect: passthrough('ASelect'),
  ASelectOption: passthrough('ASelectOption'),
  ASpace: passthrough('ASpace'),
  ASpin: passthrough('ASpin'),
  ATabPane: passthrough('ATabPane'),
  ATabs: passthrough('ATabs'),
  ATag: passthrough('ATag'),
  ATextarea: passthrough('ATextarea'),
  ATooltip: passthrough('ATooltip'),
  KvEditor: passthrough('KvEditor'),
}

beforeEach(() => {
  vi.clearAllMocks()
  getVariables.mockResolvedValue([
    { key: 'base_url', value: 'https://stg.example.com' },
    { key: 'api_ver', value: 'v2' },
  ])
  previewRequest.mockResolvedValue({
    status_code: 200,
    duration_ms: 15,
    headers: { 'content-type': 'text/plain' },
    body: 'user id=42 ok',
  })
})

describe('ApiScenarioOrchestrator regressions', () => {
  it('loads environment variables, extracts regex values, and evaluates negative status assertions', async () => {
    const wrapper = mount(ApiScenarioOrchestrator, {
      props: {
        projectId: 1,
        moduleId: 10,
        canModify: true,
        cases: [],
        environments: [
          { id: 5, project_id: 1, name: 'Staging', created_at: '', updated_at: '' },
        ],
        initialSteps: [
          {
            name: 'Fetch User',
            method: 'GET',
            url: '{{base_url}}/{{api_ver}}/users',
            headers: {},
            params: {},
            cookies: {},
            body_type: 'none',
            body: '',
            assertions: [{ target: 'status_code', operator: 'ne', expected: '200' }],
            extractions: [{ variable: 'user_id', type: 'regex', expression: 'id=(\\d+)' }],
          },
        ],
      },
      global: { stubs: globalStubs },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      selectedEnvId: number | undefined
      debugCurrentStep: (mode: 'single') => Promise<void>
      currentDebugResult: {
        passed: boolean
        assertionDetails: Array<{ passed: boolean }>
      } | null
      runtimeVariables: Record<string, string>
      steps: unknown[]
      scenarioName: string
    }

    expect(getVariables).toHaveBeenCalledWith(5)
    expect(vm.selectedEnvId).toBe(5)

    await vm.debugCurrentStep('single')
    expect(previewRequest).toHaveBeenCalledWith(1, expect.objectContaining({
      url: 'https://stg.example.com/v2/users',
      env_id: 5,
    }))
    expect(vm.runtimeVariables).toEqual({ user_id: '42' })
    // Explicit status_code != 200 assertion must fail on 200 instead of being overridden by < 400
    expect(vm.currentDebugResult?.passed).toBe(false)
    expect(vm.currentDebugResult?.assertionDetails[0].passed).toBe(false)

    // Switching project resets orchestrator scenario steps and runtime state
    await wrapper.setProps({ projectId: 2, environments: [] })
    await flushPromises()
    expect(vm.steps).toEqual([])
    expect(vm.currentDebugResult).toBeNull()
    wrapper.unmount()
  })
})
