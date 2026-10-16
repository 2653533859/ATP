import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TrafficToTestCaseSynthesizerCard from './TrafficToTestCaseSynthesizerCard.vue'
import { trafficSynthesizerApi } from '@/api/trafficGateway'

const mockReport = {
  report_id: 'syn_test_001',
  total_traffic_evaluated: 50,
  clusters_formed: 10,
  deduplication_ratio_pct: 80.0,
  synthesized_cases_count: 10,
  created_at: '2026-10-16T11:00:00Z',
  cases: [
    {
      case_id: 'tc_syn_order_1',
      cluster_id: 'cls_order_1',
      name: 'AUTO_TRAFFIC_POST_api_v1_orders_checkout_200',
      description: '由 ATP 生产流量智能合成引擎生成',
      protocol: 'HTTP',
      method: 'POST',
      url_path: '/api/v1/orders/checkout',
      headers: { 'Content-Type': 'application/json' },
      query_params_template: { channel: 'app' },
      request_body_template: '{"order_id": 1001, "amount": 199.0}',
      assertions: [
        { target: 'status_code', operator: 'eq', expected: 200, description: '验证响应状态码为 200' },
        { target: 'duration_ms', operator: 'le', expected: 200.0, description: 'SLA' },
      ],
      dataset_rows: [
        { traffic_id: 'trf_1', raw_path: '/api/v1/orders/checkout', request_body: '{"order_id": 1001}', expected_status: 200 },
        { traffic_id: 'trf_2', raw_path: '/api/v1/orders/checkout', request_body: '{"order_id": 1002}', expected_status: 200 },
      ],
      source_traffic_ids: ['trf_1', 'trf_2'],
      created_at: '2026-10-16T11:00:00Z',
    },
  ],
}

vi.mock('@/api/trafficGateway', () => ({
  trafficSynthesizerApi: {
    listReports: vi.fn(),
    runSynthesis: vi.fn(),
    getReport: vi.fn(),
    previewClusters: vi.fn(),
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
  BuildOutlined: { template: '<span>Build</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  FolderAddOutlined: { template: '<span>FolderAdd</span>' },
}))

describe('TrafficToTestCaseSynthesizerCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(trafficSynthesizerApi.listReports).mockResolvedValue({
      total: 1,
      reports: [mockReport as any],
    })
    vi.mocked(trafficSynthesizerApi.runSynthesis).mockResolvedValue({
      message: '流量聚类分析与测试用例智能合成完成',
      report: mockReport as any,
    })
  })

  it('renders card title, deduplication banner with 80%, and synthesized cases table', async () => {
    const wrapper = mount(TrafficToTestCaseSynthesizerCard, {
      global: {
        stubs: {
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.case_id" class="row">
                  <span class="case-name">{{ item.name }}</span>
                  <span class="path">{{ item.url_path }}</span>
                  <span class="sources">{{ item.source_traffic_ids.length }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查标题与去重率
    expect(wrapper.text()).toContain('真实流量特征聚类归一与自动化测试用例智能生成控制台')
    expect(trafficSynthesizerApi.listReports).toHaveBeenCalled()

    // 检查去重横幅与流向
    expect(wrapper.text()).toContain('80%')
    expect(wrapper.text()).toContain('聚类去重削峰率')
    expect(wrapper.text()).toContain('50') // evaluated
    expect(wrapper.text()).toContain('10') // clusters

    // 检查表格内容
    expect(wrapper.text()).toContain('AUTO_TRAFFIC_POST_api_v1_orders_checkout_200')
    expect(wrapper.text()).toContain('/api/v1/orders/checkout')
  })

  it('triggers synthesis on button click', async () => {
    const wrapper = mount(TrafficToTestCaseSynthesizerCard, {
      global: {
        stubs: {
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-spin': { template: '<div><slot /></div>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleRunSynthesis()

    expect(trafficSynthesizerApi.runSynthesis).toHaveBeenCalledWith(expect.objectContaining({
      auto_mask_first: true,
      case_name_prefix: 'AUTO_TRAFFIC',
      limit_captured: 100,
    }))
  })
})
