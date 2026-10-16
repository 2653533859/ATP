import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DefectTicketDispatchCard from './DefectTicketDispatchCard.vue'
import { defectTicketDispatchApi } from '@/api/rootCauseDiagnosis'

const mockJiraTicket = {
  ticket_id: 'tkt_jira_101',
  title: '[CRITICAL] [pay-service] 支付扣款并发事务用例 自动化测试执行失败',
  severity: 'CRITICAL',
  platform: 'JIRA',
  case_id: 'case_pay_deadlock_101',
  case_name: '支付扣款并发事务用例',
  culprit_service: 'pay-service',
  assignee: 'FinancePay-OnCall',
  external_issue_id: 'ATP-JIRA-4891',
  description: '### 🚨 自动化测试失败缺陷工单: [CRITICAL] 支付扣款并发事务用例',
  status: 'DISPATCHED',
  labels: ['atp-auto-bug', 'severity-critical'],
  created_at: '2026-10-16T12:00:00Z',
}

const mockGhTicket = {
  ticket_id: 'tkt_gh_202',
  title: '[MAJOR] [order-service] 用户结账下单全流程 自动化测试执行失败',
  severity: 'MAJOR',
  platform: 'GITHUB_ISSUE',
  case_id: 'case_order_crash_202',
  case_name: '用户结账下单全流程',
  culprit_service: 'order-service',
  assignee: 'OrderTeam-DevLead',
  external_issue_id: 'GH#405',
  description: '### 🚨 自动化测试失败缺陷工单: [MAJOR] 用户结账下单全流程',
  status: 'DISPATCHED',
  labels: ['atp-auto-bug', 'severity-major'],
  created_at: '2026-10-16T12:05:00Z',
}

vi.mock('@/api/rootCauseDiagnosis', () => ({
  defectTicketDispatchApi: {
    dispatch: vi.fn(),
    listTickets: vi.fn(),
    getTicket: vi.fn(),
    updateStatus: vi.fn(),
    clearTickets: vi.fn(),
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
  ReloadOutlined: { template: '<span>Reload</span>' },
}))

describe('DefectTicketDispatchCard.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(defectTicketDispatchApi.dispatch).mockResolvedValue({
      message: '缺陷工单已自动创建并成功指派',
      ticket: mockJiraTicket as any,
    })
    vi.mocked(defectTicketDispatchApi.listTickets).mockResolvedValue({
      total: 1,
      tickets: [mockJiraTicket as any],
    })
    vi.mocked(defectTicketDispatchApi.updateStatus).mockResolvedValue({
      message: '工单已解决',
      ticket_id: 'tkt_jira_101',
      status: 'RESOLVED',
    })
  })

  it('renders header, ticket feedback banner, and tickets table', async () => {
    const wrapper = mount(DefectTicketDispatchCard, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': {
            props: ['dataSource'],
            template: `
              <div class="ant-table-stub">
                <div v-for="item in dataSource" :key="item.ticket_id" class="row">
                  <span class="ext-id">{{ item.external_issue_id }}</span>
                  <span class="sev">{{ item.severity }}</span>
                  <span class="status">{{ item.status }}</span>
                </div>
              </div>
            `,
          },
        },
      },
    })

    await flushPromises()

    // 检查调用与标题
    expect(defectTicketDispatchApi.dispatch).toHaveBeenCalled()
    expect(defectTicketDispatchApi.listTickets).toHaveBeenCalled()
    expect(wrapper.text()).toContain('缺陷严重度智能评级与第三方工单自动指派网关')

    // 检查工单反馈横幅
    expect(wrapper.text()).toContain('CRITICAL P0/P1')
    expect(wrapper.text()).toContain('ATP-JIRA-4891')
    expect(wrapper.text()).toContain('FinancePay-OnCall')

    // 检查表格项
    expect(wrapper.text()).toContain('全网自动化测试缺陷工单流转台账')
  })

  it('switches preset to major_gh and verifies resolve ticket', async () => {
    vi.mocked(defectTicketDispatchApi.dispatch).mockResolvedValueOnce({
      message: '建单成功',
      ticket: mockJiraTicket as any,
    }).mockResolvedValueOnce({
      message: '建单成功',
      ticket: mockGhTicket as any,
    })

    const wrapper = mount(DefectTicketDispatchCard, {
      global: {
        stubs: {
          'a-button': { template: '<button><slot /></button>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-input': { template: '<input />' },
          'a-select': { template: '<select><slot /></select>' },
          'a-select-option': { template: '<option><slot /></option>' },
          'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
          'a-table': { template: '<div class="ant-table-stub" />' },
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as any
    await vm.applyPreset('major_gh')
    await flushPromises()

    expect(defectTicketDispatchApi.dispatch).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('GH#405')

    // 标记已解决
    await vm.handleResolveTicket('tkt_jira_101')
    expect(defectTicketDispatchApi.updateStatus).toHaveBeenCalledWith('tkt_jira_101', 'RESOLVED')
  })
})
