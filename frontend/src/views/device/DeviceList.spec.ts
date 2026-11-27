import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import DeviceList from './DeviceList.vue'

const {
  deviceList,
  deviceWorkers,
  deviceScan,
  deviceScanStatus,
  deviceUpdate,
  deviceDelete,
  deviceConnect,
  deviceClaim,
  messageError,
  messageInfo,
  messageSuccess,
  probeLocalAndroidWorker,
  authState,
} = vi.hoisted(() => ({
  deviceList: vi.fn(),
  deviceWorkers: vi.fn(),
  deviceScan: vi.fn(),
  deviceScanStatus: vi.fn(),
  deviceUpdate: vi.fn(),
  deviceDelete: vi.fn(),
  deviceConnect: vi.fn(),
  deviceClaim: vi.fn(),
  messageError: vi.fn(),
  messageInfo: vi.fn(),
  messageSuccess: vi.fn(),
  probeLocalAndroidWorker: vi.fn(),
  authState: { user: { role: 'admin' } },
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => authState }))
vi.mock('@/runtimeMode', () => ({ getRuntimeMode: () => ({ mode: 'server' }) }))
vi.mock('ant-design-vue', () => ({ message: { error: messageError, info: messageInfo, success: messageSuccess } }))
vi.mock('@/utils/localAndroidWorker', () => ({
  probeLocalAndroidWorker,
}))
vi.mock('@/api', () => ({
  deviceApi: {
    list: deviceList,
    workers: deviceWorkers,
    scan: deviceScan,
    scanStatus: deviceScanStatus,
    update: deviceUpdate,
    delete: deviceDelete,
    connect: deviceConnect,
    claim: deviceClaim,
    disconnectionRecovery: vi.fn().mockResolvedValue({}),
    forceTakeoverLease: vi.fn().mockResolvedValue({}),
    screenshot: vi.fn(),
  },
}))

const TableStub = defineComponent({
  name: 'ATable',
  props: ['dataSource'],
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        (props.dataSource || []).map((record: Record<string, unknown>) =>
          h('div', { class: 'device-row' }, [
            slots.bodyCell?.({ column: { key: 'action' }, record }),
            slots.bodyCell?.({ column: { key: 'status' }, record }),
          ]),
        ),
      )
  },
})

const passthrough = (name: string) =>
  defineComponent({ name, setup: (_p, { slots }) => () => h('div', slots.default?.()) })

function mountDeviceList() {
  return mount(DeviceList, {
    global: {
      stubs: {
        ATable: TableStub,
        AInputSearch: defineComponent({
          name: 'AInputSearch',
          props: ['value'],
          emits: ['update:value'],
          setup: (p, { emit }) => () => h('input', { 'data-test': 'search', value: p.value, onInput: (e: Event) => emit('update:value', (e.target as HTMLInputElement).value) }),
        }),
        AButton: defineComponent({
          name: 'AButton',
          emits: ['click'],
          setup: (_p, { slots, emit }) => () => h('button', { onClick: () => emit('click') }, slots.default?.()),
        }),
        ABadge: defineComponent({
          name: 'ABadge',
          props: ['status', 'text'],
          setup: (props) => () => h('span', { 'data-test': 'badge', 'data-status': props.status }, String(props.text)),
        }),
        APopconfirm: defineComponent({
          name: 'APopconfirm',
          emits: ['confirm'],
          setup: (_p, { slots, emit }) => () => h('div', { 'data-test': 'delete-confirm', onClick: () => emit('confirm') }, slots.default?.()),
        }),
        ARow: passthrough('ARow'),
        ACol: passthrough('ACol'),
        ACard: passthrough('ACard'),
        ASelect: passthrough('ASelect'),
        AModal: passthrough('AModal'),
        AForm: passthrough('AForm'),
        AFormItem: passthrough('AFormItem'),
        AInput: passthrough('AInput'),
        ATextarea: passthrough('ATextarea'),
        ASpace: passthrough('ASpace'),
        ReloadOutlined: true,
        EyeOutlined: true,
      },
    },
  })
}

const DEVICES = [
  { id: 1, name: 'Pixel-7', brand: 'Google', model: 'Pixel 7', serial: 'PX7ABC', os_version: 'Android 14', resolution: '1080x2400', status: 'online', last_seen: '2026-07-10T09:00:00Z' },
  { id: 2, name: 'Galaxy-S23', brand: 'Samsung', model: 'S23', serial: 'SGS23X', os_version: 'Android 13', resolution: '1080x2340', status: 'offline', last_seen: '2026-07-09T08:00:00Z' },
  { id: 3, name: 'Mi-13', brand: 'Xiaomi', model: 'Mi13', serial: 'MI13YZ', os_version: 'Android 13', resolution: '1440x3200', status: 'busy', last_seen: '2026-07-08T07:00:00Z' },
]

// 设备页会挂可见性监听和轮询定时器，每个用例结束都卸载，避免残留实例串扰后续用例
enableAutoUnmount(afterEach)

beforeEach(() => {
  vi.unstubAllEnvs()
  vi.clearAllMocks()
  authState.user = { role: 'admin' }
  window.localStorage.clear()
  probeLocalAndroidWorker.mockResolvedValue(null)
  deviceList.mockResolvedValue(DEVICES)
  deviceWorkers.mockResolvedValue([])
  deviceScan.mockResolvedValue({ status: 'completed', scan_id: null, devices: DEVICES })
  deviceScanStatus.mockResolvedValue({ status: 'completed', scan_id: 'scan-id', devices: DEVICES })
  deviceUpdate.mockResolvedValue({})
  deviceDelete.mockResolvedValue({})
  deviceConnect.mockResolvedValue({ success: true, message: 'ok', serial: '192.168.1.10:5555' })
  deviceClaim.mockResolvedValue({})
})

describe('DeviceList mount', () => {
  it('loads devices on mount and renders status stats and badges', async () => {
    const wrapper = mountDeviceList()
    await flushPromises()

    expect(deviceList).toHaveBeenCalledWith(undefined)
    const stats = wrapper.findAll('.pill-count').map((item) => item.text())
    expect(stats).toEqual(['3', '1', '1', '1'])
    const badges = wrapper.findAll('[data-test="badge"]').map((b) => b.attributes('data-status'))
    expect(badges).toEqual(expect.arrayContaining(['success', 'default', 'processing']))
  })

  it('keeps a real empty device inventory empty when prototype data is disabled', async () => {
    vi.stubEnv('VITE_ENABLE_PROTOTYPE_DATA', 'false')
    deviceList.mockResolvedValue([])

    const wrapper = mountDeviceList()
    await flushPromises()

    expect(wrapper.findAll('.device-card-item')).toHaveLength(0)
    expect(wrapper.find('.empty-matrix-card').exists()).toBe(true)
  })

  it('does not display fabricated owner, agent, battery, or device defaults', async () => {
    deviceList.mockResolvedValue([{ ...DEVICES[0], os_version: null, resolution: null }])
    const wrapper = mountDeviceList()
    await flushPromises()

    expect(wrapper.find('.user-val').text()).toBe('--')
    expect(wrapper.find('.agent-val').text()).toBe('--')
    expect(wrapper.find('.device-specs-sheet').text()).not.toContain('85%')
    expect(wrapper.find('.device-specs-sheet').text()).not.toContain('1080 × 2376')
  })

  it('filters devices by keyword across name/brand/model/serial', async () => {
    const wrapper = mountDeviceList()
    await flushPromises()

    await wrapper.find('[data-test="search"]').setValue('samsung')
    await flushPromises()
    expect(wrapper.findAll('.device-row')).toHaveLength(1)

    await wrapper.find('[data-test="search"]').setValue('MI13YZ') // 按序列号
    await flushPromises()
    expect(wrapper.findAll('.device-row')).toHaveLength(1)

    await wrapper.find('[data-test="search"]').setValue('')
    await flushPromises()
    expect(wrapper.findAll('.device-row')).toHaveLength(3)
  })

  it('scans for devices and surfaces the result count', async () => {
    const wrapper = mountDeviceList()
    await flushPromises()

    // header 的第一个按钮是 scan
    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()

    expect(deviceScan).toHaveBeenCalledOnce()
    expect(messageSuccess).toHaveBeenCalled()
  })

  it('polls a queued Android Worker scan before reporting completion', async () => {
    vi.useFakeTimers()
    try {
      deviceScan.mockResolvedValue({ status: 'queued', scan_id: '550e8400-e29b-41d4-a716-446655440000', devices: [] })
      deviceScanStatus
        .mockResolvedValueOnce({ status: 'running', scan_id: 'scan-id', devices: [] })
        .mockResolvedValueOnce({ status: 'completed', scan_id: 'scan-id', devices: DEVICES })

      const wrapper = mountDeviceList()
      await flushPromises()
      const clickPromise = wrapper.findAll('button')[0].trigger('click')
      await flushPromises()
      expect(messageInfo).toHaveBeenCalled()

      await vi.advanceTimersByTimeAsync(500)
      await flushPromises()
      await vi.advanceTimersByTimeAsync(500)
      await clickPromise

      expect(deviceScanStatus).toHaveBeenCalledWith('550e8400-e29b-41d4-a716-446655440000')
      expect(messageSuccess).toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('handles partial_failed aggregate worker scan without throwing fatal error', async () => {
    vi.useFakeTimers()
    try {
      deviceScan.mockResolvedValue({ status: 'queued', scan_id: 'agg-550e8400-e29b-41d4-a716-446655440000', devices: [] })
      deviceScanStatus.mockResolvedValueOnce({
        status: 'partial_failed',
        scan_id: 'agg-550e8400-e29b-41d4-a716-446655440000',
        completed_workers: 1,
        failed_workers: 1,
        total_workers: 2,
        devices: DEVICES,
      })

      const wrapper = mountDeviceList()
      await flushPromises()
      deviceList.mockClear()
      messageInfo.mockClear()

      const clickPromise = wrapper.findAll('button')[0].trigger('click')
      await flushPromises()
      await vi.advanceTimersByTimeAsync(500)
      await clickPromise

      expect(messageError).not.toHaveBeenCalled()
      expect(messageInfo).toHaveBeenCalled()
      expect(wrapper.findAll('.device-card-item')).toHaveLength(3)
      wrapper.unmount()
    } finally {
      vi.useRealTimers()
    }
  })

  it('deletes a device via the row action and reloads', async () => {
    const wrapper = mountDeviceList()
    await flushPromises()
    deviceList.mockClear()

    await wrapper.find('[data-test="delete-confirm"]').trigger('click')
    await flushPromises()

    expect(deviceDelete).toHaveBeenCalledWith(1)
    expect(messageSuccess).toHaveBeenCalled()
    expect(deviceList).toHaveBeenCalled()
  })

  it('surfaces a message when device load fails', async () => {
    deviceList.mockRejectedValueOnce(new Error('adb down'))
    mountDeviceList()
    await flushPromises()
    expect(messageError).toHaveBeenCalled()
  })

  it('auto-selects the local Android Worker when loopback identity matches an online worker', async () => {
    deviceWorkers.mockResolvedValue([
      { worker_id: 'android-win-other', hostname: 'OTHER', status: 'online' },
      { worker_id: 'android-win-local', hostname: 'LOCAL-PC', status: 'online' },
    ])
    probeLocalAndroidWorker.mockResolvedValue({
      worker_id: 'android-win-local',
      hostname: 'LOCAL-PC',
      adb_ok: true,
    })

    const wrapper = mountDeviceList()
    await flushPromises()

    expect(window.localStorage.getItem('atp:selected_android_worker_id')).toBe('android-win-local')
    expect(deviceList).toHaveBeenLastCalledWith({ worker_id: 'android-win-local' })
    expect(wrapper.text()).toContain('本机 ADB: android-win-local')

    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()
    expect(deviceScan).toHaveBeenCalledWith('android-win-local')
  })
})

describe('DeviceList status polling', () => {
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

  it('re-reads the device list every 15 seconds so an unplugged device shows offline', async () => {
    const wrapper = mountDeviceList()
    await flushPromises()
    expect(deviceList).toHaveBeenCalledTimes(1)

    deviceList.mockResolvedValue([{ ...DEVICES[0], status: 'offline' }, DEVICES[1], DEVICES[2]])
    await vi.advanceTimersByTimeAsync(15000)
    await flushPromises()

    expect(deviceList).toHaveBeenCalledTimes(2)
    expect(deviceList).toHaveBeenLastCalledWith(undefined)
    expect(deviceScan).not.toHaveBeenCalled()
    expect(wrapper.findAll('.pill-count').map((item) => item.text())).toEqual(['3', '0', '1', '2'])
    wrapper.unmount()
  })

  it('keeps the current list without an error toast when a background refresh fails', async () => {
    const wrapper = mountDeviceList()
    await flushPromises()

    deviceList.mockRejectedValueOnce(new Error('network'))
    await vi.advanceTimersByTimeAsync(15000)
    await flushPromises()

    expect(messageError).not.toHaveBeenCalled()
    expect(wrapper.findAll('.pill-count').map((item) => item.text())).toEqual(['3', '1', '1', '1'])
    wrapper.unmount()
  })

  it('pauses while the page is hidden and resumes when it becomes visible', async () => {
    const wrapper = mountDeviceList()
    await flushPromises()

    visibility = 'hidden'
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(60000)
    expect(deviceList).toHaveBeenCalledTimes(1)

    visibility = 'visible'
    document.dispatchEvent(new Event('visibilitychange'))
    await flushPromises()
    expect(deviceList).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('stops polling after unmount', async () => {
    const wrapper = mountDeviceList()
    await flushPromises()
    wrapper.unmount()

    await vi.advanceTimersByTimeAsync(60000)
    expect(deviceList).toHaveBeenCalledTimes(1)
  })
})

describe('DeviceList RBAC, table filter, and remote worker selection', () => {
  it('binds table rows to displayDevices and restricts claim to admin while sending explicit worker_id on remote connect', async () => {
    deviceWorkers.mockResolvedValue([{ worker_id: 'win-worker-1', hostname: 'WIN-1', status: 'online' }])
    deviceList.mockResolvedValue([
      { id: 1, serial: 'emu-online', name: 'OnePlus', brand: 'OnePlus', model: '12', os_version: '14', status: 'online', worker_id: null },
      { id: 2, serial: 'emu-off', name: 'Pixel', brand: 'Google', model: '7', os_version: '13', status: 'offline', worker_id: 'win-worker-1' },
    ])

    // 1. engineer user must NOT see Claim button
    authState.user = { role: 'engineer' }
    const wrapper = mountDeviceList()
    await flushPromises()
    const vm = wrapper.vm as unknown as {
      setStatusPill: (status: 'all' | 'online' | 'busy' | 'offline') => void
      isAdmin: boolean
      remoteForm: { host: string; port: number; worker_id?: string }
      openRemoteConnectModal: () => void
      handleRemoteConnect: () => Promise<void>
    }
    expect(vm.isAdmin).toBe(false)
    expect(wrapper.findAll('.device-row')).toHaveLength(2)

    // Filtering via status pill must update table view (.device-row), not only matrix cards
    vm.setStatusPill('online')
    await flushPromises()
    expect(wrapper.findAll('.device-row')).toHaveLength(1)

    // Remote connect uses explicit worker_id
    vm.openRemoteConnectModal()
    vm.remoteForm.host = '10.1.2.3'
    vm.remoteForm.worker_id = 'win-worker-1'
    await vm.handleRemoteConnect()
    expect(deviceConnect).toHaveBeenCalledWith({
      host: '10.1.2.3',
      port: 5555,
      worker_id: 'win-worker-1',
    })
    wrapper.unmount()
  })

  it('supports disconnection recovery and admin force takeover lease', async () => {
    authState.user = { role: 'admin' }
    deviceList.mockResolvedValue([
      { id: 1, serial: 'emu-1', name: 'OnePlus', brand: 'OnePlus', model: '12', os_version: '14', status: 'busy', worker_id: null },
    ])
    const apiMod = await import('@/api')
    const wrapper = mountDeviceList()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleDisconnectionRecovery({ id: 1 })
    expect(apiMod.deviceApi.disconnectionRecovery).toHaveBeenCalledWith(1)

    vm.openForceTakeoverModal({ id: 1 })
    vm.takeoverForm.ttl_seconds = 600
    vm.takeoverForm.reason = '调试卡死恢复'
    await vm.handleForceTakeover()
    expect(apiMod.deviceApi.forceTakeoverLease).toHaveBeenCalledWith(1, { ttl_seconds: 600, reason: '调试卡死恢复' })
    wrapper.unmount()

    // tester role must NOT operate disconnection recovery or admin force takeover
    vi.clearAllMocks()
    authState.user = { role: 'tester' }
    const testerWrapper = mountDeviceList()
    await flushPromises()
    const testerVm = testerWrapper.vm as any
    expect(testerVm.canOperateDevices).toBe(false)
    await testerVm.handleDisconnectionRecovery({ id: 1 })
    expect(apiMod.deviceApi.disconnectionRecovery).not.toHaveBeenCalled()
    testerWrapper.unmount()
  })
})
