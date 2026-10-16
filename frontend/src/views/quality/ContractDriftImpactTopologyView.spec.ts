import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ContractDriftImpactTopologyView from './ContractDriftImpactTopologyView.vue'
import { contractTopologyApi } from '@/api/trafficGateway'

const mockTopology = {
  services_count: 4,
  dependencies_count: 3,
  nodes: [
    { service_id: 'order-service', service_name: '订单核心服务', owner: 'OrderTeam', is_critical_asset: true },
    { service_id: 'pay-service', service_name: '支付结算微服务', owner: 'PayTeam', is_critical_asset: true },
    { service_id: 'delivery-service', service_name: '物流履约微服务', owner: 'LogisticsTeam', is_critical_asset: false },
    { service_id: 'user-service', service_name: '用户中心服务', owner: 'UserTeam', is_critical_asset: true },
  ],
  edges: [
    { consumer_service_id: 'pay-service', producer_service_id: 'order-service', endpoint: 'POST /api/v1/orders/checkout', consumed_fields: ['amount', 'order_id'], call_frequency: 'HIGH' },
    { consumer_service_id: 'delivery-service', producer_service_id: 'order-service', endpoint: 'POST /api/v1/orders/checkout', consumed_fields: ['order_id'], call_frequency: 'HIGH' },
    { consumer_service_id: 'order-service', producer_service_id: 'user-service', endpoint: 'GET /api/v1/users/profile', consumed_fields: ['user_id'], call_frequency: 'HIGH' },
  ],
}

const mockImpactReport = {
  analysis_id: 'ia_test_101',
  endpoint: 'POST /api/v1/orders/checkout',
  producer_service: 'order-service',
  broken_fields: ['amount', 'order_id'],
  blast_radius_score: 85.0,
  blast_radius_level: 'CRITICAL',
  total_impacted_services: 2,
  direct_services_count: 2,
  transitive_services_count: 0,
  impacted_services: [
    {
      service_id: 'pay-service',
      service_name: '支付结算微服务',
      owner: 'PayTeam',
      impact_tier: 'DIRECT',
      cascade_depth: 1,
      hit_broken_fields: ['amount', 'order_id'],
      is_critical_asset: true,
      remediation_advice: '支付核心强依赖 amount 进行金额扣减，需对齐契约或暂缓发布。',
    },
    {
      service_id: 'delivery-service',
      service_name: '物流履约微服务',
      owner: 'LogisticsTeam',
      impact_tier: 'DIRECT',
      cascade_depth: 1,
      hit_broken_fields: ['order_id'],
      is_critical_asset: false,
      remediation_advice: '物流单号生成依赖 order_id，需检查空指针防御。',
    },
  ],
  dispatched_alerts: [
    {
      alert_id: 'alt_1',
      target_service_id: 'pay-service',
      recipient: 'PayTeam',
      endpoint: 'POST /api/v1/orders/checkout',
      alert_channel: 'Webhook',
      status: 'SENT',
      dispatched_at: '2026-10-16T12:00:00Z',
    },
  ],
  verdict_summary: '波及 2 个关键微服务且包含核心支付资产，触发 CRITICAL 红色爆炸半径告警！',
  created_at: '2026-10-16T12:00:00Z',
}
vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    props: ['option'],
    template: '<div class="echarts-mock" />',
  },
}))


vi.mock('@/api/trafficGateway', () => ({
  contractTopologyApi: {
    getTopology: vi.fn(),
    analyzeImpact: vi.fn(),
    listReports: vi.fn(),
    getReport: vi.fn(),
    registerService: vi.fn(),
    registerDependency: vi.fn(),
    clearTopology: vi.fn(),
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
  ApartmentOutlined: { template: '<span>Apartment</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
}))

describe('ContractDriftImpactTopologyView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(contractTopologyApi.getTopology).mockResolvedValue(mockTopology as any)
    vi.mocked(contractTopologyApi.analyzeImpact).mockResolvedValue({
      message: '级联影响分析完成',
      report: mockImpactReport as any,
    })
  })

  it('renders page hero, blast radius banner, chart, and impacted services', async () => {
    const wrapper = mount(ContractDriftImpactTopologyView, {
      global: {
        stubs: {
          'v-chart': { template: '<div class="v-chart-stub" />' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-empty': { template: '<div>Empty</div>' },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(contractTopologyApi.getTopology).toHaveBeenCalled()
    expect(contractTopologyApi.analyzeImpact).toHaveBeenCalled()
    expect(wrapper.text()).toContain('契约漂移微服务级联依赖拓扑图谱与爆炸半径告警大盘')

    // 检查爆炸半径大横幅
    expect(wrapper.text()).toContain('CRITICAL BLAST RADIUS')
    expect(wrapper.text()).toContain('85%')
    expect(wrapper.text()).toContain('全网波及受损服务总数')

    // 检查受损服务列表与修复指导
    expect(wrapper.text()).toContain('支付结算微服务')
    expect(wrapper.text()).toContain('物流履约微服务')
    expect(wrapper.text()).toContain('支付核心强依赖 amount 进行金额扣减')

    // 检查告警派发
    expect(wrapper.text()).toContain('定向安全告警派发记录')
    expect(wrapper.text()).toContain('PayTeam')
  })

  it('switches preset and triggers new impact analysis', async () => {
    const wrapper = mount(ContractDriftImpactTopologyView, {
      global: {
        stubs: {
          'v-chart': { template: '<div class="v-chart-stub" />' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-empty': { template: '<div>Empty</div>' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('medium')
    await flushPromises()

    expect(contractTopologyApi.analyzeImpact).toHaveBeenCalledWith(expect.objectContaining({
      broken_fields: ['coupon_code'],
    }))
  })
})
