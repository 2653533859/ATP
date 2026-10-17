import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import TrafficDiffInspectionDrawer from './TrafficDiffInspectionDrawer.vue'

const stubs = {
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-table': { template: '<div class="ant-table-stub"><slot /></div>' },
}

describe('TrafficDiffInspectionDrawer.vue', () => {
  const sampleRecord = {
    record_id: 'rec_order_999',
    method: 'POST',
    path: '/api/v1/orders/checkout',
    status_code: 200,
    response_body: { code: 200, order_id: 'OD_1001', amount: 99.0 },
    replayed_response_body: { code: 200, order_id: 'OD_1001', amount: 105.0 },
  }

  const sampleDiffReport = {
    replayed_status_code: 200,
    effective_diff_count: 1,
    suppressed_noise_count: 1,
    diffs: [
      {
        diff_id: 'd_amount',
        category: 'VALUE_MISMATCH',
        severity: 'MINOR',
        json_path: '$.amount',
        baseline_value: 99.0,
        replayed_value: 105.0,
        is_noise: false,
      },
      {
        diff_id: 'd_time',
        category: 'VALUE_MISMATCH',
        severity: 'MINOR',
        json_path: '$.created_at',
        baseline_value: '2026-10-17T10:00:00Z',
        replayed_value: '2026-10-17T10:00:05Z',
        is_noise: true,
      },
    ],
  }

  const sampleEvaluation = {
    consistency_score: 93.0,
    verdict: 'WARN_PERMISSIVE',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer header, score, and diff view correctly', async () => {
    const wrapper = mount(TrafficDiffInspectionDrawer, {
      props: {
        open: true,
        recordData: sampleRecord,
        diffReport: sampleDiffReport,
        evaluationResult: sampleEvaluation,
      },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('93.0')
    expect(wrapper.text()).toContain('WARN_PERMISSIVE')
    expect(wrapper.text()).toContain('/api/v1/orders/checkout')
    expect(wrapper.text()).toContain('生产录制基线响应')
    expect(wrapper.text()).toContain('线下实际回放响应')
  })

  it('handles update baseline click', async () => {
    const wrapper = mount(TrafficDiffInspectionDrawer, {
      props: {
        open: true,
        recordData: sampleRecord,
        diffReport: sampleDiffReport,
        evaluationResult: sampleEvaluation,
      },
      global: { stubs },
    })
    await flushPromises()

    const updateBtn = wrapper.findAll('button').find((b) => b.text().includes('采纳回放为新基线'))
    expect(updateBtn).toBeDefined()
    await updateBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('updatedBaseline')).toEqual([['rec_order_999']])
  })
})
