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

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((nextResolve) => { resolve = nextResolve })
  return { promise, resolve }
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

  it('does not let a stale run-history response replace the latest module', async () => {
    const firstCases = deferred<typeof apiCase[]>()
    const secondCases = deferred<typeof apiCase[]>()
    const firstRuns = deferred<{ items: Array<Record<string, unknown>>; total: number; page: number; page_size: number }>()
    const secondRuns = deferred<{ items: Array<Record<string, unknown>>; total: number; page: number; page_size: number }>()
    caseList.mockReset()
    caseList
      .mockImplementationOnce(() => firstCases.promise)
      .mockImplementationOnce(() => secondCases.promise)
    runList.mockReset()
    runList
      .mockImplementationOnce(() => firstRuns.promise)
      .mockImplementationOnce(() => secondRuns.promise)

    const wrapper = mountWorkbench()
    await flushPromises()
    firstCases.resolve([apiCase])
    await flushPromises()
    expect(runList).toHaveBeenCalledTimes(1)

    const vm = wrapper.vm as unknown as {
      handleModuleSelect: (moduleId: number | null) => Promise<void>
      recentRuns: Array<{ case_id: number }>
    }
    const latestLoad = vm.handleModuleSelect(8)
    await flushPromises()
    secondCases.resolve([{ ...apiCase, id: 102, name: '最新接口' }])
    await flushPromises()
    secondRuns.resolve({
      items: [{ id: 2, case_id: 102, status: 'passed', created_at: '2026-08-24T10:00:00Z' }],
      total: 1,
      page: 1,
      page_size: 100,
    })
    await latestLoad
    firstRuns.resolve({
      items: [{ id: 1, case_id: 101, status: 'failed', created_at: '2026-08-24T09:00:00Z' }],
      total: 1,
      page: 1,
      page_size: 100,
    })
    await flushPromises()

    expect(vm.recentRuns).toEqual([{ id: 2, case_id: 102, status: 'passed', created_at: '2026-08-24T10:00:00Z' }])
    wrapper.unmount()
  })

  it('does not let a stale case detail replace the latest selection', async () => {
    const firstDetail = deferred<Record<string, unknown>>()
    const secondDetail = deferred<Record<string, unknown>>()
    caseGet.mockReset()
    caseGet
      .mockImplementationOnce(() => firstDetail.promise)
      .mockImplementationOnce(() => secondDetail.promise)

    const wrapper = mountWorkbench()
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      openDetail: (item: typeof apiCase) => Promise<void>
      selectedCase: typeof apiCase | null
      selectedCaseDetail: { id: number } | null
      detailLoading: boolean
    }
    const firstLoad = vm.openDetail(apiCase)
    await flushPromises()
    const latestCase = { ...apiCase, id: 102, name: '最新接口' }
    const latestLoad = vm.openDetail(latestCase)
    await flushPromises()

    secondDetail.resolve({ ...latestCase, config: { steps: [] } })
    await latestLoad
    firstDetail.resolve({ ...apiCase, config: { steps: [{ method: 'GET', url: '/old' }] } })
    await firstLoad
    await flushPromises()

    expect(vm.selectedCase?.id).toBe(102)
    expect(vm.selectedCaseDetail?.id).toBe(102)
    expect(vm.detailLoading).toBe(false)
    wrapper.unmount()
  })

  it('does not reopen the edit drawer after a pending detail request is closed', async () => {
    const editDetail = deferred<Record<string, unknown>>()
    caseGet.mockReset().mockImplementationOnce(() => editDetail.promise)

    const wrapper = mountWorkbench()
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      openEdit: (item: typeof apiCase) => Promise<void>
      closeCaseForm: () => void
      caseFormOpen: boolean
      editingCase: Record<string, unknown> | null
    }
    const editLoad = vm.openEdit(apiCase)
    await flushPromises()
    vm.closeCaseForm()
    editDetail.resolve({ ...apiCase, config: { steps: [] } })
    await editLoad
    await flushPromises()

    expect(vm.caseFormOpen).toBe(false)
    expect(vm.editingCase).toBeNull()
    wrapper.unmount()
  })

  it('does not let a stale project environment response replace the latest project', async () => {
    const secondProjectEnvironments = deferred<Array<{ id: number; name: string }>>()
    const latestProjectEnvironments = deferred<Array<{ id: number; name: string }>>()
    environmentList.mockReset()
    environmentList
      .mockResolvedValueOnce([{ id: 1, name: '项目一环境' }])
      .mockImplementationOnce(() => secondProjectEnvironments.promise)
      .mockImplementationOnce(() => latestProjectEnvironments.promise)

    const wrapper = mountWorkbench()
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      handleProjectChange: (projectId: number) => Promise<void>
      environments: Array<{ id: number; name: string }>
    }
    const staleLoad = vm.handleProjectChange(2)
    await flushPromises()
    const latestLoad = vm.handleProjectChange(3)
    await flushPromises()

    latestProjectEnvironments.resolve([{ id: 3, name: '项目三环境' }])
    await latestLoad
    secondProjectEnvironments.resolve([{ id: 2, name: '项目二环境' }])
    await staleLoad
    await flushPromises()

    expect(vm.environments).toEqual([{ id: 3, name: '项目三环境' }])
    wrapper.unmount()
  })
})
