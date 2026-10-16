import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TrafficCaptureGatewayDrawer from './TrafficCaptureGatewayDrawer.vue'
import { trafficCaptureApi } from '@/api/trafficGateway'

const mockConfig = {
  include_paths: ['^/api/v1/.*'],
  exclude_paths: ['^/health.*', '^/metrics.*'],
  allowed_methods: ['GET', 'POST', 'PUT', 'DELETE'],
  sampling_rate: 0.8,
  capture_request_body: true,
  capture_response_body: true,
  max_body_bytes: 1048576,
}

const mockMetrics = {
  metrics: {
    total_intercepted: 100,
    total_captured: 80,
    total_filtered_out: 15,
    total_sampled_out: 5,
  },
  active_records_count: 80,
  protocol_breakdown: { HTTP: 70, GRPC: 10 },
  filter_config: mockConfig,
}

const mockRecords = [
  {
    traffic_id: 'trf_test_001',
    protocol: 'HTTP',
    method: 'POST',
    path_or_endpoint: '/api/v1/orders/checkout',
    headers: { 'Content-Type': 'application/json' },
    query_params: { env: 'test' },
    request_body: '{"order_id": 1001, "amount": 199.0}',
    response_status_code: 200,
    response_body: '{"code": 0, "status": "CREATED"}',
    duration_ms: 45.2,
    client_ip: '192.168.1.100',
    tags: {},
    captured_at: '2026-10-16T10:00:00Z',
  },
  {
    traffic_id: 'trf_test_002',
    protocol: 'GRPC',
    method: 'POST /order.OrderService/GetOrderDetail',
    path_or_endpoint: '/order.OrderService/GetOrderDetail',
    headers: { 'content-type': 'application/grpc' },
    query_params: {},
    request_body: '{"order_id": 1001}',
    response_status_code: 0,
    response_body: '{"code": 0}',
    duration_ms: 18.0,
    client_ip: '192.168.1.105',
    tags: {},
    captured_at: '2026-10-16T10:02:00Z',
  },
]

vi.mock('@/api/trafficGateway', () => ({
  trafficCaptureApi: {
    getFilterConfig: vi.fn(),
    updateFilterConfig: vi.fn(),
    getMetrics: vi.fn(),
    listRecords: vi.fn(),
    clearRecords: vi.fn(),
    interceptTraffic: vi.fn(),
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
  ClusterOutlined: { template: '<span>Cluster</span>' },
  SaveOutlined: { template: '<span>Save</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  SendOutlined: { template: '<span>Send</span>' },
  DeleteOutlined: { template: '<span>Delete</span>' },
}))

describe('TrafficCaptureGatewayDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(trafficCaptureApi.getFilterConfig).mockResolvedValue(mockConfig as any)
    vi.mocked(trafficCaptureApi.getMetrics).mockResolvedValue(mockMetrics as any)
    vi.mocked(trafficCaptureApi.listRecords).mockResolvedValue({
      total: 2,
      records: mockRecords as any,
    })
    vi.mocked(trafficCaptureApi.updateFilterConfig).mockResolvedValue({
      message: '网关过滤配置已成功应用',
      config: mockConfig as any,
    })
    vi.mocked(trafficCaptureApi.clearRecords).mockResolvedValue({
      message: '已清空记录',
      deleted_count: 2,
    })
  })

  it('renders drawer header, KPI cards, and traffic records list on open', async () => {
    const wrapper = mount(TrafficCaptureGatewayDrawer, {
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
          'a-input-search': { template: '<input />' },
          'a-slider': { template: '<div class="ant-slider" />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-collapse': { template: '<div><slot /></div>' },
          'a-collapse-panel': { template: '<div><slot /></div>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.traffic_id" class="row">
                  <span class="path">{{ item.path_or_endpoint }}</span>
                  <span class="protocol">{{ item.protocol }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查标题与机制说明
    expect(wrapper.text()).toContain('微服务网关旁路流量镜像捕获引擎')

    // 检查 API 调用
    expect(trafficCaptureApi.getFilterConfig).toHaveBeenCalled()
    expect(trafficCaptureApi.getMetrics).toHaveBeenCalled()
    expect(trafficCaptureApi.listRecords).toHaveBeenCalled()

    // 检查 KPI 指标
    expect(wrapper.text()).toContain('网关总拦截流量')
    expect(wrapper.text()).toContain('100') // total_intercepted
    expect(wrapper.text()).toContain('80') // total_captured
    expect(wrapper.text()).toContain('15') // total_filtered_out

    // 检查表格记录
    expect(wrapper.text()).toContain('/api/v1/orders/checkout')
    expect(wrapper.text()).toContain('/order.OrderService/GetOrderDetail')
  })

  it('updates filter config and clears records', async () => {
    const wrapper = mount(TrafficCaptureGatewayDrawer, {
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
          'a-input-search': { template: '<input />' },
          'a-slider': { template: '<div class="ant-slider" />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-collapse': { template: '<div><slot /></div>' },
          'a-collapse-panel': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any

    // 测试保存配置
    vm.samplingRatePct = 50
    await vm.handleSaveConfig()
    expect(trafficCaptureApi.updateFilterConfig).toHaveBeenCalledWith(expect.objectContaining({
      sampling_rate: 0.5,
    }))

    // 测试清空记录
    await vm.handleClearRecords()
    expect(trafficCaptureApi.clearRecords).toHaveBeenCalled()
    expect(vm.records.length).toBe(0)
  })
})
