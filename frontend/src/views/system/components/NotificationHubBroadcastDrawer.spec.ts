import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import NotificationHubBroadcastDrawer from './NotificationHubBroadcastDrawer.vue'
import { notificationHubApi } from '@/api/notificationHub'

const mockStats = {
  total_dispatched_count: 24,
  overall_success_rate_pct: 95.83,
  channel_distribution: {
    wechat: 12,
    dingtalk: 8,
    feishu: 4,
  },
}

const mockAudits = [
  {
    delivery_id: 'deliv_wechat_001',
    channel: 'wechat',
    target_webhook_masked: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=******',
    priority: 'P2',
    success: true,
    attempts: 1,
    http_status: 200,
    response_message: '投递成功',
    dispatched_at: '2026-10-16T10:00:00Z',
    duration_ms: 42.5,
  },
]

vi.mock('@/api/notificationHub', () => ({
  notificationHubApi: {
    getStats: vi.fn(),
    listAudits: vi.fn(),
    broadcast: vi.fn(),
    dispatch: vi.fn(),
  },
}))

vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@ant-design/icons-vue', () => ({
  SendOutlined: { template: '<span>Send</span>' },
  PlusOutlined: { template: '<span>Plus</span>' },
}))

describe('NotificationHubBroadcastDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(notificationHubApi.getStats).mockResolvedValue(mockStats as any)
    vi.mocked(notificationHubApi.listAudits).mockResolvedValue({
      total: 1,
      records: mockAudits as any,
    })
    vi.mocked(notificationHubApi.broadcast).mockResolvedValue({
      message: '全渠道广播投递成功',
      total: 3,
      success_count: 3,
      records: mockAudits as any,
    })
  })

  it('renders drawer header, statistics cards, and live previews', async () => {
    const wrapper = mount(NotificationHubBroadcastDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-textarea': { template: '<textarea />' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
          'a-space': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    // 验证标题与统计指标
    expect(wrapper.text()).toContain('全渠道交互式告警通知中枢')
    expect(wrapper.text()).toContain('24')
    expect(wrapper.text()).toContain('95.8%')
    expect(wrapper.text()).toContain('12 次')

    // 验证卡片预览内容渲染
    expect(wrapper.text()).toContain('[ATP自动化测试通报] 核心链路用例全量回归完成')
    expect(wrapper.text()).toContain('98.5%')

    expect(notificationHubApi.getStats).toHaveBeenCalled()
    expect(notificationHubApi.listAudits).toHaveBeenCalled()
  })

  it('triggers broadcast to all configured targets', async () => {
    const wrapper = mount(NotificationHubBroadcastDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-card': { template: '<div class="ant-card"><slot /></div>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-switch': { template: '<input type="checkbox" />' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-textarea': { template: '<textarea />' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-form': { template: '<form><slot /></form>' },
          'a-form-item': { template: '<div><slot /></div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
          'a-space': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleBroadcast()

    expect(notificationHubApi.broadcast).toHaveBeenCalledWith(expect.objectContaining({
      targets: expect.any(Array),
      card: expect.objectContaining({
        title: expect.stringContaining('ATP'),
      }),
    }))
  })
})
