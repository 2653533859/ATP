import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ApiWorkbenchView from './ApiWorkbenchView.vue'

const {
  caseGet,
  caseList,
  caseRun,
  environmentList,
  projectList,
  runList,
  routerPush,
  routerReplace,
} = vi.hoisted(() => ({
  caseGet: vi.fn(),
  caseList: vi.fn(),
  caseRun: vi.fn(),
  environmentList: vi.fn(),
  projectList: vi.fn(),
  runList: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { project_id: '1' } }),
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
}))
vi.mock('@ant-design/icons-vue', () => ({
  ApiOutlined: true,
  FilterOutlined: true,
  PlayCircleOutlined: true,
  PlusOutlined: true,
  ReloadOutlined: true,
  ThunderboltOutlined: true,
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'admin' } }),
}))
vi.mock('@/api', () => ({
  caseApi: { get: caseGet, list: caseList, run: caseRun },
  environmentApi: { list: environmentList },
  projectApi: { list: projectList },
  runApi: { list: runList },
}))
vi.mock('@/components/common/ModuleTree.vue', () => ({
  default: defineComponent({ name: 'ModuleTree', setup: () => () => h('div', 'module-tree') }),
}))
vi.mock('@/components/common/CaseFormDrawer.vue', () => ({
  default: defineComponent({ name: 'CaseFormDrawer', setup: () => () => h('div') }),
}))
vi.mock('@/views/case/AIGenerateDrawer.vue', () => ({
  default: defineComponent({ name: 'AIGenerateDrawer', setup: () => () => h('div') }),
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const buttonStub = defineComponent({
  name: 'AButton',
  props: ['disabled', 'loading'],
  emits: ['click'],
  setup: (_props, { slots, emit }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()),
})

const tableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource'],
  setup(props, { slots }) {
    return () => h('div', (props.dataSource || []).map((record: Record<string, unknown>) => h('div', [
      slots.bodyCell?.({ column: { key: 'name' }, record }),
      slots.bodyCell?.({ column: { key: 'protocol' }, record }),
      slots.bodyCell?.({ column: { key: 'action' }, record }),
    ])))
  },
})

const globalStubs = {
  AAlert: passthrough('AAlert'),
  AButton: buttonStub,
  ADrawer: passthrough('ADrawer'),
  AEmpty: passthrough('AEmpty'),
  AForm: passthrough('AForm'),
  AFormItem: passthrough('AFormItem'),
  AInputSearch: passthrough('AInputSearch'),
  AModal: passthrough('AModal'),
  ASelect: passthrough('ASelect'),
  ASpace: passthrough('ASpace'),
  ASpin: passthrough('ASpin'),
  ATable: tableStub,
  ATag: passthrough('ATag'),
  ApiOutlined: true,
  FilterOutlined: true,
  PlayCircleOutlined: true,
  PlusOutlined: true,
  ReloadOutlined: true,
  ThunderboltOutlined: true,
}

const apiCase = {
  id: 101,
  name: '登录接口',
  description: '登录校验',
  case_code: 'API-001',
  summary: '登录',
  case_type: 'api',
  status: 'active',
  priority: 'P1',
  case_level: 'core',
  review_status: 'approved',
  automation_status: 'automated',
  tags: [],
  module_id: 7,
  creator_id: 1,
  is_ready_for_execution: true,
  created_at: '2026-08-24T08:00:00Z',
  updated_at: '2026-08-24T09:00:00Z',
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue([{ id: 1, name: '核心项目', current_user_role: 'owner' }])
  environmentList.mockResolvedValue([{ id: 3, name: '测试环境' }])
  caseList.mockResolvedValue([apiCase, { ...apiCase, id: 102, case_type: 'web' }])
  runList.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 })
  caseRun.mockResolvedValue({ id: 500 })
  routerPush.mockResolvedValue(undefined)
  routerReplace.mockResolvedValue(undefined)
})

function mountWorkbench() {
  return mount(ApiWorkbenchView, { global: { stubs: globalStubs } })
}

describe('ApiWorkbenchView', () => {
  it('loads the selected project and keeps only API protocols', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(environmentList).toHaveBeenCalledWith(1)
    expect(caseList).toHaveBeenCalledWith({ project_id: 1, module_id: undefined, keyword: undefined })
    expect((wrapper.vm as unknown as { filteredCases: (typeof apiCase)[] }).filteredCases).toHaveLength(1)

    wrapper.unmount()
  })

  it('starts a ready API case and navigates to its run detail', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      openRun: (item: typeof apiCase) => void
      confirmRun: () => Promise<void>
    }

    vm.openRun(apiCase)
    await vm.confirmRun()

    expect(caseRun).toHaveBeenCalledWith(101, { env_id: undefined })
    expect(routerPush).toHaveBeenCalledWith({ name: 'run-detail', params: { runId: '500' } })

    wrapper.unmount()
  })
})
