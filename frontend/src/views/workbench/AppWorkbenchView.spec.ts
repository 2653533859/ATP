import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AppWorkbenchView from './AppWorkbenchView.vue'
import type { RecordingRecordItem } from '@/api'
import { saveLocalRecordingDraft } from '@/utils/recordingDraft'

const {
  apkList,
  caseList,
  caseGet,
  casePrecheck,
  caseRun,
  deviceAcquireLease,
  deviceReleaseLease,
  deviceList,
  deviceWorkers,
  mobileListRuns,
  mobileListTasks,
  mobileTriggerTask,
  projectList,
  recordingRecordCreate,
  recordingRecordList,
  routerPush,
  routerReplace,
  runList,
} = vi.hoisted(() => ({
  apkList: vi.fn(),
  caseList: vi.fn(),
  caseGet: vi.fn(),
  casePrecheck: vi.fn(),
  caseRun: vi.fn(),
  deviceAcquireLease: vi.fn(),
  deviceReleaseLease: vi.fn(),
  deviceList: vi.fn(),
  deviceWorkers: vi.fn(),
  mobileListRuns: vi.fn(),
  mobileListTasks: vi.fn(),
  mobileTriggerTask: vi.fn(),
  projectList: vi.fn(),
  recordingRecordCreate: vi.fn(),
  recordingRecordList: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  runList: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { project_id: '1' } }),
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))
vi.mock('@ant-design/icons-vue', () => ({
  AndroidOutlined: true,
  AppstoreOutlined: true,
  EyeOutlined: true,
  EditOutlined: true,
  HomeOutlined: true,
  HistoryOutlined: true,
  LeftOutlined: true,
  MinusOutlined: true,
  MobileOutlined: true,
  PlayCircleOutlined: true,
  PlusOutlined: true,
  PoweroffOutlined: true,
  ReloadOutlined: true,
  SafetyCertificateOutlined: true,
  SendOutlined: true,
  SyncOutlined: true,
  ThunderboltOutlined: true,
  ToolOutlined: true,
}))
vi.mock('@/views/device/components/DeviceMirrorModal.vue', () => ({
  default: defineComponent({
    name: 'DeviceMirrorModal',
    props: ['open', 'device', 'canModify', 'leaseToken'],
    emits: ['update:open', 'close', 'recorded', 'draft-captured'],
    setup: () => () => h('div', { class: 'device-mirror-modal-stub' }),
  }),
}))
vi.mock('@/views/case/AndroidCaseDrawer.vue', () => ({
  default: defineComponent({
    name: 'AndroidCaseDrawer',
    props: ['open', 'moduleId', 'projectId', 'editCase', 'initialSteps', 'initialDeviceSerial', 'recordingRecordId'],
    emits: ['close', 'saved'],
    setup: () => () => h('div', { class: 'android-case-drawer-stub' }),
  }),
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'admin' } }),
}))
vi.mock('@/api', () => ({
  apkApi: { list: apkList },
  caseApi: { list: caseList, run: caseRun, get: caseGet, precheck: casePrecheck },
  deviceApi: {
    acquireLease: deviceAcquireLease,
    releaseLease: deviceReleaseLease,
    list: deviceList,
    workers: deviceWorkers,
    screenshot: vi.fn(),
  },
  mobileSpecialApi: {
    listRuns: mobileListRuns,
    listTasks: mobileListTasks,
    triggerTask: mobileTriggerTask,
  },
  projectApi: { list: projectList, getModules: vi.fn().mockResolvedValue([{ id: 10, name: '默认模块' }]) },
  recordingRecordApi: { create: recordingRecordCreate, list: recordingRecordList, update: vi.fn(), get: vi.fn(), remove: vi.fn() },
  runApi: { list: runList },
}))

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_props, { slots }) => () => h('div', slots.default?.()) })

const globalStubs = {
  AAlert: passthrough('AAlert'),
  AButton: passthrough('AButton'),
  AEmpty: passthrough('AEmpty'),
  AModal: passthrough('AModal'),
  ASelect: passthrough('ASelect'),
  ASpin: passthrough('ASpin'),
  ATag: passthrough('ATag'),
  RecordingHistoryDrawer: passthrough('RecordingHistoryDrawer'),
  AndroidOutlined: true,
  AppstoreOutlined: true,
  EyeOutlined: true,
  HistoryOutlined: true,
  MobileOutlined: true,
  PlayCircleOutlined: true,
  ReloadOutlined: true,
  SafetyCertificateOutlined: true,
  ThunderboltOutlined: true,
  ToolOutlined: true,
}

const androidCase = {
  id: 101,
  name: 'Karing 登录',
  case_code: 'AND-001',
  summary: '打开应用并完成登录',
  case_type: 'android',
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

const specialTask = {
  id: 9,
  name: 'Karing 稳定性巡检',
  project_id: 1,
  task_type: 'stability',
  source_type: 'apk_only',
  device_scope_type: 'single_device',
  device_id: 10,
  apk_id: 21,
  app_package: 'com.example.karing',
  config_json: { capture_replay: true },
  schedule_enabled: false,
  created_at: '2026-08-24T08:00:00Z',
  updated_at: '2026-08-24T09:00:00Z',
}

// 设备页会挂可见性监听和轮询定时器，每个用例结束都卸载，避免残留实例串扰后续用例
enableAutoUnmount(afterEach)

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  projectList.mockResolvedValue([{ id: 1, name: '移动项目', current_user_role: 'owner' }])
  deviceList.mockResolvedValue([
    { id: 10, serial: 'emulator-5554', name: 'Pixel 7', model: 'Pixel 7', brand: 'Google', os_version: '14', sdk_version: '34', resolution: '1080x2400', status: 'online', created_at: '', updated_at: '' },
    { id: 11, serial: 'offline-01', name: '备用机', model: 'Mi 12', brand: 'Xiaomi', os_version: '13', sdk_version: '33', status: 'offline', created_at: '', updated_at: '' },
  ])
  deviceWorkers.mockResolvedValue([{ worker_id: 'win-android-01', status: 'online', queues: ['mobile_special'], capabilities: ['adb'], updated_at: 1, expires_at: 2 }])
  apkList.mockResolvedValue([{ id: 21, project_id: 1, filename: 'karing.apk', package_name: 'com.example.karing', version_name: '1.0.0', file_size: 1024 * 1024, object_name: 'apks/21', uploaded_by: 1, created_at: '', updated_at: '' }])
  caseList.mockResolvedValue([androidCase, { ...androidCase, id: 102, case_type: 'api', name: '不应显示的接口用例' }])
  mobileListTasks.mockResolvedValue([specialTask])
  mobileListRuns.mockResolvedValue([{ id: 800, task_id: 9, task_type: 'stability', status: 'completed', device_id: 10, device_serial: 'emulator-5554', apk_id: 21, app_package: 'com.example.karing', summary_json: {}, config_snapshot: {}, trigger_type: 'manual', created_at: '2026-08-24T10:00:00Z', updated_at: '2026-08-24T10:01:00Z', task_name: 'Karing 稳定性巡检' }])
  runList.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100 })
  caseRun.mockResolvedValue({ id: 900 })
  casePrecheck.mockResolvedValue({ ok: true, device_serial: 'emulator-5554', items: [] })
  mobileTriggerTask.mockResolvedValue({ id: 901 })
  recordingRecordList.mockResolvedValue([])
  recordingRecordCreate.mockResolvedValue({ id: 77 })
  deviceAcquireLease.mockResolvedValue({ device_id: 10, owner_label: 'app-workbench', acquired_at: '', heartbeat_at: '', expires_at: '2026-08-24T11:00:00Z', lease_token: 'lease-token-123456789' })
  deviceReleaseLease.mockResolvedValue(undefined)
  routerPush.mockResolvedValue(undefined)
  routerReplace.mockResolvedValue(undefined)
})

function mountWorkbench() {
  return mount(AppWorkbenchView, { global: { stubs: globalStubs } })
}

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

describe('AppWorkbenchView', () => {
  it('checks the selected device before starting an Android run', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as { runAndroidCase: () => Promise<void> }

    casePrecheck.mockResolvedValueOnce({ ok: true, device_serial: 'another-device', items: [] })
    await vm.runAndroidCase()
    expect(caseRun).not.toHaveBeenCalled()

    casePrecheck.mockResolvedValueOnce({ ok: false, device_serial: 'emulator-5554', items: [{ status: 'FAIL', code: 'DEVICE_OFFLINE', message: '设备离线' }] })
    await vm.runAndroidCase()
    expect(caseRun).not.toHaveBeenCalled()

    await vm.runAndroidCase()
    expect(casePrecheck).toHaveBeenCalledWith(101)
    expect(caseRun).toHaveBeenCalledWith(101)
    wrapper.unmount()
  })

  it('hands recorded steps to the case draft after releasing the workbench lease', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      acquireLease: () => Promise<void>
      handleMirrorRecorded: (steps: Array<{ action: string; name: string; params: Record<string, unknown> }>) => Promise<void>
      caseDrawerOpen: boolean
    }
    await vm.acquireLease()
    await flushPromises()
    expect(wrapper.findComponent({ name: 'DeviceMirrorModal' }).props('leaseToken')).toBe('lease-token-123456789')
    await vm.handleMirrorRecorded([{ action: 'click', name: '镜像点击', params: { x: 10, y: 20 } }])
    await flushPromises()

    expect(deviceReleaseLease).toHaveBeenCalledWith(10, 'lease-token-123456789')
    expect(vm.caseDrawerOpen).toBe(true)
    const drawer = wrapper.findComponent({ name: 'AndroidCaseDrawer' })
    expect(drawer.props('initialSteps')).toEqual([{ action: 'click', name: '镜像点击', params: { x: 10, y: 20 } }])
    expect(drawer.props('initialDeviceSerial')).toBe('emulator-5554')
    wrapper.unmount()
  })

  it('retains the recorded draft when the workbench lease cannot be released', async () => {
    deviceReleaseLease.mockRejectedValueOnce(new Error('release failed'))
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      acquireLease: () => Promise<void>
      handleMirrorRecorded: (steps: Array<{ action: string; name: string; params: Record<string, unknown> }>) => Promise<void>
      caseDrawerOpen: boolean
      recordedDraftSteps: Array<{ action: string }>
    }
    await vm.acquireLease()
    await vm.handleMirrorRecorded([{ action: 'click', name: '镜像点击', params: { x: 10, y: 20 } }])

    expect(vm.caseDrawerOpen).toBe(false)
    expect(vm.recordedDraftSteps).toHaveLength(1)
    wrapper.unmount()
  })

  it('loads the Android capability assets and filters out non-Android cases', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()

    expect(projectList).toHaveBeenCalledOnce()
    expect(deviceWorkers).toHaveBeenCalledOnce()
    expect(caseList).toHaveBeenCalledWith({ project_id: 1, case_type: 'android' })
    expect((wrapper.vm as unknown as { androidCases: unknown[] }).androidCases).toHaveLength(1)
    expect((wrapper.vm as unknown as { selectedDeviceId: number | null }).selectedDeviceId).toBe(10)

    wrapper.unmount()
  })

  it('runs a special task without letting the device-pool focus override its default target', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      launchMode: 'case' | 'special'
      runSpecialTask: () => Promise<void>
      selectedSpecialTaskId: number | undefined
      launchDeviceId: number | null
    }

    vm.launchMode = 'special'
    vm.selectedSpecialTaskId = 9
    vm.launchDeviceId = null
    await vm.runSpecialTask()

    expect(mobileTriggerTask).toHaveBeenCalledWith(9, { device_id: undefined, apk_id: undefined, app_package: undefined })
    expect(routerPush).toHaveBeenCalledWith('/mobile-special/reports/901')

    wrapper.unmount()
  })

  it('passes the selected APK asset when overriding a special task launch', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      launchMode: 'case' | 'special'
      runSpecialTask: () => Promise<void>
      selectedSpecialTaskId: number | undefined
      selectedApkId: number | undefined
      launchDeviceId: number | null
    }

    vm.launchMode = 'special'
    vm.selectedSpecialTaskId = 9
    vm.selectedApkId = 21
    vm.launchDeviceId = 10
    await vm.runSpecialTask()

    expect(mobileTriggerTask).toHaveBeenCalledWith(9, {
      device_id: 10,
      apk_id: 21,
      app_package: 'com.example.karing',
    })

    wrapper.unmount()
  })

  it('does not let stale project data replace the latest project', async () => {
    const firstProjectCases = deferred<typeof androidCase[]>()
    const latestProjectCases = deferred<typeof androidCase[]>()
    caseList.mockReset()
      .mockImplementationOnce(() => firstProjectCases.promise)
      .mockImplementationOnce(() => latestProjectCases.promise)

    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      androidCases: Array<{ id: number; name: string }>
      handleProjectChange: (projectId: number) => Promise<void>
      selectedProjectId: number | null
    }

    const latestProjectLoad = vm.handleProjectChange(2)
    await flushPromises()
    expect(caseList).toHaveBeenCalledTimes(2)

    const latestCase = { ...androidCase, id: 202, name: '最新项目用例' }
    latestProjectCases.resolve([latestCase])
    await latestProjectLoad

    firstProjectCases.resolve([androidCase])
    await flushPromises()

    expect(vm.selectedProjectId).toBe(2)
    expect(vm.androidCases).toEqual([latestCase])

    wrapper.unmount()
  })

  it('opens the case drawer to create a new Android case', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      caseDrawerOpen: boolean
      editingCase: unknown
      openCreateCase: () => void
    }

    expect(vm.caseDrawerOpen).toBe(false)
    vm.openCreateCase()
    expect(vm.caseDrawerOpen).toBe(true)
    expect(vm.editingCase).toBeNull()

    wrapper.unmount()
  })

  it('opens the case drawer to edit the selected Android case', async () => {
    caseGet.mockResolvedValueOnce({ id: 101, name: 'Android 登录用例详情', case_type: 'android' })
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      caseDrawerOpen: boolean
      editingCase: { id: number; name: string } | null
      selectedCaseId: number | undefined
      openEditCase: () => Promise<void>
    }

    vm.selectedCaseId = 101
    await vm.openEditCase()

    expect(caseGet).toHaveBeenCalledWith(101)
    expect(vm.caseDrawerOpen).toBe(true)
    expect(vm.editingCase?.id).toBe(101)
    expect(vm.editingCase?.name).toBe('Android 登录用例详情')

    wrapper.unmount()
  })

  it('closes the drawer and refreshes cases when handleCaseSaved is called', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      caseDrawerOpen: boolean
      editingCase: unknown
      handleCaseSaved: () => Promise<void>
    }

    vm.caseDrawerOpen = true
    caseList.mockClear()
    await vm.handleCaseSaved()

    expect(vm.caseDrawerOpen).toBe(false)
    expect(vm.editingCase).toBeNull()
    expect(caseList).toHaveBeenCalledWith({ project_id: 1, case_type: 'android' })

    wrapper.unmount()
  })

  it('displays the empty guidance card when there are zero Android cases', async () => {
    caseList.mockResolvedValueOnce([])
    const wrapper = mountWorkbench()
    await flushPromises()

    expect(wrapper.find('.case-empty-card').exists()).toBe(true)
    expect(wrapper.find('.case-empty-card').text()).toContain('app_workbench.no_cases_title')
    expect(wrapper.find('.case-empty-card').text()).toContain('app_workbench.create_first_case')

    wrapper.unmount()
  })

  it('persists a draft when DeviceMirrorModal closes mid-recording without discarding', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()

    const mirrorModal = wrapper.findComponent({ name: 'DeviceMirrorModal' })
    const capturedSteps = [
      { action: 'click', name: '点击登录', params: { x: 120, y: 360 } },
      { action: 'assert_text_exists', name: '断言登录成功', params: { text: '欢迎' } },
    ]
    mirrorModal.vm.$emit('draft-captured', capturedSteps, { id: 10, serial: 'emulator-5554', model: 'Pixel 7' })
    await flushPromises()

    expect(recordingRecordCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        project_id: 1,
        kind: 'android',
        source: 'mirror',
        device_id: 10,
        device_serial: 'emulator-5554',
        status: 'draft',
        steps: capturedSteps,
      }),
    )
    const vm = wrapper.vm as unknown as {
      recordedDraftSteps: Array<{ action: string }>
      activeRecordingRecordId: number | null
    }
    expect(vm.recordedDraftSteps).toHaveLength(2)
    expect(vm.activeRecordingRecordId).toBe(77)
    wrapper.unmount()
  })

  it('hydrates recoverable Android draft after reload and restores into AndroidCaseDrawer', async () => {
    const serverDraft: RecordingRecordItem = {
      id: 55,
      project_id: 1,
      owner_id: 1,
      kind: 'android',
      source: 'mirror',
      session_id: 'app-55',
      title: '真机录制 · Pixel 7',
      status: 'draft',
      target_url: null,
      browser: null,
      device_id: 10,
      device_serial: 'emulator-5554',
      case_id: null,
      steps: [{ action: 'click', name: '点按登录', params: { resource_id: 'com.demo:id/login' } }],
      asset_ids: [],
      steps_count: 1,
      assertion_count: 0,
      artifacts: {},
      summary: { device_name: 'Pixel 7' },
      created_at: '2026-11-13T08:00:00Z',
      updated_at: '2026-11-13T08:01:00Z',
    }
    recordingRecordList.mockResolvedValue([serverDraft])

    const wrapper = mountWorkbench()
    await flushPromises()

    expect(recordingRecordList).toHaveBeenCalledWith({ project_id: 1, kind: 'android', limit: 30 })
    const vm = wrapper.vm as unknown as {
      appDraftCount: number
      recordedDraftSteps: Array<{ action: string }>
      activeRecordingRecordId: number | null
      caseDrawerOpen: boolean
      handleRestoreFromHistory: (record: RecordingRecordItem) => void
    }
    expect(vm.appDraftCount).toBe(1)
    expect(vm.recordedDraftSteps).toHaveLength(1)
    expect(vm.activeRecordingRecordId).toBe(55)

    vm.handleRestoreFromHistory(serverDraft)
    await flushPromises()

    expect(vm.caseDrawerOpen).toBe(true)
    const drawer = wrapper.findComponent({ name: 'AndroidCaseDrawer' })
    expect(drawer.props('recordingRecordId')).toBe(55)
    expect(drawer.props('initialSteps')).toEqual(serverDraft.steps)
    wrapper.unmount()
  })

  it('hydrates draft from localStorage fallback when backend has no unsaved App draft', async () => {
    saveLocalRecordingDraft({
      kind: 'android',
      projectId: 1,
      deviceSerial: 'emulator-5554',
      steps: [{ action: 'input_text', name: '输入账号', params: { text: 'alice' } }],
    })
    recordingRecordList.mockResolvedValue([])

    const wrapper = mountWorkbench()
    await flushPromises()

    const vm = wrapper.vm as unknown as { appDraftCount: number; recordedDraftSteps: Array<{ action: string }> }
    expect(vm.appDraftCount).toBe(1)
    expect(vm.recordedDraftSteps).toHaveLength(1)
    wrapper.unmount()
  })
})

describe('AppWorkbenchView device status polling', () => {
  let visibility: DocumentVisibilityState = 'visible'

  beforeEach(() => {
    vi.useFakeTimers()
    visibility = 'visible'
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visibility })
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    delete (document as unknown as Record<string, unknown>).visibilityState
  })

  it('refreshes device status every 15 seconds while visible and stops after unmount', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    expect(deviceList).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('.device-status-dot').map((dot) => dot.classes())).toEqual([
      expect.arrayContaining(['status-online']),
      expect.arrayContaining(['status-offline']),
    ])

    deviceList.mockResolvedValue([
      { id: 10, serial: 'emulator-5554', name: 'Pixel 7', model: 'Pixel 7', brand: 'Google', os_version: '14', sdk_version: '34', resolution: '1080x2400', status: 'offline', created_at: '', updated_at: '' },
      { id: 11, serial: 'offline-01', name: '备用机', model: 'Mi 12', brand: 'Xiaomi', os_version: '13', sdk_version: '33', status: 'offline', created_at: '', updated_at: '' },
    ])
    await vi.advanceTimersByTimeAsync(15000)
    await flushPromises()
    expect(deviceList).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('.device-status-dot.status-offline')).toHaveLength(2)

    visibility = 'hidden'
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(60000)
    expect(deviceList).toHaveBeenCalledTimes(2)

    wrapper.unmount()
    visibility = 'visible'
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(60000)
    expect(deviceList).toHaveBeenCalledTimes(2)
  })

  it('refreshes recoverable draft steps after AndroidCaseDrawer closes and avoids hijacking saved history', async () => {
    const initialDraft = {
      id: 55,
      project_id: 1,
      kind: 'android',
      source: 'mirror',
      session_id: 'app-draft-55',
      title: '旧草稿',
      status: 'draft',
      device_serial: 'emulator-5554',
      case_id: null,
      steps: [{ action: 'tap', name: '旧步骤', params: { x: 10, y: 20 } }],
      steps_count: 1,
      assertion_count: 0,
      asset_ids: [],
      artifacts: {},
      summary: {},
      created_at: '',
      updated_at: '',
    }
    const updatedDraft = {
      ...initialDraft,
      steps: [
        { action: 'tap', name: '旧步骤', params: { x: 10, y: 20 } },
        { action: 'assert_text_exists', name: '新增断言', params: { text: '欢迎' } },
      ],
      steps_count: 2,
      assertion_count: 1,
    }
    recordingRecordList.mockResolvedValueOnce([initialDraft]).mockResolvedValueOnce([updatedDraft])

    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      recordedDraftSteps: Array<{ action: string; name: string; params: Record<string, unknown> }>
      openRecordedDraft: () => Promise<void>
      closeCaseDrawer: () => void
    }
    expect(vm.recordedDraftSteps).toHaveLength(1)

    await vm.openRecordedDraft()
    vm.closeCaseDrawer()
    await flushPromises()
    expect(vm.recordedDraftSteps).toHaveLength(2)
    expect(vm.recordedDraftSteps[1].name).toBe('新增断言')

    const historyDrawer = wrapper.findComponent({ name: 'RecordingHistoryDrawer' })
    historyDrawer.vm.$emit('restore', {
      id: 303,
      project_id: 1,
      kind: 'android',
      source: 'mirror',
      session_id: 'saved-303',
      title: '已保存App历史',
      status: 'saved',
      device_serial: 'emulator-5554',
      case_id: 88,
      steps: [{ action: 'tap', name: '历史步骤', params: { x: 5, y: 6 } }],
      steps_count: 1,
      assertion_count: 0,
      asset_ids: [],
      artifacts: {},
      summary: {},
      created_at: '',
      updated_at: '',
    })
    await flushPromises()

    const drawer = wrapper.findComponent({ name: 'AndroidCaseDrawer' })
    expect(drawer.props('recordingRecordId')).toBeNull()
    wrapper.unmount()
  })
})
