import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import NetworkProfileDrawer from './NetworkProfileDrawer.vue'

const mockGetProfiles = vi.fn().mockResolvedValue({
  '2g_edge': {
    name: '2G (EDGE 良好)',
    latency_ms: 300,
    download_kbps: 250,
    upload_kbps: 200,
    packet_loss_percent: 2.0,
    offline: false,
    description: '高延迟窄带',
  },
  '4g_lte': {
    name: '4G (LTE 城市)',
    latency_ms: 50,
    download_kbps: 30000,
    upload_kbps: 15000,
    packet_loss_percent: 0.5,
    offline: false,
    description: '常规蜂窝网络',
  },
})

const mockEvaluate = vi.fn().mockResolvedValue({
  profile_id: '2g_edge',
  is_dropped: false,
  estimated_delay_seconds: 2.345,
  offline: false,
  cdp_conditions: {
    offline: false,
    latency: 300,
    downloadThroughput: 32000,
    uploadThroughput: 25600,
  },
  adb_commands: [
    ['adb', 'shell', 'tc', 'qdisc', 'add', 'dev', 'wlan0', 'root', 'netem', 'delay', '300ms'],
  ],
})

vi.mock('@/api/networkSimulation', () => ({
  networkSimulationApi: {
    getProfiles: () => mockGetProfiles(),
    evaluate: (payload: unknown) => mockEvaluate(payload),
    getScheduleConfig: vi.fn(),
  },
}))

describe('NetworkProfileDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer and loads preset network profiles when visible', async () => {
    const wrapper = mount(NetworkProfileDrawer, {
      props: { visible: true },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-divider': { template: '<hr />' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-input-number': true,
          'a-select': true,
          'a-select-option': true,
          'a-button': { template: '<button><slot /></button>' },
          'a-statistic': true,
        },
      },
    })

    expect(mockGetProfiles).toHaveBeenCalled()
    const vm = wrapper.vm as unknown as {
      visible: boolean
      selectedProfileId: string
      selectProfile: (id: string) => void
    }
    expect(vm.visible).toBe(true)

    // Trigger profile selection
    vm.selectProfile('4g_lte')
    expect(vm.selectedProfileId).toBe('4g_lte')
    expect(mockEvaluate).toHaveBeenCalledWith(
      expect.objectContaining({ profile_id: '4g_lte' }),
    )
  })

  it('emits update:visible false on close', async () => {
    const wrapper = mount(NetworkProfileDrawer, {
      props: { visible: true },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': true,
          'a-divider': true,
          'a-form': true,
          'a-form-item': true,
          'a-row': true,
          'a-col': true,
          'a-input-number': true,
          'a-select': true,
          'a-select-option': true,
          'a-button': true,
          'a-statistic': true,
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      handleClose: () => void
    }
    vm.handleClose()
    expect(wrapper.emitted('update:visible')).toBeTruthy()
    expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
  })
})
