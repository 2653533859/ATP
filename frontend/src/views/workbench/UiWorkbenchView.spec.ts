import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import UiWorkbenchView from './UiWorkbenchView.vue'
import type { RecordingRecordItem, WebRecordingStep } from '@/api'
import { saveLocalRecordingDraft } from '@/utils/recordingDraft'

const {
  baselineList,
  caseGet,
  caseList,
  caseRun,
  elementList,
  moduleList,
  pageObjectList,
  projectList,
  recordingRecordList,
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
  recordingRecordList: vi.fn(),
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
  recordingRecordApi: { list: recordingRecordList },
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
  RecordingHistoryDrawer: passthrough('RecordingHistoryDrawer'),
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
  localStorage.clear()
  projectList.mockResolvedValue([{ id: 1, name: '核心项目', current_user_role: 'owner' }])
  moduleList.mockResolvedValue([{ id: 7, name: '登录模块', project_id: 1, parent_id: null, sort_order: 1, created_at: '', children: [] }])
  caseList.mockResolvedValue([webCase, { ...webCase, id: 52, case_type: 'api', name: '接口用例' }])
  caseGet.mockResolvedValue({ ...webCase, config: { browser: 'chromium', steps: [{ action: 'goto', name: '打开首页', params: { url: 'https://example.test' } }] } })
  runList.mockResolvedValue({ items: [{ id: 700, case_id: 51, status: 'passed', trace_id: 'trace-1', created_at: '2026-08-24T10:00:00Z', duration_ms: 420, result_summary: {}, steps: [], case_name: '登录流程' }], total: 1, page: 1, page_size: 100 })
  elementList.mockResolvedValue([{ id: 12, name: '登录按钮', locator: { strategy: 'role', value: 'button' }, fallback_locators: [], version: 1, project_id: 1, created_at: '', updated_at: '' }])
  pageObjectList.mockResolvedValue([])
  baselineList.mockResolvedValue([])
  recordingRecordList.mockResolvedValue([])
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

  it('hydrates recoverable Web draft and Trace/HAR links after reload and restores into case creation', async () => {
    const serverDraft: RecordingRecordItem = {
      id: 88,
      project_id: 1,
      owner_id: 1,
      kind: 'web',
      source: 'workbench',
      session_id: 'sess-88',
      title: 'Web 录制 · demo.local',
      status: 'draft',
      target_url: 'https://demo.local/login',
      browser: 'chromium',
      device_id: null,
      device_serial: null,
      case_id: null,
      steps: [
        { action: 'goto', name: '打开页面', params: { url: 'https://demo.local/login' } },
        { action: 'assert_url_contains', name: '断言登录页', params: { expected: '/login' } },
      ],
      asset_ids: [12],
      steps_count: 2,
      assertion_count: 1,
      artifacts: {
        trace: {
          kind: 'trace',
          filename: 'trace.zip',
          content_type: 'application/zip',
          size: 1024,
          object_name: 'traces/recordings/1/sess-88/trace.zip',
          url: 'https://minio.local/trace.zip?sig=1',
        },
        har: {
          kind: 'har',
          filename: 'network.har',
          content_type: 'application/json',
          size: 512,
          object_name: 'reports/recordings/1/sess-88/network.har',
          url: 'https://minio.local/network.har?sig=2',
        },
      },
      summary: {},
      created_at: '2026-11-13T08:00:00Z',
      updated_at: '2026-11-13T08:01:00Z',
    }
    recordingRecordList.mockResolvedValue([serverDraft])

    const wrapper = mountWorkbench()
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      webDraftCount: number
      recoverableDraftBanner: {
        id: number | null
        traceUrl: string | null
        harUrl: string | null
        stepsCount: number
      } | null
      restoreRecoverableDraft: () => void
      handleCaseSaved: () => void
      caseDrawerOpen: boolean
      initialCaseSteps: WebRecordingStep[]
      initialCaseAssetIds: number[]
      activeRecordingRecordId: number | null
    }

    expect(recordingRecordList).toHaveBeenCalledWith({ project_id: 1, kind: 'web', limit: 30 })
    expect(vm.webDraftCount).toBe(1)
    expect(vm.recoverableDraftBanner?.id).toBe(88)
    expect(vm.recoverableDraftBanner?.traceUrl).toBe('https://minio.local/trace.zip?sig=1')
    expect(vm.recoverableDraftBanner?.harUrl).toBe('https://minio.local/network.har?sig=2')

    vm.restoreRecoverableDraft()
    expect(vm.caseDrawerOpen).toBe(true)
    expect(vm.initialCaseSteps).toHaveLength(2)
    expect(vm.initialCaseAssetIds).toEqual([12])
    expect(vm.activeRecordingRecordId).toBe(88)

    vm.handleCaseSaved()
    expect(vm.caseDrawerOpen).toBe(false)
    expect(vm.activeRecordingRecordId).toBeNull()
    wrapper.unmount()
  })

  it('falls back to localStorage draft when backend has no unsaved Web records', async () => {
    saveLocalRecordingDraft({
      kind: 'web',
      projectId: 1,
      title: '本地草稿',
      targetUrl: 'https://local.test/app?token=secret',
      steps: [{ action: 'click', name: '点击提交', params: { selector: '#submit' } }],
    })
    recordingRecordList.mockResolvedValue([])

    const wrapper = mountWorkbench()
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      webDraftCount: number
      recoverableDraftBanner: { title: string; stepsCount: number } | null
    }
    expect(vm.webDraftCount).toBe(1)
    expect(vm.recoverableDraftBanner?.stepsCount).toBe(1)
    wrapper.unmount()
  })

  it('uses source="assets" for baseline capture, drops unsafe artifact URLs, and avoids hijacking saved history on restore', async () => {
    localStorage.clear()
    recordingRecordList.mockResolvedValue([
      {
        id: 61,
        project_id: 1,
        kind: 'web',
        source: 'assets',
        session_id: 'baseline-1',
        title: '基线截图录制',
        status: 'stopped',
        target_url: 'https://example.test/home',
        browser: 'chromium',
        case_id: null,
        steps: [{ action: 'goto', name: '打开首页', params: { url: 'https://example.test/home' } }],
        steps_count: 1,
        assertion_count: 0,
        asset_ids: [],
        artifacts: {
          trace: {
            kind: 'trace',
            filename: 't.zip',
            content_type: 'application/zip',
            size: 10,
            url: 'javascript:alert(1)',
          },
        },
        summary: {},
        created_at: '',
        updated_at: '',
      },
      {
        id: 62,
        project_id: 1,
        kind: 'web',
        source: 'workbench',
        session_id: 'workbench-62',
        title: '工作台含不安全链接草稿',
        status: 'draft',
        target_url: 'https://example.test/login',
        browser: 'chromium',
        case_id: null,
        steps: [{ action: 'goto', name: '打开登录页', params: { url: 'https://example.test/login' } }],
        steps_count: 1,
        assertion_count: 0,
        asset_ids: [],
        artifacts: {
          trace: {
            kind: 'trace',
            filename: 't.zip',
            content_type: 'application/zip',
            size: 10,
            url: 'javascript:alert(1)',
          },
          har: {
            kind: 'har',
            filename: 'net.har',
            content_type: 'application/json',
            size: 20,
            url: 'https://minio.local/net.har',
          },
        },
        summary: {},
        created_at: '',
        updated_at: '',
      },
    ])

    const wrapper = mountWorkbench()
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      webDraftCount: number
      activeRecordingRecordId: number | null
      recoverableDraftBanner: { id: number; traceUrl: string | null; harUrl: string | null } | null
      openRecorder: (mode: 'case' | 'baseline') => void
    }
    expect(vm.webDraftCount).toBe(1)
    expect(vm.recoverableDraftBanner?.id).toBe(62)
    expect(vm.recoverableDraftBanner?.traceUrl).toBeNull()
    expect(vm.recoverableDraftBanner?.harUrl).toBe('https://minio.local/net.har')

    const baselineRecorder = wrapper.findComponent({ name: 'WebRecorderModal' })
    vm.openRecorder('baseline')
    await wrapper.vm.$nextTick()
    expect(baselineRecorder.attributes('source')).toBe('assets')

    baselineRecorder.vm.$emit('stopped', {
      id: 'baseline-sess-1',
      status: 'stopped',
      source: 'assets',
      start_url: 'https://example.test/home',
      browser: 'chromium',
      steps: [{ action: 'goto', name: '打开首页', params: { url: 'https://example.test/home' } }],
      asset_ids: [],
      recording_record_id: 99,
    })
    await flushPromises()
    expect(vm.activeRecordingRecordId).toBeNull()
    expect(localStorage.length).toBe(0)

    const historyDrawer = wrapper.findComponent({ name: 'RecordingHistoryDrawer' })
    expect(historyDrawer.vm.$attrs['can-modify'] ?? historyDrawer.vm.$attrs.canModify).toBe(true)
    historyDrawer.vm.$emit('restore', {
      id: 777,
      project_id: 1,
      kind: 'web',
      source: 'workbench',
      session_id: 'saved-777',
      title: '已保存历史录制',
      status: 'saved',
      target_url: 'https://example.test/done',
      browser: 'chromium',
      case_id: 45,
      steps: [{ action: 'goto', name: '打开目标页', params: { url: 'https://example.test/done' } }],
      steps_count: 1,
      assertion_count: 0,
      asset_ids: [],
      artifacts: {},
      summary: {},
      created_at: '',
      updated_at: '',
    })
    await flushPromises()
    expect(vm.activeRecordingRecordId).toBeNull()
    wrapper.unmount()
  })
})
