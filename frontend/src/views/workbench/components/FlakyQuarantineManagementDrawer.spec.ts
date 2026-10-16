import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import FlakyQuarantineManagementDrawer from './FlakyQuarantineManagementDrawer.vue'
import { ciImpactApi } from '@/api/ciImpact'

const mockFlakyReport = {
  filter_id: 'flaky_demo_123',
  mode: 'auto_adaptive',
  total_cases_evaluated: 5,
  stable_cases_count: 3,
  flaky_cases_count: 2,
  isolated_cases_count: 1,
  retried_cases_count: 1,
  suppression_ratio_pct: 40.0,
  actionable_case_ids: [101, 102, 104, 105],
  quarantined_case_ids: [103],
  evaluations: [
    {
      case_id: 101,
      case_name: '订单结算优惠抵扣用例',
      is_flaky: false,
      flakiness_score: 0.0,
      failure_rate: 0.0,
      total_runs_analyzed: 10,
      action: 'normal_passthrough',
      suppression_reason: '测试用例历史执行稳固，未检出显著统计性抖动',
      retry_count_recommended: 0,
    },
    {
      case_id: 102,
      case_name: '下单收银台流程',
      is_flaky: true,
      flakiness_score: 0.40,
      failure_rate: 0.20,
      total_runs_analyzed: 10,
      action: 'retry_attached',
      suppression_reason: '自适应重试：用例存在中度抖动 (指数: 0.40)，附加自动重试',
      retry_count_recommended: 2,
    },
    {
      case_id: 103,
      case_name: '第三方跨境支付渠道回调',
      is_flaky: true,
      flakiness_score: 1.0,
      failure_rate: 0.50,
      total_runs_analyzed: 10,
      action: 'isolated_to_quarantine',
      suppression_reason: '自适应隔离：用例历史高频随机抖动 (指数: 1.00)，移至异步观察队列',
      retry_count_recommended: 0,
    },
  ],
  created_at: '2026-10-16T10:00:00Z',
}

vi.mock('@/api/ciImpact', () => ({
  ciImpactApi: {
    filterFlakyTests: vi.fn(),
    setGovernanceOverride: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  FilterOutlined: { template: '<span>Filter</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  SafetyCertificateOutlined: { template: '<span>Safety</span>' },
}))

describe('FlakyQuarantineManagementDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ciImpactApi.filterFlakyTests).mockResolvedValue({
      message: 'Flaky 用例自适应抑制完成',
      report: mockFlakyReport as any,
    })
    vi.mocked(ciImpactApi.setGovernanceOverride).mockResolvedValue({
      message: '治理覆盖策略已生效',
      case_id: 103,
      action: 'isolated_to_quarantine',
    })
  })

  it('renders drawer header, KPI cards, and evaluations table', async () => {
    const wrapper = mount(FlakyQuarantineManagementDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-progress': { template: '<div class="ant-progress" />' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-textarea': { template: '<textarea />' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.case_id" class="row">
                  <span class="case-name-col">{{ item.case_name }}</span>
                  <span class="reason-col">{{ item.suppression_reason }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 验证标题与统计指标
    expect(wrapper.text()).toContain('Flaky 抖动用例自适应抑制隔离引擎')
    expect(wrapper.text()).toContain('5')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('1')
    expect(wrapper.text()).toContain('40%')

    // 验证用例列表
    expect(wrapper.text()).toContain('订单结算优惠抵扣用例')
    expect(wrapper.text()).toContain('第三方跨境支付渠道回调')

    expect(ciImpactApi.filterFlakyTests).toHaveBeenCalled()
  })

  it('triggers governance override submission', async () => {
    const wrapper = mount(FlakyQuarantineManagementDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-progress': { template: '<div class="ant-progress" />' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-textarea': { template: '<textarea />' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleOverrideSubmit()

    expect(ciImpactApi.setGovernanceOverride).toHaveBeenCalledWith(expect.objectContaining({
      case_id: 103,
      action: 'isolated_to_quarantine',
    }))
  })
})
