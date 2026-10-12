import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CaseList from './CaseList.vue'

const { caseList, getModules, messageError, projectList, routerPush, routerReplace } = vi.hoisted(() => ({
  caseList: vi.fn(),
  getModules: vi.fn(),
  messageError: vi.fn(),
  projectList: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: {} }),
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
}))
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('ant-design-vue', () => ({ message: { error: messageError }, Modal: { confirm: vi.fn() } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { role: 'admin' }, token: 'token' }) }))
vi.mock('@/components/common/ModuleTree.vue', () => ({ default: defineComponent({ name: 'ModuleTree', emits: ['select'], setup: (_p, { emit }) => () => h('button', { 'data-test': 'module-tree', onClick: () => emit('select', 5) }, 'module') }) }))
vi.mock('@/components/common/CaseFormDrawer.vue', () => ({ default: defineComponent({ name: 'CaseFormDrawer', setup: () => () => h('div') }) }))
vi.mock('@/views/case/WebCaseDrawer.vue', () => ({ default: defineComponent({ name: 'WebCaseDrawer', setup: () => () => h('div') }) }))
vi.mock('@/views/case/AndroidCaseDrawer.vue', () => ({ default: defineComponent({ name: 'AndroidCaseDrawer', setup: () => () => h('div') }) }))
vi.mock('@/views/case/CaseHistoryDrawer.vue', () => ({ default: defineComponent({ name: 'CaseHistoryDrawer', setup: () => () => h('div') }) }))
vi.mock('@/views/case/AIGenerateDrawer.vue', () => ({ default: defineComponent({ name: 'AIGenerateDrawer', setup: () => () => h('div') }) }))
vi.mock('@/api', () => ({
  caseApi: { list: caseList, run: vi.fn(), copy: vi.fn(), workflow: vi.fn() },
  environmentApi: { list: vi.fn().mockResolvedValue([]) },
  projectApi: { getModules, list: projectList },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_p, { slots }) => () => h('div', slots.default?.()) })

const buttonStub = defineComponent({
  name: 'AButton',
  emits: ['click'],
  setup: (_p, { slots, emit }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()),
})

const tagStub = defineComponent({
  name: 'ATag',
  props: ['color'],
  setup: (props, { slots }) => () => h('span', { 'data-tag-color': props.color || 'default' }, slots.default?.()),
})

const tableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource'],
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        (props.dataSource || []).map((record: Record<string, unknown>) =>
          h('div', { class: 'case-row' }, [
            slots.bodyCell?.({ column: { key: 'name' }, record }),
            slots.bodyCell?.({ column: { key: 'case_type' }, record }),
            slots.bodyCell?.({ column: { key: 'stability' }, record }),
            slots.bodyCell?.({ column: { key: 'action' }, record }),
          ]),
        ),
      )
  },
})

function mountCaseList() {
  return mount(CaseList, {
    global: {
      stubs: {
        AButton: buttonStub,
        ACard: passthrough('ACard'),
        ACol: passthrough('ACol'),
        ADropdown: passthrough('ADropdown'),
        AInputSearch: passthrough('AInputSearch'),
        AMenu: passthrough('AMenu'),
        AMenuItem: passthrough('AMenuItem'),
        AModal: passthrough('AModal'),
        APopconfirm: passthrough('APopconfirm'),
        ARow: passthrough('ARow'),
        ASelect: passthrough('ASelect'),
        ASelectOption: passthrough('ASelectOption'),
        ASpace: passthrough('ASpace'),
        AStatistic: defineComponent({ name: 'AStatistic', props: ['value'], setup: (props) => () => h('span', { 'data-test': 'stat' }, String(props.value)) }),
        ATable: tableStub,
        ATag: tagStub,
        ATooltip: passthrough('ATooltip'),
        AUpload: passthrough('AUpload'),
        BatchOperationBar: passthrough('BatchOperationBar'),
        DownOutlined: true,
        FileTextOutlined: true,
        HistoryOutlined: true,
        PlusOutlined: true,
        ThunderboltOutlined: true,
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue([{ id: 10, name: 'Core' }])
  getModules.mockResolvedValue([{ id: 5, name: 'Auth', children: [] }])
  caseList.mockResolvedValue([
    {
      id: 100,
      name: 'Login',
      case_code: 'API-100',
      module_id: 5,
      case_type: 'api',
      priority: 'P1',
      case_level: 'smoke',
      status: 'active',
      review_status: 'approved',
      automation_status: 'auto',
      tags: ['smoke'],
      summary: 'happy path',
      is_flaky: false,
    },
  ])
})

describe('CaseList mount', () => {
  it('loads default project modules and cases', async () => {
    const wrapper = mountCaseList()
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(getModules).toHaveBeenCalledWith(10)
    expect(caseList).toHaveBeenCalledWith(expect.objectContaining({ project_id: 10 }))
    expect(wrapper.findAll('.case-row')).toHaveLength(1)
    expect(wrapper.text()).toContain('Login')
  })

  it('syncs route when selecting a module from ModuleTree', async () => {
    const wrapper = mountCaseList()
    await flushPromises()

    await wrapper.find('[data-test="module-tree"]').trigger('click')
    await flushPromises()

    expect(routerReplace).toHaveBeenCalledWith(expect.objectContaining({ name: 'cases' }))
  })

  it('shows a neutral status before the first run and colors measured stability', async () => {
    const baseCase = (id: number, stats?: Record<string, unknown>) => ({
      id,
      name: `Case ${id}`,
      case_code: `API-${id}`,
      module_id: 5,
      case_type: 'api',
      priority: 'P1',
      case_level: 'smoke',
      status: 'active',
      review_status: 'approved',
      automation_status: 'auto',
      tags: [],
      summary: '',
      flaky_stats: stats,
    })
    caseList.mockResolvedValue([
      baseCase(1, { total_runs: 0, is_flaky: false }),
      baseCase(2, { total_runs: 3, is_flaky: false }),
      baseCase(3, { total_runs: 3, is_flaky: true }),
      baseCase(4),
    ])

    const wrapper = mountCaseList()
    await flushPromises()

    const rows = wrapper.findAll('.case-row')
    expect(rows).toHaveLength(4)
    expect(rows[0].findAll('[data-tag-color="default"]').some((tag) => tag.text() === 'case.flaky.no_runs')).toBe(true)
    expect(rows[1].find('[data-tag-color="green"]').text()).toBe('case.flaky.stable')
    expect(rows[2].find('[data-tag-color="volcano"]').text()).toBe('case.flaky.flaky')
    expect(rows[3].findAll('[data-tag-color="default"]').some((tag) => tag.text() === 'case.flaky.no_runs')).toBe(true)
  })
})
