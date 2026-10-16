import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import GoldenResponseBaselineDashboardView from './GoldenResponseBaselineDashboardView.vue'
import { goldenBaselineApi } from '@/api/trafficGateway'

const mockBaselines = [
  {
    baseline_id: 'gbl_order_001',
    endpoint: 'POST /api/v1/orders/checkout',
    protocol: 'HTTP',
    version_tag: 'v1.0-prod-gold',
    description: '官方订单结算黄金基线快照',
    golden_request_body: '{"order_id": 10001}',
    golden_response_status: 200,
    golden_response_body: '{"code": 0, "status": "PAID"}',
    tolerance_threshold_pct: 95.0,
    is_active: true,
    tags: {},
    created_at: '2026-10-16T10:00:00Z',
    updated_at: '2026-10-16T10:00:00Z',
  },
  {
    baseline_id: 'gbl_user_002',
    endpoint: 'GET /api/v1/users/profile',
    protocol: 'HTTP',
    version_tag: 'v1.0-prod-gold',
    description: '官方用户资料查询黄金基线',
    golden_request_body: '',
    golden_response_status: 200,
    golden_response_body: '{"code": 0, "username": "alice"}',
    tolerance_threshold_pct: 90.0,
    is_active: true,
    tags: {},
    created_at: '2026-10-16T10:05:00Z',
    updated_at: '2026-10-16T10:05:00Z',
  },
]

const mockBatchReport = {
  batch_id: 'bvr_test_001',
  total_verified: 2,
  passed_count: 2,
  drifted_count: 0,
  pass_rate_pct: 100.0,
  created_at: '2026-10-16T13:00:00Z',
  results: [],
}

vi.mock('@/api/trafficGateway', () => ({
  goldenBaselineApi: {
    listBaselines: vi.fn(),
    listBatchReports: vi.fn(),
    getBaseline: vi.fn(),
    createBaseline: vi.fn(),
    deleteBaseline: vi.fn(),
    verifySingle: vi.fn(),
    batchVerify: vi.fn(),
    getBatchReport: vi.fn(),
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
  SafetyCertificateOutlined: { template: '<span>Safety</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  PlayCircleOutlined: { template: '<span>Play</span>' },
  PlusOutlined: { template: '<span>Plus</span>' },
  AuditOutlined: { template: '<span>Audit</span>' },
}))

describe('GoldenResponseBaselineDashboardView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(goldenBaselineApi.listBaselines).mockResolvedValue({
      total: 2,
      baselines: mockBaselines as any,
    })
    vi.mocked(goldenBaselineApi.listBatchReports).mockResolvedValue({
      total: 1,
      reports: [mockBatchReport as any],
    })
    vi.mocked(goldenBaselineApi.verifySingle).mockResolvedValue({
      message: '回归校验完成',
      result: {
        verification_id: 'vrf_1',
        baseline_id: 'gbl_order_001',
        version_tag: 'v1.0-prod-gold',
        endpoint: 'POST /api/v1/orders/checkout',
        actual_status_code: 200,
        similarity_score_pct: 100.0,
        tolerance_threshold_pct: 95.0,
        passed: true,
        diff_report_id: 'diff_1',
        critical_diffs_count: 0,
        warning_diffs_count: 0,
        alert_level: 'NORMAL',
        summary: '校验通过',
        verified_at: '2026-10-16T13:00:00Z',
      } as any,
    })
  })

  it('renders hero title, batch report banner with 100%, and baselines table', async () => {
    const wrapper = mount(GoldenResponseBaselineDashboardView, {
      global: {
        stubs: {
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-input': { template: '<input />' },
          'a-input-search': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-slider': { template: '<div class="ant-slider" />' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.baseline_id" class="row">
                  <span class="endpoint">{{ item.endpoint }}</span>
                  <span class="version">{{ item.version_tag }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查标题与 API 调用
    expect(wrapper.text()).toContain('接口黄金响应基线版本化管理与回归偏离大盘')
    expect(goldenBaselineApi.listBaselines).toHaveBeenCalled()
    expect(goldenBaselineApi.listBatchReports).toHaveBeenCalled()

    // 检查横幅
    expect(wrapper.text()).toContain('100.0%')
    expect(wrapper.text()).toContain('全量达标')
    expect(wrapper.text()).toContain('bvr_test_001')

    // 检查表格基线
    expect(wrapper.text()).toContain('POST /api/v1/orders/checkout')
    expect(wrapper.text()).toContain('GET /api/v1/users/profile')
  })

  it('supports applying critical drift preset', async () => {
    const wrapper = mount(GoldenResponseBaselineDashboardView, {
      global: {
        stubs: {
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-input': { template: '<input />' },
          'a-input-search': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-slider': { template: '<div class="ant-slider" />' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-textarea': { template: '<textarea />' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    vm.applyPreset('critical_drift')
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('50.0%')
    expect(wrapper.text()).toContain('偏离报警: 2 处')
    expect(wrapper.text()).toContain('CRITICAL DRIFT')
  })
})
