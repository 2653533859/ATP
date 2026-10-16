import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import HealingAuditTrailPanel from './HealingAuditTrailPanel.vue'
import { healingAuditTrailApi } from '@/api/aiHealing'

const mockMetrics = {
  total_healing_actions_count: 18,
  verification_success_rate_pct: 94.44,
  average_confidence_score: 0.925,
  total_fault_clusters_count: 4,
  estimated_engineering_hours_saved: 5.61,
}

const mockClusters = [
  {
    cluster_id: 'cluster_e7a1b2',
    signature: 'sig_nosuch_element_checkout_btn_v1',
    primary_exception: 'NoSuchElementException',
    root_cause_summary: '前端发布重构导致元素选择器失效，关键业务按钮缺少唯一 data-testid',
    occurrences_count: 7,
    affected_case_ids: [101, 102, 108],
    affected_run_ids: [501, 502],
    first_seen: '2026-10-15T08:00:00Z',
    last_seen: '2026-10-16T10:00:00Z',
    suggested_healing_action: 'multimodal_locator_healing',
  },
  {
    cluster_id: 'cluster_f8c3d4',
    signature: 'sig_schema_validation_extra_field',
    primary_exception: 'SchemaValidationError',
    root_cause_summary: '后端响应契约漂移，新增非破坏性字段 coupon_code',
    occurrences_count: 3,
    affected_case_ids: [201, 205],
    affected_run_ids: [601],
    first_seen: '2026-10-16T09:00:00Z',
    last_seen: '2026-10-16T11:00:00Z',
    suggested_healing_action: 'flexible_schema_assertion',
  },
]

const mockEntries = [
  {
    audit_id: 'audit_act_001',
    case_id: 101,
    step_name: '点击结算按钮',
    action_type: 'locator_replaced',
    original_value: '//*[@id="checkout-btn-v1"]',
    healed_value: '//*[@data-testid="submit-order-btn"]',
    confidence_score: 0.95,
    verification_status: 'verified_success',
    cluster_id: 'cluster_e7a1b2',
    duration_ms: 12.5,
    metadata: {},
    created_at: '2026-10-16T10:05:00Z',
  },
  {
    audit_id: 'audit_act_002',
    case_id: 201,
    step_name: '校验下单响应报文',
    action_type: 'schema_autofixed',
    original_value: { type: 'object', required: ['order_id'] },
    healed_value: { type: 'object', required: ['order_id'], properties: { coupon_code: { type: 'string' } } },
    confidence_score: 1.0,
    verification_status: 'auto_accepted',
    cluster_id: 'cluster_f8c3d4',
    duration_ms: 8.2,
    metadata: {},
    created_at: '2026-10-16T10:10:00Z',
  },
]

vi.mock('@/api/aiHealing', () => ({
  healingAuditTrailApi: {
    getMetrics: vi.fn(),
    listClusters: vi.fn(),
    getCluster: vi.fn(),
    listEntries: vi.fn(),
    clusterError: vi.fn(),
    recordAction: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  ClusterOutlined: { template: '<span>Cluster</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  BugOutlined: { template: '<span>Bug</span>' },
  PlusOutlined: { template: '<span>Plus</span>' },
  CheckCircleOutlined: { template: '<span>Check</span>' },
}))

describe('HealingAuditTrailPanel.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(healingAuditTrailApi.getMetrics).mockResolvedValue(mockMetrics as any)
    vi.mocked(healingAuditTrailApi.listClusters).mockResolvedValue({ total: 2, clusters: mockClusters } as any)
    vi.mocked(healingAuditTrailApi.listEntries).mockResolvedValue({ total: 2, entries: mockEntries } as any)
  })

  it('renders KPI metrics cards and fault clusters table on mount', async () => {
    const wrapper = mount(HealingAuditTrailPanel, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-tooltip': { template: '<span><slot /></span>' },
          'a-table': {
            props: ['dataSource', 'columns'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.cluster_id || item.audit_id" class="table-row">
                  <span v-if="item.cluster_id" class="cluster-id-col">{{ item.cluster_id }}</span>
                  <span v-if="item.primary_exception" class="exception-col">{{ item.primary_exception }}</span>
                  <span v-if="item.root_cause_summary" class="summary-col">{{ item.root_cause_summary }}</span>
                  <span v-if="item.audit_id" class="audit-id-col">{{ item.audit_id }}</span>
                  <span v-if="item.step_name" class="step-col">{{ item.step_name }}</span>
                </div>
              </div>
            `,
          },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-textarea': { template: '<textarea />' },
          'a-progress': { template: '<div class="ant-progress" />' },
        },
      },
    })

    await flushPromises()

    // 验证头部与 KPI 指标渲染
    expect(wrapper.text()).toContain('异常故障簇智能聚合与自愈执行流水审计')
    expect(wrapper.text()).toContain('累计自愈执行流水')
    expect(wrapper.text()).toContain('18')
    expect(wrapper.text()).toContain('94.4%')
    expect(wrapper.text()).toContain('92.5%')
    expect(wrapper.text()).toContain('4')
    expect(wrapper.text()).toContain('5.6')

    // 验证故障簇列表数据加载
    expect(healingAuditTrailApi.getMetrics).toHaveBeenCalled()
    expect(healingAuditTrailApi.listClusters).toHaveBeenCalled()
    expect(healingAuditTrailApi.listEntries).toHaveBeenCalled()

    expect(wrapper.text()).toContain('cluster_e7a1b2')
    expect(wrapper.text()).toContain('NoSuchElementException')
    expect(wrapper.text()).toContain('前端发布重构导致元素选择器失效')
  })

  it('triggers cluster error simulation and reloads data', async () => {
    vi.mocked(healingAuditTrailApi.clusterError).mockResolvedValue({
      message: '异常事件已成功聚类归因',
      cluster: mockClusters[0] as any,
    })

    const wrapper = mount(HealingAuditTrailPanel, {
      global: {
        stubs: {
          'a-spin': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-tooltip': { template: '<span><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-textarea': { template: '<textarea />' },
          'a-progress': { template: '<div class="ant-progress" />' },
        },
      },
    })

    await flushPromises()

    // 调用 simulate cluster
    const vm = wrapper.vm as any
    await vm.handleSimulateCluster()

    expect(healingAuditTrailApi.clusterError).toHaveBeenCalledWith(expect.objectContaining({
      exception_type: 'NoSuchElementException',
    }))
  })
})
