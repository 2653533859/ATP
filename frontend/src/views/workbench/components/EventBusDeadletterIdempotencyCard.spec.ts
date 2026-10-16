import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import EventBusDeadletterIdempotencyCard from './EventBusDeadletterIdempotencyCard.vue'
import { eventBusGuardApi } from '@/api/distributedConsistency'

const mockIdempotencyReport = {
  idempotency_key: 'order_sku_9982',
  topic: 'order.events',
  consumer_group: 'order_consumer_group',
  total_deliveries: 3,
  state_mutations_count: 1,
  duplicate_suppressed_count: 2,
  is_idempotent: true,
  verdict_summary: '幂等性验证通过：共模拟重复投递 3 次，仅首次发生状态变更 (1 次)，后续 2 次被安全拦截！',
  verified_at: '2026-10-16T12:00:00Z',
}

const mockLagMetrics = [
  {
    topic: 'order.events',
    consumer_group: 'order_consumer_group',
    current_lag: 0,
    lag_severity: 'HEALTHY',
    avg_processing_time_ms: 18.5,
    oldest_unconsumed_age_sec: 0.0,
  },
]

const mockDeadLetters = [
  {
    message_id: 'msg_poison_101',
    topic: 'payment.notify',
    consumer_group: 'pay_handler',
    idempotency_key: 'pay_fail_99',
    payload: { pay_id: 'p_99' },
    status: 'DEAD_LETTER',
    retry_count: 3,
    max_retries: 3,
    lag_ms: 2500.0,
    error_message: 'DB deadlock timeout',
    produced_at: '2026-10-16T12:00:00Z',
    consumed_at: null,
  },
]

vi.mock('@/api/distributedConsistency', () => ({
  eventBusGuardApi: {
    produce: vi.fn(),
    consume: vi.fn(),
    verifyIdempotency: vi.fn(),
    getLag: vi.fn(),
    listDeadLetters: vi.fn(),
    requeueDeadLetter: vi.fn(),
    clearMessages: vi.fn(),
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
  MailOutlined: { template: '<span>Mail</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  ReloadOutlined: { template: '<span>Reload</span>' },
}))

describe('EventBusDeadletterIdempotencyCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(eventBusGuardApi.verifyIdempotency).mockResolvedValue({
      message: '幂等性压测完成',
      report: mockIdempotencyReport as any,
    })
    vi.mocked(eventBusGuardApi.getLag).mockResolvedValue({
      total: 1,
      metrics: mockLagMetrics as any,
    })
    vi.mocked(eventBusGuardApi.listDeadLetters).mockResolvedValue({
      total: 1,
      dead_letters: mockDeadLetters as any,
    })
    vi.mocked(eventBusGuardApi.requeueDeadLetter).mockResolvedValue({
      message: '死信已重新入队排队',
      message_id: 'msg_poison_101',
    })
  })

  it('renders header, idempotency test tab, and triggers test', async () => {
    const wrapper = mount(EventBusDeadletterIdempotencyCard, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div>Empty</div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(eventBusGuardApi.verifyIdempotency).toHaveBeenCalled()
    expect(wrapper.text()).toContain('消息事件总线死信积压、消费延迟与幂等防线引擎')

    // 检查幂等裁决横幅
    expect(wrapper.text()).toContain('幂等防线达标 (IDEMPOTENT)')
    expect(wrapper.text()).toContain('3 次')
    expect(wrapper.text()).toContain('1 次')
    expect(wrapper.text()).toContain('2 次')
  })

  it('requeues dead letter message', async () => {
    const wrapper = mount(EventBusDeadletterIdempotencyCard, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-input-number': { template: '<input type="number" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-tabs': { template: '<div><slot /></div>' },
          'a-tab-pane': { template: '<div><slot /></div>' },
          'a-empty': { template: '<div>Empty</div>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.handleRequeue('msg_poison_101')
    await flushPromises()

    expect(eventBusGuardApi.requeueDeadLetter).toHaveBeenCalledWith('msg_poison_101')
  })
})
