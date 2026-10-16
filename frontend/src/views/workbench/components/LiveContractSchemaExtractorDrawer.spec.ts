import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import LiveContractSchemaExtractorDrawer from './LiveContractSchemaExtractorDrawer.vue'
import { liveContractApi } from '@/api/trafficGateway'

const mockContract = {
  contract_id: 'ct_test_101',
  endpoint: 'POST /api/v1/orders/checkout',
  method: 'POST',
  path: '/api/v1/orders/checkout',
  protocol: 'HTTP',
  samples_count: 5,
  request_schema: {
    type: 'object',
    properties: {
      order_id: { type: 'integer', format: 'int64' },
      amount: { type: 'number', format: 'double' },
      channel: { type: 'string', enum: ['APP', 'H5', 'WEB'] },
    },
    required: ['amount', 'order_id'],
  },
  response_schemas: {
    '200': {
      type: 'object',
      properties: { code: { type: 'integer' }, status: { type: 'string' } },
    },
    '400': {
      type: 'object',
      properties: { code: { type: 'integer' }, error: { type: 'string' } },
    },
  },
  query_parameters: [],
  header_parameters: [],
  protobuf_definition: 'syntax = "proto3";\n\nmessage OrderRequest {\n  double amount = 1;\n  int64 order_id = 2;\n}',
  extracted_at: '2026-10-16T12:00:00Z',
}

vi.mock('@/api/trafficGateway', () => ({
  liveContractApi: {
    listContracts: vi.fn(),
    extractSingle: vi.fn(),
    extractBatch: vi.fn(),
    getContract: vi.fn(),
    getContractByEndpoint: vi.fn(),
    clearContracts: vi.fn(),
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
  BranchesOutlined: { template: '<span>Branches</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
  CodeOutlined: { template: '<span>Code</span>' },
}))

describe('LiveContractSchemaExtractorDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(liveContractApi.listContracts).mockResolvedValue({
      total: 1,
      contracts: [mockContract as any],
    })
    vi.mocked(liveContractApi.extractBatch).mockResolvedValue({
      message: '全网接口契约逆向推导完成',
      report: {
        report_id: 'ebp_1',
        total_traffic_analyzed: 5,
        contracts_extracted_count: 1,
        contracts: [mockContract as any],
        created_at: '2026-10-16T12:00:00Z',
      },
    })
  })

  it('renders drawer header, KPI metrics, and OpenAPI schema properties table', async () => {
    const wrapper = mount(LiveContractSchemaExtractorDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.name" class="row">
                  <span class="prop-name">{{ item.name }}</span>
                  <span class="prop-type">{{ item.type }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查标题与 API 调用
    expect(wrapper.text()).toContain('生产流量接口契约动态逆向推导引擎')
    expect(liveContractApi.listContracts).toHaveBeenCalled()

    // 检查 KPI 指标
    expect(wrapper.text()).toContain('归纳样本总数')
    expect(wrapper.text()).toContain('5 条')
    expect(wrapper.text()).toContain('2 个') // required: amount, order_id
    expect(wrapper.text()).toContain('1 个') // enum: channel

    // 检查属性表格
    expect(wrapper.text()).toContain('order_id')
    expect(wrapper.text()).toContain('amount')
    expect(wrapper.text()).toContain('channel')

    // 检查 Protobuf
    expect(wrapper.text()).toContain('syntax = "proto3"')
  })

  it('switches presets and triggers extractBatch', async () => {
    const wrapper = mount(LiveContractSchemaExtractorDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any

    // 切换至用户资料预设
    vm.applyPreset('users')
    expect(vm.currentEndpoint).toBe('GET /api/v1/users/profile')

    // 执行推导
    await vm.handleRunExtract()
    expect(liveContractApi.extractBatch).toHaveBeenCalledWith(expect.objectContaining({
      limit_captured: 100,
    }))
  })
})
