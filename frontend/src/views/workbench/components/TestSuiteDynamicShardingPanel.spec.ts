import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TestSuiteDynamicShardingPanel from './TestSuiteDynamicShardingPanel.vue'
import { testSuiteShardingApi } from '@/api/cloudNativeCluster'

const mockPlan = {
  plan_id: 'shard_plan_1001_8',
  total_cases: 8,
  total_shards: 3,
  total_estimated_duration_ms: 22700.0,
  makespan_ms: 8200.0,
  min_shard_duration_ms: 7000.0,
  avg_shard_duration_ms: 7566.67,
  balance_score_pct: 91.5,
  shards: [
    {
      shard_index: 0,
      assigned_node_id: 'worker-node-1',
      case_ids: ['ecom_checkout', 'ecom_logistics'],
      case_count: 2,
      estimated_duration_ms: 8000.0,
    },
    {
      shard_index: 1,
      assigned_node_id: 'worker-node-2',
      case_ids: ['ecom_browse_cart', 'ecom_pay'],
      case_count: 2,
      estimated_duration_ms: 8000.0,
    },
    {
      shard_index: 2,
      assigned_node_id: 'worker-node-3',
      case_ids: ['ecom_login', 'ecom_inventory', 'ecom_coupon', 'ecom_points'],
      case_count: 4,
      estimated_duration_ms: 6700.0,
    },
  ],
  created_at: '2026-10-17T11:00:00Z',
}

const mockStraggler = {
  has_straggler: true,
  stragglers: [
    {
      shard_index: 0,
      node_id: 'worker-node-1',
      elapsed_ms: 12500.0,
      remaining_cases: 12,
      reason: '耗时 (12500.0ms) 超过集群均值，积压用例剩余 12 个',
    },
  ],
  recommendation: '建议将积压用例动态迁移至已完成的空闲 Worker 节点执行重平衡。',
  checked_at: '2026-10-17T11:02:00Z',
}

vi.mock('@/api/cloudNativeCluster', () => ({
  testSuiteShardingApi: {
    calculatePlan: vi.fn(),
    rebalanceDetect: vi.fn(),
    listPlans: vi.fn(),
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
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  ClockCircleOutlined: { template: '<span>Clock</span>' },
  RadarChartOutlined: { template: '<span>Radar</span>' },
}))

describe('TestSuiteDynamicShardingPanel.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(testSuiteShardingApi.calculatePlan).mockResolvedValue({
      message: '分片方案生成成功',
      plan: mockPlan as any,
    })
    vi.mocked(testSuiteShardingApi.rebalanceDetect).mockResolvedValue(mockStraggler as any)
  })

  it('renders header, sharding matrix, and straggler warning', async () => {
    const wrapper = mount(TestSuiteDynamicShardingPanel, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-progress': { template: '<div class="ant-progress" />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-input-number': { template: '<input type="number" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-alert': { template: '<div class="ant-alert"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(testSuiteShardingApi.calculatePlan).toHaveBeenCalled()
    expect(testSuiteShardingApi.rebalanceDetect).toHaveBeenCalled()

    // 检查标题与 KPI
    expect(wrapper.text()).toContain('LPT 贪心装箱算法与跨节点多分片负载均衡引擎')
    expect(wrapper.text()).toContain('8 个')
    expect(wrapper.text()).toContain('3 节点')
    expect(wrapper.text()).toContain('8200 ms')
    expect(wrapper.text()).toContain('91.5%')

    // 检查分片网格
    expect(wrapper.text()).toContain('worker-node-1')
    expect(wrapper.text()).toContain('worker-node-2')
    expect(wrapper.text()).toContain('worker-node-3')

    // 切换预设
    const vm = wrapper.vm as any
    vm.selectedPreset = 'api_regression'
    await vm.handlePresetChange()
    await flushPromises()

    expect(testSuiteShardingApi.calculatePlan).toHaveBeenCalledTimes(2)
  })
})
