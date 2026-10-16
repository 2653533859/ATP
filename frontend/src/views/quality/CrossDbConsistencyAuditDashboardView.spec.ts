import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CrossDbConsistencyAuditDashboardView from './CrossDbConsistencyAuditDashboardView.vue'
import { crossDbAuditApi } from '@/api/distributedConsistency'

const mockReconciledReport = {
  report_id: 'aud_test_101',
  rule_id: 'r_test_1',
  rule_name: 'order-service与pay-service双向对账',
  verdict: 'RECONCILED',
  consistency_rate_pct: 100.0,
  total_records_checked: 2,
  consistent_records_count: 2,
  mismatched_records_count: 0,
  missing_in_target_count: 0,
  missing_in_source_count: 0,
  value_mismatches_count: 0,
  diff_records: [],
  verdict_summary: '跨库双向对账全部通过（一致率 100.0%），共稽核 2 条数据记录，零差异。',
  audited_at: '2026-10-16T12:00:00Z',
}

const mockMissingReport = {
  report_id: 'aud_test_102',
  rule_id: 'r_test_2',
  rule_name: 'order-service与pay-service双向对账',
  verdict: 'CRITICAL',
  consistency_rate_pct: 50.0,
  total_records_checked: 2,
  consistent_records_count: 1,
  mismatched_records_count: 1,
  missing_in_target_count: 1,
  missing_in_source_count: 0,
  value_mismatches_count: 0,
  diff_records: [
    {
      join_key_value: 'ord_1002',
      category: 'MISSING_IN_TARGET',
      field_diffs: [],
      remediation_sql: "INSERT INTO payments (order_id, amount, status, user_id) VALUES ('ord_1002', 350.0, 'PAID', 'u_3');",
    },
  ],
  verdict_summary: '跨库最终一致性严重破坏 (50.0% < 98.0%)！检出 1 处数据撕裂。',
  audited_at: '2026-10-16T12:05:00Z',
}

vi.mock('@/api/distributedConsistency', () => ({
  crossDbAuditApi: {
    registerRule: vi.fn(),
    listRules: vi.fn(),
    deleteRule: vi.fn(),
    executeAudit: vi.fn(),
    listReports: vi.fn(),
    getReport: vi.fn(),
    clearStore: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  DatabaseOutlined: { template: '<span>Database</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
}))

describe('CrossDbConsistencyAuditDashboardView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(crossDbAuditApi.executeAudit).mockResolvedValue({
      message: '跨库数据一致性稽核完成',
      report: mockReconciledReport as any,
    })
  })

  it('renders page hero, reconciled verdict banner, 100% rate, and empty diff', async () => {
    const wrapper = mount(CrossDbConsistencyAuditDashboardView, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-empty': { template: '<div class="ant-empty">Empty</div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(crossDbAuditApi.executeAudit).toHaveBeenCalled()
    expect(wrapper.text()).toContain('跨微服务异构数据源最终一致性双向稽核对账大盘')

    // 检查裁决横幅
    expect(wrapper.text()).toContain('RECONCILED')
    expect(wrapper.text()).toContain('100%')
    expect(wrapper.text()).toContain('2') // total records checked

    // 检查空差异状态
    expect(wrapper.text()).toContain('Empty')
  })

  it('switches preset to missing_target and checks diff table with remediation SQL', async () => {
    vi.mocked(crossDbAuditApi.executeAudit).mockResolvedValueOnce({
      message: '跨库数据一致性稽核完成',
      report: mockReconciledReport as any,
    }).mockResolvedValueOnce({
      message: '跨库数据一致性稽核完成',
      report: mockMissingReport as any,
    })

    const wrapper = mount(CrossDbConsistencyAuditDashboardView, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-empty': { template: '<div class="ant-empty">Empty</div>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.join_key_value" class="row">
                  <span class="key">{{ item.join_key_value }}</span>
                  <span class="cat">{{ item.category }}</span>
                  <span class="sql">{{ item.remediation_sql }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('missing_target')
    await flushPromises()

    expect(crossDbAuditApi.executeAudit).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('CRITICAL')
    expect(wrapper.text()).toContain('50%')
    expect(wrapper.text()).toContain('ord_1002')
    expect(wrapper.text()).toContain('MISSING_IN_TARGET')
    expect(wrapper.text()).toContain('INSERT INTO payments')
  })
})
