import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AutonomousApiFuzzingExplorerDrawer from './AutonomousApiFuzzingExplorerDrawer.vue'
import { autonomousApiFuzzingApi } from '@/api/cloudNativeCluster'

const mockSession = {
  session_id: 'fuzz_orders_1001',
  target_endpoint: '/api/v1/orders/checkout',
  target_method: 'POST',
  total_mutations_count: 18,
  flaws_count: 2,
  critical_count: 1,
  high_count: 1,
  robustness_score_pct: 55.0,
  findings: [
    {
      flaw_id: 'flaw_crash_01',
      strategy: 'SQL_INJECTION_PROBE',
      flaw_type: 'UNHANDLED_SERVER_CRASH',
      severity: 'CRITICAL',
      mutated_key: 'notes',
      mutated_value: "'; DROP TABLE users; --",
      status_code: 500,
      response_excerpt: "InternalServerError: syntax error at or near 'DROP TABLE'",
      reproduction_curl: "curl -X POST '/api/v1/orders/checkout' -d '{\"notes\": \"DROP TABLE\"}'",
    },
    {
      flaw_id: 'flaw_dos_02',
      strategy: 'UNICODE_CONTROL_CHARS',
      flaw_type: 'PERFORMANCE_SPIKE_DOS',
      severity: 'HIGH',
      mutated_key: 'notes',
      mutated_value: '\\uffff\\ufeff',
      status_code: 200,
      response_excerpt: '请求耗时异常飙升 (3500ms)',
      reproduction_curl: "curl -X POST '/api/v1/orders/checkout' -d '{\"notes\": \"unicode\"}'",
    },
  ],
  created_at: '2026-10-17T12:00:00Z',
}

vi.mock('@/api/cloudNativeCluster', () => ({
  autonomousApiFuzzingApi: {
    run: vi.fn(),
    getStrategies: vi.fn(),
    listSessions: vi.fn(),
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
  BugOutlined: { template: '<span>Bug</span>' },
  ThunderboltOutlined: { template: '<span>Thunderbolt</span>' },
  CopyOutlined: { template: '<span>Copy</span>' },
}))

describe('AutonomousApiFuzzingExplorerDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(autonomousApiFuzzingApi.run).mockResolvedValue({
      message: '变异探索测试完成',
      session: mockSession as any,
    })
  })

  it('renders header, 4 KPI cards, flaw finding cards, and cURL commands', async () => {
    const wrapper = mount(AutonomousApiFuzzingExplorerDrawer, {
      props: {
        open: true,
      },
      global: {
        stubs: {
          'a-drawer': { template: '<div class="ant-drawer"><slot /></div>' },
          'a-button': { template: '<button><slot /></button>' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-row': { template: '<div><slot /></div>' },
          'a-col': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-checkbox-group': { template: '<div><slot /></div>' },
          'a-checkbox': { template: '<input type="checkbox" />' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-empty': { template: '<div><slot /></div>' },
        },
      },
    })

    await flushPromises()

    expect(autonomousApiFuzzingApi.run).toHaveBeenCalled()

    // 检查标题与 KPI
    expect(wrapper.text()).toContain('状态反馈驱动的 API 模糊变异与反向安全鲁棒性探查引擎')
    expect(wrapper.text()).toContain('18 次')
    expect(wrapper.text()).toContain('55%')
    expect(wrapper.text()).toContain('1 处')

    // 检查缺陷卡片
    expect(wrapper.text()).toContain('UNHANDLED_SERVER_CRASH')
    expect(wrapper.text()).toContain('HTTP 500')
    expect(wrapper.text()).toContain('notes')
    expect(wrapper.text()).toContain("curl -X POST '/api/v1/orders/checkout'")

    // 重新运行
    const vm = wrapper.vm as any
    await vm.handleRunFuzzing()
    await flushPromises()

    expect(autonomousApiFuzzingApi.run).toHaveBeenCalledTimes(2)
  })
})
