import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import PrecisionSelectionDiffModal from './PrecisionSelectionDiffModal.vue'

const stubs = {
  'a-modal': {
    props: ['title'],
    template: '<div class="ant-modal-stub"><h3>{{ title }}</h3><slot /><slot name="footer" /></div>',
  },
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-tabs': { template: '<div class="ant-tabs-stub"><slot /></div>' },
  'a-tab-pane': { template: '<div class="ant-tab-pane-stub"><slot /></div>' },
  'a-table': { template: '<div class="ant-table-stub"><slot /></div>' },
}

describe('PrecisionSelectionDiffModal.vue', () => {
  const sampleAnalysis = {
    analysis_id: 'prec_analysis_001',
    changed_symbols: ['calculate_discount'],
    impacted_endpoints_count: 2,
    impacted_cases_count: 3,
    total_cases_in_suite: 100,
    regression_reduction_ratio: 0.97,
    estimated_time_saved_seconds: 970.0,
    impacted_cases: [
      {
        case_id: 'case_order_checkout_flow',
        case_name: '收银台正常加购下单主流程',
        priority: 'P0',
        execution_cost_seconds: 15.0,
        impacted_by_endpoints: ['POST /api/v1/orders/checkout'],
      },
    ],
  }

  const sampleDiff = {
    symbols: [
      {
        symbol_id: 'sym_1',
        symbol_name: 'calculate_discount',
        qualified_name: 'discount.calculate_discount',
        file_path: 'backend/app/services/discount.py',
        change_type: 'SIGNATURE_CHANGED',
        severity: 'CRITICAL',
      },
    ],
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders modal with metrics, reduction ratio, and case recommendation', async () => {
    const wrapper = mount(PrecisionSelectionDiffModal, {
      props: {
        open: true,
        analysisResult: sampleAnalysis,
        diffReport: sampleDiff,
      },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('增量精准测试用例推荐与影响分析对比中枢')
    expect(wrapper.text()).toContain('97.0%')
    expect(wrapper.text()).toContain('用例裁剪节省率')
    expect(wrapper.text()).toContain('16.2m')
  })

  it('handles start precision regression click and emits startRegression', async () => {
    const wrapper = mount(PrecisionSelectionDiffModal, {
      props: {
        open: true,
        analysisResult: sampleAnalysis,
        diffReport: sampleDiff,
      },
      global: { stubs },
    })
    await flushPromises()

    const startBtn = wrapper.findAll('button').find((b) => b.text().includes('一键派发增量精准回归'))
    expect(startBtn).toBeDefined()
    await startBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.emitted('startRegression')).toBeTruthy()
  })
})
