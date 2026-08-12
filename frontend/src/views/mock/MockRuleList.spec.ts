import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MockRuleList from './MockRuleList.vue'

const {
  projectList,
  ruleList,
  ruleCreate,
  ruleUpdate,
  ruleDelete,
  ruleLogs,
  ruleExport,
  ruleImport,
  ruleAiGenerate,
  messageError,
  messageSuccess,
  messageWarning,
} = vi.hoisted(() => ({
  projectList: vi.fn(),
  ruleList: vi.fn(),
  ruleCreate: vi.fn(),
  ruleUpdate: vi.fn(),
  ruleDelete: vi.fn(),
  ruleLogs: vi.fn(),
  ruleExport: vi.fn(),
  ruleImport: vi.fn(),
  ruleAiGenerate: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string, params?: Record<string, unknown>) => params ? `${key}:${JSON.stringify(params)}` : key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess, warning: messageWarning },
}))
vi.mock('@/api/http', () => ({ getBackendOrigin: () => 'http://backend' }))
vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  mockRuleApi: {
    list: ruleList,
    create: ruleCreate,
    update: ruleUpdate,
    delete: ruleDelete,
    logs: ruleLogs,
    exportRules: ruleExport,
    importRules: ruleImport,
    aiGenerate: ruleAiGenerate,
  },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const buttonStub = defineComponent({
  name: 'AButton',
  props: { disabled: Boolean },
  emits: ['click'],
  setup: (props, { slots, emit }) => () => h('button', { disabled: props.disabled, onClick: () => emit('click') }, slots.default?.()),
})

const tableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource'],
  setup: (props, { slots }) => () => h(
    'div',
    { 'data-test': 'rule-table' },
    (props.dataSource || []).map((record: Record<string, unknown>) => h(
      'div',
      { class: 'rule-row', key: String(record.id) },
      slots.bodyCell?.({ column: { key: 'action' }, record }),
    )),
  ),
})

function mountPage() {
  return mount(MockRuleList, {
    global: {
      stubs: {
        AAlert: passthrough('AAlert'),
        AButton: buttonStub,
        ACard: passthrough('ACard'),
        ACol: passthrough('ACol'),
        ADivider: passthrough('ADivider'),
        ADrawer: passthrough('ADrawer'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInput: passthrough('AInput'),
        AInputNumber: passthrough('AInputNumber'),
        AModal: passthrough('AModal'),
        APopconfirm: passthrough('APopconfirm'),
        ARow: passthrough('ARow'),
        ASelect: passthrough('ASelect'),
        ASelectOption: passthrough('ASelectOption'),
        ASpace: passthrough('ASpace'),
        ASwitch: passthrough('ASwitch'),
        ATable: tableStub,
        ATag: passthrough('ATag'),
        ATextarea: passthrough('ATextarea'),
        AUpload: passthrough('AUpload'),
        PlusOutlined: true,
        UnorderedListOutlined: true,
        ThunderboltOutlined: true,
      },
    },
  })
}

const PROJECTS = [{ id: 7, name: 'Core' }]
const RULE = {
  id: 8,
  project_id: 7,
  name: 'Users',
  method: 'GET',
  path: '/api/users',
  status_code: 200,
  delay_ms: 0,
  is_enabled: true,
  render_template: false,
  record_requests: true,
  response_headers: { 'Content-Type': 'application/json' },
  response_body: '{"ok":true}',
  match_conditions: { query: { scene: 'ok' }, headers: {}, body: {} },
  recorded_samples: [{ path: '/api/users' }],
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue(PROJECTS)
  ruleList.mockResolvedValue([RULE])
  ruleCreate.mockResolvedValue({ id: 9 })
  ruleUpdate.mockResolvedValue({})
  ruleDelete.mockResolvedValue({})
  ruleLogs.mockResolvedValue([{ timestamp: '2026-08-01T10:00:00Z', method: 'GET', path: '/api/users', matched: true }])
  ruleExport.mockResolvedValue({ project_id: 7, rules: [RULE] })
  ruleImport.mockResolvedValue([RULE])
  ruleAiGenerate.mockResolvedValue({
    project_id: 7,
    rules: [{
      name: 'Generated users',
      method: 'GET',
      path: '/api/users/generated',
      status_code: 200,
      response_headers: { 'Content-Type': 'application/json' },
      response_body: '{"ok":true}',
      match_conditions: { query: {}, headers: {}, body: {} },
      delay_ms: 0,
      is_enabled: true,
      render_template: false,
      record_requests: false,
    }],
    warnings: [],
  })
})

describe('MockRuleList mount', () => {
  it('loads projects and rules for the selected project', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectId = 7
    await vm.loadRules()

    expect(projectList).toHaveBeenCalledOnce()
    expect(ruleList).toHaveBeenCalledWith({ project_id: 7 })
    expect(wrapper.findAll('.rule-row')).toHaveLength(1)
    expect(vm.mockBaseUrl).toBe('http://backend/mock/7')
  })

  it('normalizes paths and JSON conditions when creating a rule', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectId = 7
    vm.openCreate()
    vm.form.name = 'Orders'
    vm.form.path = 'api/orders'
    vm.form.response_body = '{"ok":true}'
    vm.headersText = '{"Content-Type":"application/json"}'
    vm.queryConditionsText = '{"scene":"success"}'
    vm.headerConditionsText = '{}'
    vm.bodyConditionsText = '{}'

    await vm.handleSave()
    expect(ruleCreate).toHaveBeenCalledWith(expect.objectContaining({
      project_id: 7,
      path: '/api/orders',
      response_headers: { 'Content-Type': 'application/json' },
      match_conditions: { query: { scene: 'success' }, headers: {}, body: {} },
    }))
  })

  it('rejects invalid JSON, supports edit/copy, and imports rules', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectId = 7
    vm.openCreate()
    vm.form.name = 'Broken'
    vm.form.path = '/broken'
    vm.headersText = '{bad json'
    await vm.handleSave()
    expect(messageWarning).toHaveBeenCalled()
    expect(ruleCreate).not.toHaveBeenCalled()

    vm.openEdit(RULE)
    expect(vm.isEdit).toBe(true)
    expect(vm.currentSamples).toHaveLength(1)
    vm.handleCopy(RULE)
    expect(vm.isEdit).toBe(false)
    expect(vm.form.name).toContain('mock.copy_name')
    expect(vm.currentSamples).toEqual([])

    await vm.beforeImportRules({ text: async () => JSON.stringify({ rules: [RULE] }) } as File)
    expect(ruleImport).toHaveBeenCalledWith({ project_id: 7, rules: [RULE] })
    expect(messageSuccess).toHaveBeenCalledWith('mock.msg.import_success')
  })

  it('loads logs, exports rules, and deletes a rule', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectId = 7
    await wrapper.vm.$nextTick()
    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock')
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)

    await vm.openLogs()
    expect(ruleLogs).toHaveBeenCalledWith(7)
    await wrapper.findAll('button').find((button) => button.text() === 'mock.export_rules')!.trigger('click')
    expect(ruleExport).toHaveBeenCalledWith(7)
    expect(messageSuccess).toHaveBeenCalledWith('mock.msg.export_success')
    await vm.handleDelete(8)
    expect(ruleDelete).toHaveBeenCalledWith(8)
    expect(messageSuccess).toHaveBeenCalledWith('mock.msg.delete_success')

    createObjectURL.mockRestore()
    revokeObjectURL.mockRestore()
    anchorClick.mockRestore()
  })

  it('generates Mock drafts for review and saves them only after confirmation', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.projectId = 7
    vm.selectedRuleIds = [8]

    vm.openAIMockGeneration()
    expect(vm.aiMockGenerateOpen).toBe(true)
    await vm.generateAIMockRules()

    expect(ruleAiGenerate).toHaveBeenCalledWith(expect.objectContaining({
      project_id: 7,
      rule_ids: [8],
      rule_count: 1,
    }))
    expect(vm.aiMockPreviewOpen).toBe(true)
    expect(ruleCreate).not.toHaveBeenCalled()

    await vm.saveAIMockRules()
    expect(ruleCreate).toHaveBeenCalledWith(expect.objectContaining({
      project_id: 7,
      name: 'Generated users',
      path: '/api/users/generated',
    }))
    expect(vm.aiMockPreviewOpen).toBe(false)
  })
})
