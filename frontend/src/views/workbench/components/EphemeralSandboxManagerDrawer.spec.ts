import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import EphemeralSandboxManagerDrawer from './EphemeralSandboxManagerDrawer.vue'
import { sandboxesApi } from '@/api/sandboxes'

const mockSandboxes = [
  {
    sandbox_id: 'sbx_http_20005',
    session_name: '核心结算链路瞬时仿真沙箱',
    protocol: 'http' as const,
    host: '127.0.0.1',
    allocated_port: 20005,
    base_url: 'http://127.0.0.1:20005',
    status: 'ready' as const,
    ttl_seconds: 300,
    created_at: '2026-10-16T12:00:00Z',
    expires_at: '2026-10-16T12:05:00Z',
    is_expired: false,
    mock_rules_count: 1,
  },
  {
    sandbox_id: 'sbx_grpc_20006',
    session_name: '用户鉴权微服务 gRPC 沙箱',
    protocol: 'grpc' as const,
    host: '127.0.0.1',
    allocated_port: 20006,
    base_url: 'grpc://127.0.0.1:20006',
    status: 'expired' as const,
    ttl_seconds: 60,
    created_at: '2026-10-16T11:50:00Z',
    expires_at: '2026-10-16T11:51:00Z',
    is_expired: true,
    mock_rules_count: 0,
  },
]

vi.mock('@/api/sandboxes', () => ({
  sandboxesApi: {
    list: vi.fn(),
    provision: vi.fn(),
    terminate: vi.fn(),
    reapExpired: vi.fn(),
    mockDispatch: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}))

describe('EphemeralSandboxManagerDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer header, provisioning form, and sandbox waterline KPIs', async () => {
    vi.mocked(sandboxesApi.list).mockResolvedValue({
      total: mockSandboxes.length,
      sandboxes: mockSandboxes,
    })

    const wrapper = mount(EphemeralSandboxManagerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': {
            template: `
              <div class="ant-table">
                <div v-for="item in dataSource" :key="item.sandbox_id" class="row">
                  <slot name="bodyCell" :column="{ key: 'session_name' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'protocol' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'endpoint' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'status' }" :record="item" />
                  <slot name="bodyCell" :column="{ key: 'actions' }" :record="item" />
                </div>
              </div>
            `,
            props: ['dataSource'],
          },
          'a-modal': { template: '<div class="ant-modal"><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('瞬时轻量级多协议仿真沙箱与端口生命周期管理')
    expect(wrapper.text()).toContain('20000~29999 端口动态池')
    expect(wrapper.text()).toContain('活跃运行沙箱 (Active)')
    expect(wrapper.text()).toContain('端口占用总数 (Ports Allocated)')

    // 验证沙箱列表渲染
    expect(wrapper.text()).toContain('核心结算链路瞬时仿真沙箱')
    expect(wrapper.text()).toContain('端口 20005')
    expect(wrapper.text()).toContain('http://127.0.0.1:20005')
    expect(wrapper.text()).toContain('用户鉴权微服务 gRPC 沙箱')
  })

  it('triggers on-demand sandbox provisioning and refreshes list', async () => {
    vi.mocked(sandboxesApi.list).mockResolvedValue({
      total: 0,
      sandboxes: [],
    })
    vi.mocked(sandboxesApi.provision).mockResolvedValue({
      message: '沙箱拉起成功',
      sandbox: mockSandboxes[0],
    })

    const wrapper = mount(EphemeralSandboxManagerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table" />' },
          'a-modal': { template: '<div />' },
        },
      },
    })

    await flushPromises()

    const provisionBtn = wrapper.findAll('button').find((b) => b.text().includes('一键拉起沙箱'))
    expect(provisionBtn).toBeDefined()
    await provisionBtn!.trigger('click')
    await flushPromises()

    expect(sandboxesApi.provision).toHaveBeenCalledWith({
      session_name: expect.any(String),
      protocol: 'http',
      ttl_seconds: 300,
      mock_rules: expect.any(Array),
    })
    expect(sandboxesApi.list).toHaveBeenCalledTimes(2)
  })

  it('triggers reap expired sandboxes and displays notification', async () => {
    vi.mocked(sandboxesApi.list).mockResolvedValue({
      total: 1,
      sandboxes: [mockSandboxes[1]],
    })
    vi.mocked(sandboxesApi.reapExpired).mockResolvedValue({
      message: '过期收割完成',
      reaped_count: 1,
      reaped_sandbox_ids: ['sbx_grpc_20006'],
    })

    const wrapper = mount(EphemeralSandboxManagerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div><slot name="title" /><slot /></div>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-table': { template: '<div class="ant-table" />' },
          'a-modal': { template: '<div />' },
        },
      },
    })

    await flushPromises()

    const reapBtn = wrapper.findAll('button').find((b) => b.text().includes('过期自动收割 (Reap)'))
    expect(reapBtn).toBeDefined()
    await reapBtn!.trigger('click')
    await flushPromises()

    expect(sandboxesApi.reapExpired).toHaveBeenCalledTimes(1)
    expect(sandboxesApi.list).toHaveBeenCalledTimes(2)
  })
})
