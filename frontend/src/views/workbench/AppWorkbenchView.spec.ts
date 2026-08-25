import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AppWorkbenchView from './AppWorkbenchView.vue'

const {
  apkList,
  caseList,
  caseRun,
  deviceAcquireLease,
  deviceList,
  deviceWorkers,
  mobileListRuns,
  mobileListTasks,
  mobileTriggerTask,
  projectList,
  routerPush,
  routerReplace,
  runList,
} = vi.hoisted(() => ({
  apkList: vi.fn(),
  caseList: vi.fn(),
  caseRun: vi.fn(),
  deviceAcquireLease: vi.fn(),
  deviceList: vi.fn(),
  deviceWorkers: vi.fn(),
  mobileListRuns: vi.fn(),
  mobileListTasks: vi.fn(),
  mobileTriggerTask: vi.fn(),
  projectList: vi.fn(),
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
  MobileOutlined: true,
  PlayCircleOutlined: true,
  ReloadOutlined: true,
  SafetyCertificateOutlined: true,
  ThunderboltOutlined: true,
  ToolOutlined: true,
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'admin' } }),
}))
vi.mock('@/api', () => ({
  apkApi: { list: apkList },
  caseApi: { list: caseList, run: caseRun },
  deviceApi: {
    acquireLease: deviceAcquireLease,
    list: deviceList,
    workers: deviceWorkers,
    screenshot: vi.fn(),
  },
  mobileSpecialApi: {
    listRuns: mobileListRuns,
    listTasks: mobileListTasks,
    triggerTask: mobileTriggerTask,
  },
  projectApi: { list: projectList },
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
  AndroidOutlined: true,
  AppstoreOutlined: true,
  EyeOutlined: true,
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

beforeEach(() => {
  vi.clearAllMocks()
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
  mobileTriggerTask.mockResolvedValue({ id: 901 })
  deviceAcquireLease.mockResolvedValue({ device_id: 10, owner_label: 'app-workbench', acquired_at: '', heartbeat_at: '', expires_at: '2026-08-24T11:00:00Z', lease_token: 'lease-token-123456789' })
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
})
