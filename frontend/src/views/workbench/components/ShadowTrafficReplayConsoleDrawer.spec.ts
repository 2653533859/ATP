import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ShadowTrafficReplayConsoleDrawer from './ShadowTrafficReplayConsoleDrawer.vue'
import { shadowReplayApi } from '@/api/trafficGateway'

const mockMockRules = [
  { rule_id: 'mock_pay', name: '第三方支付网关拦截 (微信/支付宝)', pattern: '.*alipay.*', mock_status_code: 200, mock_response_body: '{}', enabled: true },
  { rule_id: 'mock_sms', name: '短信与消息推送服务拦截', pattern: '.*sms.*', mock_status_code: 200, mock_response_body: '{}', enabled: true },
]

const mockReport = {
  session_id: 'rpl_test_001',
  target_base_url: 'http://test-server:8000',
  write_guard_mode: 'BLOCK_WRITES',
  total_items: 6,
  success_count: 6,
  failure_count: 0,
  blocked_write_count: 2,
  mocked_external_count: 2,
  avg_duration_ms: 12.4,
  created_at: '2026-10-16T12:00:00Z',
  results: [
    {
      item_id: 'rit_1',
      traffic_id: 'trf_1',
      method: 'GET',
      path_or_endpoint: '/api/v1/products/101',
      executed_url: 'http://test-server:8000/api/v1/products/101',
      original_status_code: 200,
      replayed_status_code: 200,
      duration_ms: 22.5,
      was_mocked: false,
      mock_reason: null,
      was_write_blocked: false,
      replayed_response_body: '{"product_id": 101}',
      success: true,
      error_message: null,
    },
    {
      item_id: 'rit_2',
      traffic_id: 'trf_2',
      method: 'POST',
      path_or_endpoint: '/api/v1/orders/checkout',
      executed_url: 'http://test-server:8000/api/v1/orders/checkout',
      original_status_code: 200,
      replayed_status_code: 200,
      duration_ms: 1.5,
      was_mocked: false,
      mock_reason: null,
      was_write_blocked: true,
      replayed_response_body: '{"code": 0, "shadow_blocked": true}',
      success: true,
      error_message: null,
    },
    {
      item_id: 'rit_3',
      traffic_id: 'trf_3',
      method: 'POST',
      path_or_endpoint: 'https://api.alipay.com/gateway.do',
      executed_url: 'https://api.alipay.com/gateway.do',
      original_status_code: 200,
      replayed_status_code: 200,
      duration_ms: 2.0,
      was_mocked: true,
      mock_reason: '命中第三方外部依赖 Mock 规则: 第三方支付网关拦截 (微信/支付宝)',
      was_write_blocked: false,
      replayed_response_body: '{"code": 0, "status": "SUCCESS"}',
      success: true,
      error_message: null,
    },
  ],
}

vi.mock('@/api/trafficGateway', () => ({
  shadowReplayApi: {
    getDefaultMockRules: vi.fn(),
    listSessions: vi.fn(),
    runReplay: vi.fn(),
    getSession: vi.fn(),
    clearSessions: vi.fn(),
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
  SendOutlined: { template: '<span>Send</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  PlayCircleOutlined: { template: '<span>Play</span>' },
  CheckCircleOutlined: { template: '<span>Check</span>' },
  CloseCircleOutlined: { template: '<span>Close</span>' },
  LockOutlined: { template: '<span>Lock</span>' },
  ApiOutlined: { template: '<span>Api</span>' },
}))

describe('ShadowTrafficReplayConsoleDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(shadowReplayApi.getDefaultMockRules).mockResolvedValue({
      rules: mockMockRules as any,
    })
    vi.mocked(shadowReplayApi.listSessions).mockResolvedValue({
      total: 1,
      sessions: [mockReport as any],
    })
    vi.mocked(shadowReplayApi.runReplay).mockResolvedValue({
      message: '影子流量无副作用回放完成',
      report: mockReport as any,
    })
  })

  it('renders drawer header, KPI metrics, and replay results stream table', async () => {
    const wrapper = mount(ShadowTrafficReplayConsoleDrawer, {
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
          'a-input-number': { template: '<input type="number" />' },
          'a-slider': { template: '<div class="ant-slider" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-collapse': { template: '<div><slot /></div>' },
          'a-collapse-panel': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.item_id" class="row">
                  <span class="path">{{ item.path_or_endpoint }}</span>
                  <span class="url">{{ item.executed_url }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查标题与 API 调用
    expect(wrapper.text()).toContain('影子流量安全回放与零副作用沙箱调度引擎')
    expect(shadowReplayApi.getDefaultMockRules).toHaveBeenCalled()
    expect(shadowReplayApi.listSessions).toHaveBeenCalled()

    // 检查 KPI 指标
    expect(wrapper.text()).toContain('回放总请求数')
    expect(wrapper.text()).toContain('6') // total_items
    expect(wrapper.text()).toContain('写操作安全拦截')
    expect(wrapper.text()).toContain('外部依赖 Mock 代理')

    // 检查表格项目
    expect(wrapper.text()).toContain('/api/v1/products/101')
    expect(wrapper.text()).toContain('/api/v1/orders/checkout')
  })

  it('runs replay and filters results', async () => {
    const wrapper = mount(ShadowTrafficReplayConsoleDrawer, {
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
          'a-input-number': { template: '<input type="number" />' },
          'a-slider': { template: '<div class="ant-slider" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-collapse': { template: '<div><slot /></div>' },
          'a-collapse-panel': { template: '<div><slot /></div>' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-modal': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any

    // 运行回放
    await vm.handleRunReplay()
    expect(shadowReplayApi.runReplay).toHaveBeenCalledWith(expect.objectContaining({
      write_guard_mode: 'BLOCK_WRITES',
      rate_limit_qps: 20,
    }))

    // 过滤仅写拦截
    vm.statusFilter = 'BLOCKED_WRITE'
    expect(vm.filteredResults.length).toBe(1)
    expect(vm.filteredResults[0].was_write_blocked).toBe(true)

    // 过滤仅外部 Mock
    vm.statusFilter = 'MOCKED'
    expect(vm.filteredResults.length).toBe(1)
    expect(vm.filteredResults[0].was_mocked).toBe(true)
  })
})
