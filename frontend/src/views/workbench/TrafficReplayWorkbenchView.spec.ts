import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import TrafficReplayWorkbenchView from './TrafficReplayWorkbenchView.vue'
import { trafficReplayApi } from '@/api/trafficReplay'

vi.mock('@/api/trafficReplay', () => ({
  trafficReplayApi: {
    listRecords: vi.fn().mockResolvedValue({
      total: 2,
      records: [
        {
          record_id: 'trf_order_001',
          trace_id: 'tr_mock_123',
          method: 'POST',
          path: '/api/v1/orders/checkout',
          status_code: 200,
          replayed_status_code: 200,
          consistency_score: 95.0,
          impact_level: 'NON_BREAKING',
          is_sanitized: true,
          response_body: { code: 200, order_id: 'OD_1001' },
          replayed_response_body: { code: 200, order_id: 'OD_1001' },
        },
      ],
    }),
    batchReplay: vi.fn().mockResolvedValue({
      message: '成功调度',
      dispatched_tasks: [{ task_id: 't_1', status: 'DISPATCHED' }],
    }),
    ingestMirrorTraffic: vi.fn().mockResolvedValue({
      should_record: true,
      reason: '命中',
      item: {
        record_id: 'trf_new_002',
        trace_id: 'tr_new_456',
        method: 'POST',
        path: '/api/v1/orders/checkout',
        status_code: 200,
        is_sanitized: true,
      },
    }),
  },
}))

const stubs = {
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-table': { template: '<div class="ant-table-stub"><slot /></div>' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-input-search': { template: '<input class="ant-input-search-stub" />' },
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-modal': { template: '<div class="ant-modal-stub"><slot /><slot name="footer" /></div>' },
}

describe('TrafficReplayWorkbenchView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page header and 4 Bento KPI cards', async () => {
    const wrapper = mount(TrafficReplayWorkbenchView, {
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('生产流量可信回放与变异演练工作台中枢')
    expect(wrapper.text()).toContain('94.6')
    expect(wrapper.text()).toContain('回放一致性平均得分')
    expect(wrapper.text()).toContain('镜像流量录制总量')
    expect(wrapper.text()).toContain('动态噪声自适应平滑率')
    expect(wrapper.text()).toContain('外部调用防击穿拦截')
  })

  it('fetches records on mount and handles batch replay', async () => {
    const wrapper = mount(TrafficReplayWorkbenchView, {
      global: { stubs },
    })
    await flushPromises()

    expect(trafficReplayApi.listRecords).toHaveBeenCalled()

    const batchBtn = wrapper.findAll('button').find((b) => b.text().includes('批量回放全部'))
    expect(batchBtn).toBeDefined()
    await batchBtn!.trigger('click')
    await flushPromises()

    expect(trafficReplayApi.batchReplay).toHaveBeenCalledWith(
      expect.objectContaining({
        record_ids: ['trf_order_001'],
      })
    )
  })

  it('opens diff inspection drawer and rule modal', async () => {
    const wrapper = mount(TrafficReplayWorkbenchView, {
      global: { stubs },
    })
    await flushPromises()

    const vm = wrapper.vm as any
    vm.openDiffDrawer(vm.trafficRecords[0])
    expect(vm.diffDrawerOpen).toBe(true)

    vm.openNewRuleModal()
    expect(vm.ruleModalOpen).toBe(true)
  })
})
