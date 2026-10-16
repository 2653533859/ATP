import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AssetDependencyGraphViewer from './AssetDependencyGraphViewer.vue'
import { assetGraphApi } from '@/api/assetGraph'

const mockGraphResponse = {
  project_id: 1,
  total_nodes: 5,
  total_forward_edges: 4,
  nodes: [
    { node_id: 'plan_1', asset_type: 'plan' as const, asset_id: 1, name: '核心回归测试计划', project_id: 1 },
    { node_id: 'suite_10', asset_type: 'suite' as const, asset_id: 10, name: '结算链路套件', project_id: 1 },
    { node_id: 'case_101', asset_type: 'case' as const, asset_id: 101, name: '提交订单支付用例', project_id: 1 },
    { node_id: 'api_501', asset_type: 'api_endpoint' as const, asset_id: 501, name: 'POST /api/v1/order/pay', project_id: 1 },
    { node_id: 'dataset_20', asset_type: 'dataset' as const, asset_id: 20, name: '支付测试数据集', project_id: 1 },
  ],
  forward_edges: {
    plan_1: ['suite_10'],
    suite_10: ['case_101'],
    case_101: ['api_501', 'dataset_20'],
  },
  reverse_edges: {
    suite_10: ['plan_1'],
    case_101: ['suite_10'],
    api_501: ['case_101'],
    dataset_20: ['case_101'],
  },
}

const mockOrphansResponse = {
  orphan_cases: [
    { node_id: 'case_999', asset_type: 'case' as const, asset_id: 999, name: '未绑定套件的游离用例', project_id: 1 },
  ],
  orphan_datasets: [
    { node_id: 'dataset_888', asset_type: 'dataset' as const, asset_id: 888, name: '游离历史测试数据源', project_id: 1 },
  ],
  total_orphans_count: 2,
}

vi.mock('@/api/assetGraph', () => ({
  assetGraphApi: {
    getProjectGraph: vi.fn(),
    reindex: vi.fn(),
    getOrphans: vi.fn(),
    getDownstream: vi.fn(),
    getUpstream: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    template: '<div class="echarts-mock" @click="$emit(\'click\', { dataType: \'node\', data: { id: \'case_101\' } })" />',
    props: ['option'],
  },
}))

describe('AssetDependencyGraphViewer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders graph viewer title, description, and topology KPI metrics on mount', async () => {
    vi.mocked(assetGraphApi.getProjectGraph).mockResolvedValue(mockGraphResponse)
    vi.mocked(assetGraphApi.getOrphans).mockResolvedValue(mockOrphansResponse)

    const wrapper = mount(AssetDependencyGraphViewer, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('全域测试资产依赖拓扑图谱与孤儿资产治理看板')
    expect(wrapper.text()).toContain('Plan → Suite → Case → API / Dataset')
    expect(wrapper.text()).toContain('5') // total nodes
    expect(wrapper.text()).toContain('4') // total edges
    expect(wrapper.text()).toContain('未绑定套件的游离用例') // orphan list
    expect(wrapper.text()).toContain('[孤儿资产治理预警]')
  })

  it('triggers reindex and reloads the project asset graph', async () => {
    vi.mocked(assetGraphApi.getProjectGraph).mockResolvedValue(mockGraphResponse)
    vi.mocked(assetGraphApi.getOrphans).mockResolvedValue({
      orphan_cases: [],
      orphan_datasets: [],
      total_orphans_count: 0,
    })
    vi.mocked(assetGraphApi.reindex).mockResolvedValue({
      message: '资产依赖索引重建完成',
      total_nodes: 5,
      total_forward_edges: 4,
    })

    const wrapper = mount(AssetDependencyGraphViewer, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert" />' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const reindexBtn = wrapper.findAll('button').find((b) => b.text().includes('重新全量索引'))
    expect(reindexBtn).toBeDefined()
    await reindexBtn!.trigger('click')
    await flushPromises()

    expect(assetGraphApi.reindex).toHaveBeenCalledWith(1)
    expect(assetGraphApi.getProjectGraph).toHaveBeenCalledTimes(2)
  })

  it('handles node click to fetch and display downstream and upstream dependencies', async () => {
    vi.mocked(assetGraphApi.getProjectGraph).mockResolvedValue(mockGraphResponse)
    vi.mocked(assetGraphApi.getOrphans).mockResolvedValue({
      orphan_cases: [],
      orphan_datasets: [],
      total_orphans_count: 0,
    })
    vi.mocked(assetGraphApi.getDownstream).mockResolvedValue({
      source_node_id: 'case_101',
      max_depth: 10,
      visited_count: 2,
      downstream_nodes: [
        { node_id: 'api_501', asset_type: 'api_endpoint' as const, asset_id: 501, name: 'POST /api/v1/order/pay', project_id: 1 },
      ],
    })
    vi.mocked(assetGraphApi.getUpstream).mockResolvedValue({
      target_node_id: 'case_101',
      max_depth: 10,
      visited_count: 2,
      upstream_nodes: [
        { node_id: 'suite_10', asset_type: 'suite' as const, asset_id: 10, name: '结算链路套件', project_id: 1 },
      ],
    })

    const wrapper = mount(AssetDependencyGraphViewer, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input-number': { template: '<input />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert" />' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    // 点击 mock 的 VChart 触发 node 点击
    const chart = wrapper.find('.echarts-mock')
    expect(chart.exists()).toBe(true)
    await chart.trigger('click')
    await flushPromises()

    expect(assetGraphApi.getDownstream).toHaveBeenCalledWith('case_101')
    expect(assetGraphApi.getUpstream).toHaveBeenCalledWith('case_101')

    expect(wrapper.text()).toContain('提交订单支付用例')
    expect(wrapper.text()).toContain('POST /api/v1/order/pay')
    expect(wrapper.text()).toContain('结算链路套件')
  })
})
