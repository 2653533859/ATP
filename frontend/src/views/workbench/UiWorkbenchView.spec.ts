import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import UiWorkbenchView from './UiWorkbenchView.vue'
import type { WebRecordingStep } from '@/api'

const {
  baselineList,
  caseGet,
  caseList,
  caseRun,
  elementList,
  moduleList,
  pageObjectList,
  projectList,
  routerPush,
  routerReplace,
  runList,
  workerStatus,
} = vi.hoisted(() => ({
  baselineList: vi.fn(),
  caseGet: vi.fn(),
  caseList: vi.fn(),
  caseRun: vi.fn(),
  elementList: vi.fn(),
  moduleList: vi.fn(),
  pageObjectList: vi.fn(),
  projectList: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  runList: vi.fn(),
  workerStatus: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { project_id: '1', module_id: '7' } }),
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@ant-design/icons-vue', () => ({
  CheckCircleOutlined: true,
  DesktopOutlined: true,
  EyeOutlined: true,
  HistoryOutlined: true,
  PlayCircleOutlined: true,
  PlusOutlined: true,
  ReloadOutlined: true,
  SettingOutlined: true,
  VideoCameraOutlined: true,
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'admin' } }),
}))
vi.mock('@/api', () => ({
  caseApi: { get: caseGet, list: caseList, run: caseRun },
  projectApi: { getModules: moduleList, list: projectList },
  runApi: { list: runList },
  webAssetsApi: { listElements: elementList, listPageObjects: pageObjectList },
  webRecordingApi: { workers: workerStatus },
  webVisualApi: { listBaselines: baselineList },
}))

const passthrough = (name: string) => defineComponent({
  name,
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const globalStubs = {
  AAlert: passthrough('AAlert'),
  AButton: passthrough('AButton'),
  ACol: passthrough('ACol'),
  AEmpty: passthrough('AEmpty'),
  AForm: passthrough('AForm'),
  AFormItem: passthrough('AFormItem'),
  AInput: passthrough('AInput'),
  AInputNumber: passthrough('AInputNumber'),
  AModal: passthrough('AModal'),
  ARow: passthrough('ARow'),
  ASelect: passthrough('ASelect'),
  ASpace: passthrough('ASpace'),
  ASpin: passthrough('ASpin'),
  ATag: passthrough('ATag'),
  ModuleTree: passthrough('ModuleTree'),
  WebCaseDrawer: passthrough('WebCaseDrawer'),
  WebRecorderModal: passthrough('WebRecorderModal'),
  CheckCircleOutlined: true,
  DesktopOutlined: true,
  EyeOutlined: true,
  HistoryOutlined: true,
  PlayCircleOutlined: true,
  PlusOutlined: true,
  ReloadOutlined: true,
  SettingOutlined: true,
  VideoCameraOutlined: true,
}

const webCase = {
  id: 51,
  name: '登录流程',
  case_code: 'WEB-001',
  summary: '打开页面并登录',
  case_type: 'web',
  status: 'active',
  priority: 'P1',
  case_level: 'smoke',
  review_status: 'approved',
  automation_status: 'auto',
  script_status: 'generated',
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
  moduleList.mockResolvedValue([{ id: 7, name: '登录模块', project_id: 1, parent_id: null, sort_order: 1, created_at: '', children: [] }])
  caseList.mockResolvedValue([webCase, { ...webCase, id: 52, case_type: 'api', name: '接口用例' }])
  caseGet.mockResolvedValue({ ...webCase, config: { browser: 'chromium', steps: [{ action: 'goto', name: '打开首页', params: { url: 'https://example.test' } }] } })
  runList.mockResolvedValue({ items: [{ id: 700, case_id: 51, status: 'passed', trace_id: 'trace-1', created_at: '2026-08-24T10:00:00Z', duration_ms: 420, result_summary: {}, steps: [], case_name: '登录流程' }], total: 1, page: 1, page_size: 100 })
  elementList.mockResolvedValue([{ id: 12, name: '登录按钮', locator: { strategy: 'role', value: 'button' }, fallback_locators: [], version: 1, project_id: 1, created_at: '', updated_at: '' }])
  pageObjectList.mockResolvedValue([])
  baselineList.mockResolvedValue([])
  workerStatus.mockResolvedValue({ mode: 'worker', ready: true, workers: [], registered_count: 1, available_count: 1 })
  caseRun.mockResolvedValue({ id: 701 })
  routerPush.mockResolvedValue(undefined)
  routerReplace.mockResolvedValue(undefined)
})

function mountWorkbench() {
  return mount(UiWorkbenchView, { global: { stubs: globalStubs } })
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((nextResolve) => { resolve = nextResolve })
  return { promise, resolve }
}

describe('UiWorkbenchView', () => {
  it('loads only Web cases and connects the selected case to detail data', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()

    expect(caseList).toHaveBeenCalledWith(expect.objectContaining({ project_id: 1, module_id: 7, case_type: 'web' }))
    expect((wrapper.vm as unknown as { webCases: unknown[] }).webCases).toHaveLength(1)
    expect((wrapper.vm as unknown as { selectedCaseId: number | null }).selectedCaseId).toBe(51)
    expect(caseGet).toHaveBeenCalledWith(51)
    expect((wrapper.vm as unknown as { assetCount: number }).assetCount).toBe(1)

    wrapper.unmount()
  })

  it('runs the selected Web case through the existing run detail flow', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    await (wrapper.vm as unknown as { runSelectedCase: () => Promise<void> }).runSelectedCase()

    expect(caseRun).toHaveBeenCalledWith(51)
    expect(routerPush).toHaveBeenCalledWith({ name: 'run-detail', params: { runId: '701' } })
    wrapper.unmount()
  })

  it('turns a recording result into a new Web case draft', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      handleRecorded: (steps: WebRecordingStep[], assetIds: number[]) => void
      handleRecorderClose: () => void
      caseDrawerOpen: boolean
      initialCaseSteps: WebRecordingStep[]
    }
    const steps = [{ action: 'click', name: '点击登录', params: { selector: '#login' } }]
    vm.handleRecorded(steps, [12])
    vm.handleRecorderClose()

    expect(vm.caseDrawerOpen).toBe(true)
    expect(vm.initialCaseSteps).toEqual(steps)
    wrapper.unmount()
  })

  it('clears project-scoped state when the project selection is cleared', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      handleProjectChange: (value: unknown) => Promise<void>
      selectedProjectId: number | null
      webCases: unknown[]
      recentRuns: unknown[]
      elements: unknown[]
      pageObjects: unknown[]
      baselines: unknown[]
      workerStatus: unknown
    }

    await vm.handleProjectChange(null)

    expect(vm.selectedProjectId).toBeNull()
    expect(vm.webCases).toHaveLength(0)
    expect(vm.recentRuns).toHaveLength(0)
    expect(vm.elements).toHaveLength(0)
    expect(vm.pageObjects).toHaveLength(0)
    expect(vm.baselines).toHaveLength(0)
    expect(vm.workerStatus).toBeNull()
    wrapper.unmount()
  })

  it('does not let stale run history replace the latest module', async () => {
    const firstCases = deferred<typeof webCase[]>()
    const secondCases = deferred<typeof webCase[]>()
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
    caseGet.mockImplementation(async (caseId: number) => ({ ...webCase, id: caseId, config: { steps: [] } }))

    const wrapper = mountWorkbench()
    await flushPromises()
    firstCases.resolve([webCase])
    await flushPromises()
    expect(runList).toHaveBeenCalledTimes(1)

    const vm = wrapper.vm as unknown as {
      handleModuleSelect: (moduleId: number | null) => Promise<void>
      recentRuns: Array<{ id: number; case_id: number }>
      selectedCaseDetail: { id: number } | null
    }
    const latestLoad = vm.handleModuleSelect(8)
    await flushPromises()
    secondCases.resolve([{ ...webCase, id: 52, name: '最新页面用例' }])
    await flushPromises()
    secondRuns.resolve({
      items: [{ id: 2, case_id: 52, status: 'passed', created_at: '2026-08-24T10:00:00Z' }],
      total: 1,
      page: 1,
      page_size: 100,
    })
    await latestLoad
    firstRuns.resolve({
      items: [{ id: 1, case_id: 51, status: 'failed', created_at: '2026-08-24T09:00:00Z' }],
      total: 1,
      page: 1,
      page_size: 100,
    })
    await flushPromises()

    expect(vm.recentRuns).toEqual([{ id: 2, case_id: 52, status: 'passed', created_at: '2026-08-24T10:00:00Z' }])
    expect(vm.selectedCaseDetail?.id).toBe(52)
    wrapper.unmount()
  })
})
