import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SandboxTrafficMirrorCard from './SandboxTrafficMirrorCard.vue'
import { trafficMirrorApi } from '@/api/sandboxes'

const mockPolicy = {
  policy_id: 'pol_prod_order_shadow',
  name: '生产交易流量影子分流与隔离策略',
  source_service: 'order-service',
  route_pattern: '^/api/v1/orders/.*',
  target_sandbox_id: 'sbx_http_20005',
  sample_ratio: 1.0,
  isolate_side_effects: true,
  blocked_outbound_patterns: ['*payment*', '*charge*', '*sms*', '*notify*'],
  enabled: true,
}

const mockProcessResult = {
  policy_id: 'pol_prod_order_shadow',
  traffic_processed: 2,
  intercepted_side_effects_count: 2,
  safety_verified: true,
  isolation_audit: [
    {
      call_id: 'call_pay_01',
      target_destination: 'https://bank.internal/api/charge',
      method: 'POST',
      is_intercepted: true,
      intercept_reason: 'Matched blocked pattern *charge*',
      mock_response: {
        status: 200,
        headers: { 'X-Sandboxed-Isolated': 'true' },
      },
    },
    {
      call_id: 'call_sms_02',
      target_destination: 'https://sms-provider.internal/send',
      method: 'POST',
      is_intercepted: true,
      intercept_reason: 'Matched blocked pattern *sms*',
      mock_response: {
        status: 200,
        headers: { 'X-Sandboxed-Isolated': 'true' },
      },
    },
  ],
}

vi.mock('@/api/sandboxes', () => ({
  trafficMirrorApi: {
    listPolicies: vi.fn(),
    createPolicy: vi.fn(),
    processBatch: vi.fn(),
    getAudit: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

describe('SandboxTrafficMirrorCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders card title, description, and loads mirror policies on mount', async () => {
    vi.mocked(trafficMirrorApi.listPolicies).mockResolvedValue({
      total: 1,
      policies: [mockPolicy],
    })

    const wrapper = mount(SandboxTrafficMirrorCard, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot name="extra" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('沙箱网络流量镜像与写操作副作用安全隔离')
    expect(wrapper.text()).toContain('敏感写操作强阻断模式池：')
    expect(wrapper.text()).toContain('*payment*')
    expect(wrapper.text()).toContain('*charge*')
  })

  it('saves traffic mirror policy on button click', async () => {
    vi.mocked(trafficMirrorApi.listPolicies).mockResolvedValue({
      total: 0,
      policies: [],
    })
    vi.mocked(trafficMirrorApi.createPolicy).mockResolvedValue({
      message: '策略保存成功',
      policy: mockPolicy,
    })

    const wrapper = mount(SandboxTrafficMirrorCard, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot name="extra" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert" />' },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    const saveBtn = wrapper.findAll('button').find((b) => b.text().includes('保存策略'))
    expect(saveBtn).toBeDefined()
    await saveBtn!.trigger('click')
    await flushPromises()

    expect(trafficMirrorApi.createPolicy).toHaveBeenCalledWith({
      policy_id: expect.any(String),
      name: expect.any(String),
      source_service: 'order-service',
      route_pattern: expect.any(String),
      target_sandbox_id: expect.any(String),
      sample_ratio: 1.0,
      isolate_side_effects: true,
      blocked_outbound_patterns: expect.any(Array),
      enabled: true,
    })
  })

  it('injects traffic and verifies zero leakage side-effect isolation', async () => {
    vi.mocked(trafficMirrorApi.listPolicies).mockResolvedValue({
      total: 1,
      policies: [mockPolicy],
    })
    vi.mocked(trafficMirrorApi.processBatch).mockResolvedValue(mockProcessResult)

    const wrapper = mount(SandboxTrafficMirrorCard, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot name="extra" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-button': { template: '<button><slot /></button>' },
          'a-alert': { template: '<div class="ant-alert">{{ message }} {{ description }}</div>', props: ['message', 'description'] },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.call_id" class="row">
                  <slot name="bodyCell" :column="{ key: 'method' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'is_intercepted' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'response' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
        },
      },
    })

    await flushPromises()

    const injectBtn = wrapper.findAll('button').find((b) => b.text().includes('注入镜像流量并验证隔离'))
    expect(injectBtn).toBeDefined()
    await injectBtn!.trigger('click')
    await flushPromises()

    expect(trafficMirrorApi.processBatch).toHaveBeenCalledWith({
      policy_id: 'pol_prod_order_shadow',
      traffic_stream: expect.any(Array),
      outbound_calls: expect.any(Array),
    })

    // 验证零泄露安全横幅与审计流水
    expect(wrapper.text()).toContain('[ZERO LEAKAGE 零泄露合规证明]')
    expect(wrapper.text()).toContain('处理镜像流量请求')
    expect(wrapper.text()).toContain('已强行拦截隔离')
    expect(wrapper.text()).toContain('X-Sandboxed-Isolated: true')
  })
})
