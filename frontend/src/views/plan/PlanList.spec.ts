import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import PlanList from './PlanList.vue'

const {
  environmentList,
  messageError,
  messageSuccess,
  messageWarning,
  planBatchDelete,
  planBatchToggle,
  planCreate,
  planDelete,
  planList,
  planListRuns,
  planRun,
  planUpdate,
  projectList,
  suiteList,
} = vi.hoisted(() => ({
  environmentList: vi.fn(),
  messageError: vi.fn(),
  messageSuccess: vi.fn(),
  messageWarning: vi.fn(),
  planBatchDelete: vi.fn(),
  planBatchToggle: vi.fn(),
  planCreate: vi.fn(),
  planDelete: vi.fn(),
  planList: vi.fn(),
  planListRuns: vi.fn(),
  planRun: vi.fn(),
  planUpdate: vi.fn(),
  projectList: vi.fn(),
  suiteList: vi.fn(),
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string, params?: Record<string, unknown>) => (params ? `${key}:${JSON.stringify(params)}` : key) }) }))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('ant-design-vue', () => ({
  message: { error: messageError, success: messageSuccess, warning: messageWarning },
}))
vi.mock('@/api', () => ({
  environmentApi: { list: environmentList },
  planApi: {
    batchDelete: planBatchDelete,
    batchToggle: planBatchToggle,
    create: planCreate,
    delete: planDelete,
    exportRunHtml: vi.fn(),
    exportRunPdf: vi.fn(),
    list: planList,
    listRuns: planListRuns,
    run: planRun,
    update: planUpdate,
  },
  projectApi: { list: projectList },
  suiteApi: { list: suiteList },
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
        { 'data-test': 'plan-table' },
        [
          h('button', {
            'data-test': 'select-first-row',
            onClick: () => props.rowSelection?.onChange?.([1]),
          }),
          ...(props.dataSource || []).map((record: Record<string, unknown>) =>
            h('div', { class: 'plan-row', key: record.id as number }, [
              h('span', { class: 'plan-name' }, String(record.name)),
              slots.bodyCell?.({ column: { key: 'schedule_type' }, record }),
              slots.bodyCell?.({ column: { key: 'is_enabled' }, record }),
              slots.bodyCell?.({ column: { key: 'suites' }, record }),
              slots.bodyCell?.({ column: { key: 'action' }, record }),
            ]),
          ),
        ],
      )
  },
})

function mountPlanList() {
  return mount(PlanList, {
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
        AInput: inputStub('AInput'),
        AInputGroup: passthrough('AInputGroup'),
        AInputNumber: inputStub('AInputNumber'),
        AModal: passthrough('AModal'),
        APopconfirm: popconfirmStub,
        ARadioButton: passthrough('ARadioButton'),
        ARadioGroup: passthrough('ARadioGroup'),
        ARow: passthrough('ARow'),
        ASelect: selectStub,
        ASpace: passthrough('ASpace'),
        ASwitch: passthrough('ASwitch'),
        ATable: tableStub,
        ATag: defineComponent({ name: 'ATag', setup: (_p, { slots }) => () => h('span', { 'data-test': 'tag' }, slots.default?.()) }),
        ATextarea: inputStub('ATextarea'),
        BatchOperationBar: passthrough('BatchOperationBar'),
        PlusOutlined: true,
      },
    },
  })
}

const PROJECTS = [{ id: 10, name: 'Core' }]
const PLANS = [
  {
    id: 1,
    name: 'Nightly',
    description: '',
    project_id: 10,
    suite_ids: [{ suite_id: 2, sort: 0 }],
    schedule_type: 'cron',
    cron_expression: '0 9 * * *',
    is_enabled: true,
    auto_create_bugs: false,
    config: { execution_mode: 'sequential', fail_strategy: 'continue', max_workers: 1, min_pass_rate: 0.8 },
    created_at: '2026-07-11T01:00:00Z',
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue(PROJECTS)
  planList.mockResolvedValue(PLANS)
  suiteList.mockResolvedValue([{ id: 2, name: 'Smoke' }])
  environmentList.mockResolvedValue([{ id: 5, name: 'staging' }])
  planRun.mockResolvedValue({ id: 99 })
  planDelete.mockResolvedValue({})
  planListRuns.mockResolvedValue([{ id: 77, status: 'passed', created_at: '2026-07-11T02:00:00Z' }])
  planCreate.mockResolvedValue({ id: 3 })
  planUpdate.mockResolvedValue({})
  planBatchDelete.mockResolvedValue({ requested: 1, processed: 1 })
  planBatchToggle.mockResolvedValue({ requested: 1, processed: 1 })
})

async function chooseProject(wrapper: ReturnType<typeof mountPlanList>) {
  await flushPromises()
  await wrapper.find('[data-test="select"]').setValue('10')
  await flushPromises()
}

describe('PlanList mount', () => {
  it('loads project options on mount and plans after project selection', async () => {
    const wrapper = mountPlanList()
    await chooseProject(wrapper)

    expect(projectList).toHaveBeenCalledOnce()
    expect(planList).toHaveBeenCalledWith({ project_id: 10 })
    expect(wrapper.findAll('.plan-row')).toHaveLength(1)
    expect(wrapper.text()).toContain('Nightly')
  })

  it('runs, opens records, and deletes from row actions', async () => {
    const wrapper = mountPlanList()
    await chooseProject(wrapper)
    planList.mockClear()

    const buttons = wrapper.findAll('button')
    await buttons.find((button) => button.text().includes('plan.actions.run'))!.trigger('click')
    await flushPromises()
    expect(planRun).toHaveBeenCalledWith(1)
    expect(messageSuccess).toHaveBeenCalled()

    await buttons.find((button) => button.text().includes('plan.actions.records'))!.trigger('click')
    await flushPromises()
    expect(planListRuns).toHaveBeenCalledWith({ plan_id: 1 })

    const confirms = wrapper.findAll('[data-test="confirm"]')
    await confirms[confirms.length - 1].trigger('click')
    await flushPromises()
    expect(planDelete).toHaveBeenCalledWith(1)
  })

  it('opens create flow and saves a valid manual plan', async () => {
    const wrapper = mountPlanList()
    await chooseProject(wrapper)

    await wrapper.findAll('button').find((button) => button.text().includes('plan.new'))!.trigger('click')
    await flushPromises()
    await wrapper.findAll('input')[0].setValue('Release gate')
    await wrapper.findAll('button').find((button) => button.text().includes('plan.actions.edit'))!.trigger('click')
    await flushPromises()

    expect(suiteList).toHaveBeenCalledWith({ project_id: 10 })
    expect(environmentList).toHaveBeenCalledWith(10)
  })

  it('supports batch selection and enable toggle', async () => {
    const wrapper = mountPlanList()
    await chooseProject(wrapper)

    await wrapper.find('[data-test="select-first-row"]').trigger('click')
    await wrapper.findAll('button').find((button) => button.text().includes('plan.batch_enable'))!.trigger('click')
    await flushPromises()

    expect(planBatchToggle).toHaveBeenCalledWith([1], true)
    expect(messageSuccess).toHaveBeenCalled()
  })

  it('surfaces load failures', async () => {
    planList.mockRejectedValue(new Error('boom'))
    const wrapper = mountPlanList()
    await chooseProject(wrapper)

    expect(messageError).toHaveBeenCalled()
    expect(wrapper.findAll('.plan-row')).toHaveLength(0)
  })
})
