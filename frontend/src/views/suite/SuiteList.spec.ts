import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SuiteList from './SuiteList.vue'

const {
  caseList,
  environmentList,
  getModules,
  messageError,
  messageSuccess,
  messageWarning,
  modalConfirm,
  projectList,
  routerPush,
  suiteBatchCopy,
  suiteBatchDelete,
  suiteCreate,
  suiteDelete,
  suiteList,
  suiteListRuns,
  suiteRun,
  suiteUpdate,
} = vi.hoisted(() => ({
  caseList: vi.fn(),
  environmentList: vi.fn(),
  getModules: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  modalConfirm: vi.fn(),
  projectList: vi.fn(),
  routerPush: vi.fn(),
  suiteBatchCopy: vi.fn(),
  suiteBatchDelete: vi.fn(),
  suiteCreate: vi.fn(),
  suiteDelete: vi.fn(),
  suiteList: vi.fn(),
  suiteListRuns: vi.fn(),
  suiteRun: vi.fn(),
  suiteUpdate: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ push: routerPush }),
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ locale: { value: 'zh-CN' }, t: (key: string, params?: Record<string, unknown>) => (params ? `${key}:${JSON.stringify(params)}` : key) }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess, warning: messageWarning },
  Modal: { confirm: modalConfirm },
}))
vi.mock('vuedraggable', () => ({
  default: defineComponent({ name: 'Draggable', setup: (_p, { slots }) => () => h('div', slots.default?.({ element: {}, index: 0 })) }),
}))
vi.mock('@/api', () => ({
  caseApi: { list: caseList },
  environmentApi: { list: environmentList },
  projectApi: { getModules, list: projectList },
  suiteApi: {
    batchCopy: suiteBatchCopy,
    batchDelete: suiteBatchDelete,
    create: suiteCreate,
    delete: suiteDelete,
    exportRunHtml: vi.fn(),
    exportRunPdf: vi.fn(),
    list: suiteList,
    listRuns: suiteListRuns,
    run: suiteRun,
    update: suiteUpdate,
  },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_p, { slots }) => () => h('div', slots.default?.()) })

const buttonStub = defineComponent({
  name: 'AButton',
  emits: ['click'],
  setup: (_p, { slots, emit }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()),
})

const inputStub = (name: string) =>
  defineComponent({
    name,
    props: ['value'],
    emits: ['update:value'],
    setup: (props, { emit }) =>
      () => h('input', { value: props.value, onInput: (event: Event) => emit('update:value', (event.target as HTMLInputElement).value) }),
  })

const selectStub = defineComponent({
  name: 'ASelect',
  props: ['value', 'options'],
  emits: ['update:value', 'change'],
  setup: (props, { emit, slots }) =>
    () =>
      h(
        'select',
        {
          'data-test': 'select',
          value: props.value ?? '',
          onChange: (event: Event) => {
            const raw = (event.target as HTMLSelectElement).value
            const value = raw === '' ? undefined : Number(raw)
            emit('update:value', value)
            emit('change', value)
          },
        },
        props.options?.length
          ? props.options.map((option: { label: string; value: number | string }) =>
              h('option', { value: option.value }, option.label),
            )
          : slots.default?.(),
      ),
})

const selectOptionStub = defineComponent({
  name: 'ASelectOption',
  props: ['value'],
  setup: (props, { slots }) => () => h('option', { value: props.value }, slots.default?.()),
})

const popconfirmStub = defineComponent({
  name: 'APopconfirm',
  emits: ['confirm'],
  setup: (_p, { slots, emit }) => () => h('span', { 'data-test': 'confirm', onClick: () => emit('confirm') }, slots.default?.()),
})

const tableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource', 'rowSelection'],
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        { 'data-test': 'suite-table' },
        [
          h('button', {
            'data-test': 'select-first-row',
            onClick: () => props.rowSelection?.onChange?.([1]),
          }),
          ...(props.dataSource || []).map((record: Record<string, unknown>) =>
            h('div', { class: 'suite-row', key: record.id as number }, [
              h('span', { class: 'suite-name' }, String(record.name ?? record.case_name ?? record.id)),
              slots.bodyCell?.({ column: { key: 'project' }, record }),
              slots.bodyCell?.({ column: { key: 'strategy' }, record }),
              slots.bodyCell?.({ column: { key: 'case_count' }, record }),
              slots.bodyCell?.({ column: { key: 'action' }, record }),
            ]),
          ),
        ],
      )
  },
})

function mountSuiteList() {
  return mount(SuiteList, {
    global: {
      stubs: {
        AAlert: passthrough('AAlert'),
        AButton: buttonStub,
        ACol: passthrough('ACol'),
        ADrawer: passthrough('ADrawer'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInput: inputStub('AInput'),
        AInputNumber: inputStub('AInputNumber'),
        AInputSearch: inputStub('AInputSearch'),
        AModal: passthrough('AModal'),
        APopconfirm: popconfirmStub,
        AProgress: passthrough('AProgress'),
        ARow: passthrough('ARow'),
        ASelect: selectStub,
        ASelectOption: selectOptionStub,
        ASpace: passthrough('ASpace'),
        ATable: tableStub,
        ATag: defineComponent({ name: 'ATag', setup: (_p, { slots }) => () => h('span', { 'data-test': 'tag' }, slots.default?.()) }),
        ATextarea: inputStub('ATextarea'),
        ATooltip: passthrough('ATooltip'),
        ATreeSelect: selectStub,
        Draggable: passthrough('Draggable'),
        BatchOperationBar: passthrough('BatchOperationBar'),
        HolderOutlined: true,
        PlusOutlined: true,
      },
    },
  })
}

const PROJECTS = [{ id: 10, name: 'Core' }]
const SUITES = [
  {
    id: 1,
    name: 'Smoke',
    description: '',
    project_id: 10,
    case_ids: [{ case_id: 100, sort: 0 }],
    config: { execution_mode: 'parallel', fail_strategy: 'continue', max_workers: 2, min_pass_rate: 0.8 },
    created_at: '2026-07-11T01:00:00Z',
  },
]
const CASES = [
  {
    id: 100,
    case_code: 'API-100',
    name: 'Login works',
    module_id: 5,
    case_type: 'api',
    priority: 'P1',
    status: 'active',
    review_status: 'approved',
    automation_status: 'automated',
    is_ready_for_execution: true,
    tags: ['smoke'],
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue(PROJECTS)
  suiteList.mockResolvedValue(SUITES)
  caseList.mockResolvedValue(CASES)
  getModules.mockResolvedValue([{ id: 5, name: 'Auth', children: [] }])
  environmentList.mockResolvedValue([{ id: 7, name: 'staging' }])
  suiteRun.mockResolvedValue({ id: 55 })
  suiteListRuns.mockResolvedValue([{ id: 66, status: 'passed', case_runs: [], created_at: '2026-07-11T02:00:00Z' }])
  suiteDelete.mockResolvedValue({})
  suiteCreate.mockResolvedValue({ id: 2 })
  suiteUpdate.mockResolvedValue({})
  suiteBatchCopy.mockResolvedValue({ requested: 1, processed: 1 })
  suiteBatchDelete.mockResolvedValue({ requested: 1, processed: 1 })
})

async function chooseProject(wrapper: ReturnType<typeof mountSuiteList>) {
  await flushPromises()
  await wrapper.find('[data-test="select"]').setValue('10')
  await flushPromises()
}

describe('SuiteList mount', () => {
  it('loads projects and suites on mount, then filters by project selection', async () => {
    const wrapper = mountSuiteList()
    await chooseProject(wrapper)

    expect(projectList).toHaveBeenCalledOnce()
    expect(suiteList).toHaveBeenCalledWith({ project_id: 10 })
    expect(wrapper.findAll('.suite-row')).toHaveLength(1)
    expect(wrapper.text()).toContain('Smoke')
  })

  it('opens run modal, confirms run, and opens run records', async () => {
    const wrapper = mountSuiteList()
    await chooseProject(wrapper)

    await wrapper.findAll('button').find((button) => button.text().includes('suite.actions.run'))!.trigger('click')
    await flushPromises()
    expect(environmentList).toHaveBeenCalledWith(10)

    await wrapper.findAll('button').find((button) => button.text().includes('common.ok'))?.trigger('click')
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('suite.actions.records'))!.trigger('click')
    await flushPromises()
    expect(suiteListRuns).toHaveBeenCalledWith({ suite_id: 1 })
  })

  it('opens create flow and loads selectable cases/modules', async () => {
    const wrapper = mountSuiteList()
    await chooseProject(wrapper)

    await wrapper.findAll('button').find((button) => button.text().includes('suite.new'))!.trigger('click')
    await flushPromises()

    expect(caseList).toHaveBeenCalledWith({ project_id: 10 })
    expect(getModules).toHaveBeenCalledWith(10)
  })

  it('supports batch copy after table selection', async () => {
    const wrapper = mountSuiteList()
    await chooseProject(wrapper)

    await wrapper.find('[data-test="select-first-row"]').trigger('click')
    await wrapper.findAll('button').find((button) => button.text().includes('suite.batch_copy'))!.trigger('click')
    await flushPromises()

    expect(suiteBatchCopy).toHaveBeenCalledWith([1])
    expect(messageSuccess).toHaveBeenCalled()
  })

  it('deletes a suite from row action and reports load failures', async () => {
    const wrapper = mountSuiteList()
    await chooseProject(wrapper)

    const confirms = wrapper.findAll('[data-test="confirm"]')
    await confirms[confirms.length - 1].trigger('click')
    await flushPromises()
    expect(suiteDelete).toHaveBeenCalledWith(1)

    suiteList.mockRejectedValueOnce(new Error('boom'))
    await wrapper.find('[data-test="select"]').setValue('10')
    await flushPromises()
    expect(messageError).toHaveBeenCalled()
  })
})
