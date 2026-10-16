import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import TrafficChaosFaultInjectorDrawer from './TrafficChaosFaultInjectorDrawer.vue'
import { trafficChaosApi } from '@/api/trafficGateway'

const mockRule = {
  rule_id: 'rule_chaos_101',
  rule_name: '订单结算网关高时延压测',
  fault_type: 'LATENCY',
  match_criteria: {
    endpoint_pattern: '.*/orders/checkout.*',
    methods: ['POST'],
    header_match: { 'X-Canary': 'beta' },
    param_match: {},
    traffic_ratio: 1.0,
  },
  latency_ms: 1200,
  latency_jitter_max_ms: 300,
  error_status_code: 500,
  error_response_body: '{}',
  corruption_mode: 'TRUNCATE',
  enabled: true,
  max_triggers_limit: 50,
  current_triggers_count: 5,
  created_at: '2026-10-16T12:00:00Z',
}

const mockSession = {
  experiment_id: 'exp_test_101',
  name: '生产微服务全网混沌故障注入演练',
  description: '测试会话',
  rules: [mockRule],
  total_requests_intercepted: 12,
  total_faults_injected: 10,
  fault_breakdown: { LATENCY: 10 },
  is_active: true,
  started_at: '2026-10-16T12:00:00Z',
  stopped_at: null,
}

vi.mock('@/api/trafficGateway', () => ({
  trafficChaosApi: {
    createRule: vi.fn(),
    listRules: vi.fn(),
    deleteRule: vi.fn(),
    evaluateFault: vi.fn(),
    startSession: vi.fn(),
    stopSession: vi.fn(),
    listSessions: vi.fn(),
    getSession: vi.fn(),
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
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  PlusOutlined: { template: '<span>Plus</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
  PlayCircleOutlined: { template: '<span>PlayCircle</span>' },
  StopOutlined: { template: '<span>Stop</span>' },
}))

describe('TrafficChaosFaultInjectorDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(trafficChaosApi.listRules).mockResolvedValue({
      total: 1,
      rules: [mockRule as any],
    })
    vi.mocked(trafficChaosApi.listSessions).mockResolvedValue({
      total: 1,
      sessions: [mockSession as any],
    })
    vi.mocked(trafficChaosApi.evaluateFault).mockResolvedValue({
      message: '在线演练评估完成',
      result: {
        intercept_id: 'ic_1',
        rule_id: 'rule_chaos_101',
        fault_triggered: true,
        fault_type: 'LATENCY',
        injected_latency_ms: 1250,
        effective_status_code: 200,
        effective_response_body: '{"code": 0}',
        log_message: '命中高时延注入规则: 注入 1250ms 延迟',
      },
    })
  })

  it('renders drawer header, rules table, and active chaos session status', async () => {
    const wrapper = mount(TrafficChaosFaultInjectorDrawer, {
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
          'a-textarea': { template: '<textarea />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-slider': { template: '<div class="slider" />' },
          'a-progress': { template: '<div class="progress" />' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div class="form-item"><slot /></div>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.rule_id" class="row">
                  <span class="rule-name">{{ item.rule_name }}</span>
                  <span class="fault-type">{{ item.fault_type }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查加载
    expect(trafficChaosApi.listRules).toHaveBeenCalled()
    expect(trafficChaosApi.listSessions).toHaveBeenCalled()

    // 检查标题与模式卡片
    expect(wrapper.text()).toContain('基于流量特征匹配的应用层微服务故障注入防线')
    expect(wrapper.text()).toContain('网络慢调用 (LATENCY)')
    expect(wrapper.text()).toContain('协议错误码 (ERROR_RESPONSE)')
    expect(wrapper.text()).toContain('载荷损坏 (CORRUPTION)')
    expect(wrapper.text()).toContain('中途断开 (ABRUPT_DROP)')

    // 检查演练状态
    expect(wrapper.text()).toContain('演练注入中 (ACTIVE)')
    expect(wrapper.text()).toContain('拦截请求')
    expect(wrapper.text()).toContain('12')

    // 检查规则表格
    expect(wrapper.text()).toContain('订单结算网关高时延压测')
  })

  it('runs online sandbox simulation and renders injected fault feedback', async () => {
    const wrapper = mount(TrafficChaosFaultInjectorDrawer, {
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
          'a-textarea': { template: '<textarea />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-slider': { template: '<div class="slider" />' },
          'a-progress': { template: '<div class="progress" />' },
          'a-popconfirm': { template: '<div><slot /></div>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div class="form-item"><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleSimulate()
    await flushPromises()

    expect(trafficChaosApi.evaluateFault).toHaveBeenCalledWith(expect.objectContaining({
      path_or_endpoint: '/api/v1/orders/checkout',
      method: 'POST',
    }))

    expect(wrapper.text()).toContain('故障已成功注入')
    expect(wrapper.text()).toContain('1250 ms')
  })
})
