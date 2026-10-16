import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import CrossProtocolSessionBusPanel from './CrossProtocolSessionBusPanel.vue'
import { sessionBusApi } from '@/api/sandboxes'

const mockVars = {
  user_token: 'jwt_mock_token_abc',
  order_sn: 'ORD-20261016-001',
  user_id: 'usr_123',
  trace_id: 'tr_7788',
}

const mockPropagateGrpcResult = {
  direction: 'http_to_grpc',
  grpc_metadata: {
    authorization: 'Bearer jwt_mock_token_abc',
    'x-trace-id': 'tr_7788',
    'x-order-sn': 'ORD-20261016-001',
  },
}

const mockRenderResult = {
  rendered: {
    request_id: 'tr_7788',
    authorization: 'Bearer jwt_mock_token_abc',
    endpoint: '/api/v1/checkout/ORD-20261016-001',
    user_info: {
      uid: 'usr_123',
    },
  },
}

vi.mock('@/api/sandboxes', () => ({
  sessionBusApi: {
    initBus: vi.fn(),
    getVars: vi.fn(),
    setVar: vi.fn(),
    propagateContext: vi.fn(),
    renderTemplate: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

describe('CrossProtocolSessionBusPanel.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('initializes session bus on mount and loads variables table', async () => {
    vi.mocked(sessionBusApi.initBus).mockResolvedValue({
      bus_id: 'bus_cross_demo_01',
      message: '总线初始化成功',
    })
    vi.mocked(sessionBusApi.getVars).mockResolvedValue({
      bus_id: 'bus_cross_demo_01',
      variables: mockVars,
    })

    const wrapper = mount(CrossProtocolSessionBusPanel, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.key" class="row">
                  <slot name="bodyCell" :column="{ key: 'key' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'value' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'type' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
        },
      },
    })

    await flushPromises()

    expect(sessionBusApi.initBus).toHaveBeenCalledWith('bus_cross_demo_01')
    expect(wrapper.text()).toContain('跨协议数据透传与会话上下文共享总线')
    expect(wrapper.text()).toContain('HTTP ⇄ gRPC ⇄ WS 全局共享树')

    // 验证变量渲染
    expect(wrapper.text()).toContain('user_token')
    expect(wrapper.text()).toContain('jwt_mock_token_abc')
    expect(wrapper.text()).toContain('ORD-20261016-001')
  })

  it('triggers context propagation and displays generated protocol metadata', async () => {
    vi.mocked(sessionBusApi.initBus).mockResolvedValue({
      bus_id: 'bus_cross_demo_01',
      message: '总线初始化成功',
    })
    vi.mocked(sessionBusApi.getVars).mockResolvedValue({
      bus_id: 'bus_cross_demo_01',
      variables: mockVars,
    })
    vi.mocked(sessionBusApi.propagateContext).mockResolvedValue(mockPropagateGrpcResult)

    const wrapper = mount(CrossProtocolSessionBusPanel, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    const propagateBtn = wrapper.findAll('button').find((b) => b.text().includes('执行上下文透传'))
    expect(propagateBtn).toBeDefined()
    await propagateBtn!.trigger('click')
    await flushPromises()

    expect(sessionBusApi.propagateContext).toHaveBeenCalledWith('bus_cross_demo_01', 'http_to_grpc')
    expect(wrapper.text()).toContain('透传生成的目标协议凭据上下文')
    expect(wrapper.text()).toContain('authorization')
    expect(wrapper.text()).toContain('x-trace-id')
  })

  it('triggers dynamic template interpolation and displays rendered payload preview', async () => {
    vi.mocked(sessionBusApi.initBus).mockResolvedValue({
      bus_id: 'bus_cross_demo_01',
      message: '总线初始化成功',
    })
    vi.mocked(sessionBusApi.getVars).mockResolvedValue({
      bus_id: 'bus_cross_demo_01',
      variables: mockVars,
    })
    vi.mocked(sessionBusApi.renderTemplate).mockResolvedValue(mockRenderResult)

    const wrapper = mount(CrossProtocolSessionBusPanel, {
      global: {
        stubs: {
          'a-card': { template: '<div class="ant-card"><slot name="title" /><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-textarea': { template: '<textarea />' },
          'a-radio-group': { template: '<div><slot /></div>' },
          'a-radio-button': { template: '<button><slot /></button>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-row': { template: '<div class="ant-row"><slot /></div>' },
          'a-col': { template: '<div class="ant-col"><slot /></div>' },
          'a-table': { template: '<div class="ant-table" />' },
        },
      },
    })

    await flushPromises()

    const renderBtn = wrapper.findAll('button').find((b) => b.text().includes('执行插值渲染'))
    expect(renderBtn).toBeDefined()
    await renderBtn!.trigger('click')
    await flushPromises()

    expect(sessionBusApi.renderTemplate).toHaveBeenCalledWith('bus_cross_demo_01', expect.any(Object))
    expect(wrapper.text()).toContain('插值完成的实际有效载荷')
    expect(wrapper.text()).toContain('/api/v1/checkout/ORD-20261016-001')
  })
})
