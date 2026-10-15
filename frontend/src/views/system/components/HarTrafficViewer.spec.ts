import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import HarTrafficViewer from './HarTrafficViewer.vue'

const mockParseHar = vi.fn().mockResolvedValue({
  valid: true,
  total_requests: 3,
  failed_requests: 1,
  success_rate: 66.67,
  total_bytes_transferred: 1048576, // 1 MB
  avg_latency_ms: 250.0,
  domains_accessed: ['api.atp.io'],
  slowest_requests: [
    {
      index: 1,
      url: 'https://api.atp.io/v1/payments/verify',
      method: 'POST',
      status: 504,
      duration_ms: 3150.2,
      bytes: 510,
      is_failed: true,
    },
    {
      index: 0,
      url: 'https://api.atp.io/v1/cases/batch-run',
      method: 'POST',
      status: 200,
      duration_ms: 1420.0,
      bytes: 45650,
      is_failed: false,
    },
  ],
  entries_summary: [
    {
      index: 0,
      url: 'https://api.atp.io/v1/cases/batch-run',
      method: 'POST',
      status: 200,
      duration_ms: 1420.0,
      bytes: 45650,
      is_failed: false,
    },
    {
      index: 1,
      url: 'https://api.atp.io/v1/payments/verify',
      method: 'POST',
      status: 504,
      duration_ms: 3150.2,
      bytes: 510,
      is_failed: true,
    },
    {
      index: 2,
      url: 'https://api.atp.io/v1/auth/session',
      method: 'GET',
      status: 200,
      duration_ms: 85.0,
      bytes: 1560,
      is_failed: false,
    },
  ],
})

vi.mock('@/api/networkSimulation', () => ({
  networkSimulationApi: {
    parseHar: (har: unknown) => mockParseHar(har),
  },
}))

describe('HarTrafficViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders initial empty state and loads sample HAR on button click', async () => {
    const wrapper = mount(HarTrafficViewer, {
      global: {
        stubs: {
          'a-upload': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-card': { template: '<div><slot /></div>' },
          'a-statistic': true,
          'a-tag': { template: '<span><slot /></span>' },
          'a-radio-group': true,
          'a-radio-button': true,
          'a-input': true,
          'a-table': true,
          'a-empty': { template: '<div class="empty-stub"><slot /></div>' },
        },
      },
    })

    expect(wrapper.find('.empty-stub').exists()).toBe(true)

    const vm = wrapper.vm as unknown as {
      loadSampleHar: () => void
      parsedData: unknown
      filteredEntries: Array<{ url: string; is_failed: boolean }>
      statusFilter: 'all' | 'failed'
      searchKeyword: string
    }

    // Load sample HAR
    vm.loadSampleHar()
    await wrapper.vm.$nextTick()
    await Promise.resolve()

    expect(mockParseHar).toHaveBeenCalled()
    expect(vm.parsedData).toBeTruthy()
    expect(vm.filteredEntries.length).toBe(3)

    // Filter only failed
    vm.statusFilter = 'failed'
    expect(vm.filteredEntries.length).toBe(1)
    expect(vm.filteredEntries[0].url).toContain('payments/verify')

    // Filter by keyword
    vm.statusFilter = 'all'
    vm.searchKeyword = 'batch-run'
    expect(vm.filteredEntries.length).toBe(1)
    expect(vm.filteredEntries[0].url).toContain('batch-run')
  })
})
