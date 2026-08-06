import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DatasetLibrary from './DatasetLibrary.vue'

const {
  projectList,
  datasetList,
  datasetGet,
  datasetCreate,
  datasetUpdate,
  datasetDelete,
  datasetImpact,
  datasetVersions,
  datasetRollback,
  datasetUpload,
  datasetPreviewUpload,
  datasetValidate,
  messageError,
  messageSuccess,
  messageWarning,
  routerPush,
} = vi.hoisted(() => ({
  projectList: vi.fn(),
  datasetList: vi.fn(),
  datasetGet: vi.fn(),
  datasetCreate: vi.fn(),
  datasetUpdate: vi.fn(),
  datasetDelete: vi.fn(),
  datasetImpact: vi.fn(),
  datasetVersions: vi.fn(),
  datasetRollback: vi.fn(),
  datasetUpload: vi.fn(),
  datasetPreviewUpload: vi.fn(),
  datasetValidate: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  routerPush: vi.fn(),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerPush }),
}))

vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess, warning: messageWarning },
}))

vi.mock('@/api', () => ({
  projectApi: { list: projectList },
  datasetApi: {
    list: datasetList,
    get: datasetGet,
    create: datasetCreate,
    update: datasetUpdate,
    delete: datasetDelete,
    getImpact: datasetImpact,
    listVersions: datasetVersions,
    rollback: datasetRollback,
    upload: datasetUpload,
    previewUpload: datasetPreviewUpload,
    validate: datasetValidate,
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

const inputStub = (name: string, tag: 'input' | 'textarea') => defineComponent({
  name,
  props: ['value'],
  emits: ['update:value'],
  setup: (props, { emit }) => () => h(tag, {
    value: props.value,
    onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value),
  }),
})

const drawerStub = defineComponent({
  name: 'ADrawer',
  setup: (_props, { slots }) => () => h('div', { 'data-test': 'dataset-drawer' }, [
    slots.default?.(),
    slots.footer?.(),
  ]),
})

const tableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource'],
  setup: (props, { slots }) => () => h(
    'div',
    { 'data-test': 'dataset-table' },
    (props.dataSource || []).map((record: Record<string, unknown>) => h(
      'div',
      { class: 'dataset-row', key: String(record.id) },
      slots.bodyCell?.({ column: { key: 'actions' }, record }),
    )),
  ),
})

const confirmStub = defineComponent({
  name: 'APopconfirm',
  emits: ['confirm'],
  setup: (_props, { slots, emit }) => () => h(
    'span',
    { 'data-test': 'confirm', onClick: () => emit('confirm') },
    slots.default?.(),
  ),
})

function mountPage() {
  return mount(DatasetLibrary, {
    global: {
      stubs: {
        AAlert: passthrough('AAlert'),
        AButton: buttonStub,
        ACard: passthrough('ACard'),
        ACheckbox: passthrough('ACheckbox'),
        ACol: passthrough('ACol'),
        ADrawer: drawerStub,
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInput: inputStub('AInput', 'input'),
        AInputSearch: passthrough('AInputSearch'),
        AModal: passthrough('AModal'),
        APopconfirm: confirmStub,
        ARadio: passthrough('ARadio'),
        ARadioButton: passthrough('ARadioButton'),
        ARadioGroup: passthrough('ARadioGroup'),
        ARow: passthrough('ARow'),
        ASelect: passthrough('ASelect'),
        ASpace: passthrough('ASpace'),
        ASpin: passthrough('ASpin'),
        AStatistic: passthrough('AStatistic'),
        ATable: tableStub,
        ATextarea: inputStub('ATextarea', 'textarea'),
        ATag: passthrough('ATag'),
        AUpload: passthrough('AUpload'),
        PlusOutlined: true,
      },
    },
  })
}

const PROJECTS = [{ id: 1, name: 'Core', owner_id: 1 }]
const DATASETS = [{
  id: 11,
  project_id: 1,
  name: 'Users',
  description: 'test users',
  format: 'json',
  row_count: 2,
  schema_field_count: 1,
  validation_policy: 'hard',
  updated_at: '2026-08-01T10:00:00Z',
}]

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue(PROJECTS)
  datasetList.mockResolvedValue(DATASETS)
  datasetGet.mockResolvedValue({
    ...DATASETS[0],
    rows: [{ id: 1 }],
    schema_fields: [{ name: 'id', type: 'integer', required: true, default: 0 }],
  })
  datasetCreate.mockResolvedValue({ id: 12 })
  datasetUpdate.mockResolvedValue({})
  datasetDelete.mockResolvedValue({})
  datasetImpact.mockResolvedValue({ dataset_id: 11, cases: [], suites: [], plans: [], total_count: 0 })
  datasetVersions.mockResolvedValue([{ version: 1, created_at: '2026-08-01T10:00:00Z' }])
  datasetRollback.mockResolvedValue({})
  datasetUpload.mockResolvedValue({})
  datasetPreviewUpload.mockResolvedValue({ valid: true, can_upload: true, issues: [], normalized_rows: [] })
  datasetValidate.mockResolvedValue({ valid: true, can_upload: true, issues: [], normalized_rows: [] })
})

describe('DatasetLibrary mount', () => {
  it('loads the first project and its datasets on mount', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(datasetList).toHaveBeenCalledWith(1)
    expect(wrapper.findAll('.dataset-row')).toHaveLength(1)
    expect(wrapper.text()).toContain('dataset.title')
  })

  it('validates a new dataset and sends normalized rows and schema fields', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    await wrapper.findAll('button').find((button) => button.text().includes('system_pages.dataset.create'))!.trigger('click')
    await wrapper.findAll('button').find((button) => button.text() === 'common.save')!.trigger('click')
    expect(messageWarning).toHaveBeenCalledWith('system_pages.dataset.name_required')

    vm.form.name = 'Orders'
    vm.rowsText = '[{"id": 1}]'
    vm.form.schema_fields = [{ name: 'id', type: 'integer', required: true, defaultText: '0' }]
    await wrapper.findAll('button').find((button) => button.text() === 'common.save')!.trigger('click')

    expect(datasetCreate).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Orders',
      project_id: 1,
      rows: [{ id: 1 }],
      schema_fields: [{ name: 'id', type: 'integer', required: true, default: 0 }],
      validation_policy: 'soft',
    }))
    expect(messageSuccess).toHaveBeenCalledWith('common.saved')
  })

  it('explains missing project selection and surfaces save failures', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.projectId = null
    vm.openCreate()
    expect(messageWarning).toHaveBeenCalledWith('system_pages.dataset.select_project_before_create')

    vm.projectId = 1
    vm.form.name = 'Orders'
    datasetCreate.mockRejectedValueOnce(new Error('request failed'))
    await vm.onSave()
    expect(messageError).toHaveBeenCalledWith('request failed')
  })

  it('rejects malformed rows, validates data, and confirms an upload', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.openCreate()
    vm.form.name = 'Orders'
    vm.rowsText = '{bad json'
    await vm.onSave()
    expect(vm.rowsTextError).toBe('system_pages.dataset.rows_parse_failed')
    expect(datasetCreate).not.toHaveBeenCalled()

    vm.rowsText = '[{"id": 1}]'
    vm.form.schema_fields = []
    await vm.validateCurrentRows()
    expect(datasetValidate).toHaveBeenCalledWith({ schema_fields: [], rows: [{ id: 1 }], preview_limit: 5 })
    expect(vm.validationOpen).toBe(true)

    const file = { name: 'orders.json' } as File
    const result = await vm.onUpload(11, file)
    expect(result).toBe(false)
    expect(datasetPreviewUpload).toHaveBeenCalledWith(11, file)
    await vm.confirmValidationAction()
    expect(datasetUpload).toHaveBeenCalledWith(11, file)
  })

  it('supports edit, version rollback, impact lookup, and deletion', async () => {
    const wrapper = mountPage()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.openEdit(DATASETS[0])
    expect(datasetGet).toHaveBeenCalledWith(11)
    expect(vm.form.name).toBe('Users')

    await vm.openVersions(DATASETS[0])
    expect(datasetVersions).toHaveBeenCalledWith(11)
    await vm.rollbackVersion(1)
    expect(datasetRollback).toHaveBeenCalledWith(11, 1)

    await vm.openImpact(DATASETS[0])
    expect(datasetImpact).toHaveBeenCalledWith(11)
    await wrapper.find('[data-test="confirm"]').trigger('click')
    expect(datasetDelete).toHaveBeenCalledWith(11)
    expect(messageSuccess).toHaveBeenCalledWith('common.deleted')
  })
})
