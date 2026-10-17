import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AutonomousExplorationDashboardDrawer from './AutonomousExplorationDashboardDrawer.vue'
import { intentWorkflowApi } from '@/api/intentWorkflow'

const mockSession = {
  session_id: 'expsess_ios_test_99',
  platform: 'ios' as const,
  device_id: '00008101-IPHONE-REAL',
  goal: '探索 iOS 电商 App 加购与结算',
  status: 'ACTIVE' as const,
  states_count: 2,
  transitions_count: 1,
  states: [
    {
      state_id: 'state_home',
      screen_name: '首页推荐视口',
      ui_signature: 'sig_home_123',
      elements: [
        {
          element_id: 'el_btn_login',
          element_type: 'button',
          label: '登录账号',
          bounding_box: [10, 20, 100, 40],
          center_coords: [55, 40] as [number, number],
          clickable: true,
          confidence: 0.98,
        },
      ],
      visit_count: 2,
      first_seen_at: '2026-10-17T12:00:00Z',
    },
    {
      state_id: 'state_checkout',
      screen_name: '订单结算中心',
      ui_signature: 'sig_checkout_456',
      elements: [
        {
          element_id: 'el_btn_pay',
          element_type: 'button',
          label: '立即支付',
          bounding_box: [20, 200, 300, 50],
          center_coords: [170, 225] as [number, number],
          clickable: true,
          confidence: 0.99,
        },
      ],
      visit_count: 1,
      first_seen_at: '2026-10-17T12:01:00Z',
    },
  ],
  transitions: [
    {
      transition_id: 'trans_01',
      from_state_id: 'state_home',
      to_state_id: 'state_checkout',
      action_type: 'TAP',
      target_element_label: '登录账号',
      performed_at: '2026-10-17T12:00:30Z',
    },
  ],
  current_state_id: 'state_checkout',
  step_count: 1,
  max_steps: 20,
  started_at: '2026-10-17T12:00:00Z',
}

const mockAnomalies = [
  {
    anomaly_id: 'anom_01',
    session_id: 'expsess_ios_test_99',
    anomaly_type: 'WHITE_SCREEN' as const,
    severity: 'CRITICAL' as const,
    state_id: 'state_home',
    title: '检测到界面疑似白屏或无控件响应',
    description: '视觉模型在当前屏幕视口内未能感知到任何可交互控件。',
    suggested_action: '检查前端 JS 控制台日志与渲染线程。',
    detected_at: '2026-10-17 12:00:35',
  },
]

const stubs = {
  'a-drawer': { template: '<div class="ant-drawer-stub"><slot /></div>' },
  'a-button': { template: '<button><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag-stub"><slot /></span>' },
  'a-space': { template: '<div class="ant-space-stub"><slot /></div>' },
  'a-tabs': { template: '<div class="ant-tabs-stub"><slot /></div>' },
  'a-tab-pane': { template: '<div class="ant-tab-pane-stub"><slot /></div>' },
  'a-table': {
    template: `
      <div class="ant-table-stub">
        <div v-for="item in dataSource" :key="item.element_id" class="table-row">
          <span>{{ item.element_id }}</span>
          <span>{{ item.label }}</span>
        </div>
      </div>
    `,
    props: ['dataSource', 'columns'],
  },
  'a-empty': { template: '<div class="ant-empty-stub" />' },
}

describe('AutonomousExplorationDashboardDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(intentWorkflowApi, 'getExploration').mockResolvedValue({
      session: mockSession as any,
    })
    vi.spyOn(intentWorkflowApi, 'listAnomalies').mockResolvedValue({
      total: 1,
      anomalies: mockAnomalies as any,
    })
  })

  it('renders session header, platform tag, and state/transition counters when open', async () => {
    const wrapper = mount(AutonomousExplorationDashboardDrawer, {
      props: {
        open: true,
        sessionId: 'expsess_ios_test_99',
      },
      global: { stubs },
    })
    await flushPromises()

    expect(intentWorkflowApi.getExploration).toHaveBeenCalledWith('expsess_ios_test_99')
    expect(wrapper.text()).toContain('expsess_ios_test_99')
    expect(wrapper.text()).toContain('IOS 端')
    expect(wrapper.text()).toContain('加购与结算')
  })

  it('renders state nodes and transitions in graph tab', async () => {
    const wrapper = mount(AutonomousExplorationDashboardDrawer, {
      props: {
        open: true,
        sessionId: 'expsess_ios_test_99',
      },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('首页推荐视口')
    expect(wrapper.text()).toContain('订单结算中心')
    expect(wrapper.text()).toContain('TAP')
    expect(wrapper.text()).toContain('登录账号')
  })

  it('renders detected anomalies and suggestions in anomalies tab', async () => {
    const wrapper = mount(AutonomousExplorationDashboardDrawer, {
      props: {
        open: true,
        sessionId: 'expsess_ios_test_99',
      },
      global: { stubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('检测到界面疑似白屏或无控件响应')
    expect(wrapper.text()).toContain('WHITE_SCREEN')
    expect(wrapper.text()).toContain('CRITICAL')
    expect(wrapper.text()).toContain('检查前端 JS 控制台日志')
  })

  it('triggers stepExploration API when clicking 单步推进探索', async () => {
    vi.spyOn(intentWorkflowApi, 'stepExploration').mockResolvedValue({
      message: '单步探索成功',
      action: {
        action_type: 'TAP',
        target_label: '确认支付',
      },
      anomaly: null,
      current_step: 2,
      states_count: 2,
    })

    const wrapper = mount(AutonomousExplorationDashboardDrawer, {
      props: {
        open: true,
        sessionId: 'expsess_ios_test_99',
      },
      global: { stubs },
    })
    await flushPromises()

    const stepBtn = wrapper.findAll('button').find((b) => b.text().includes('单步推进探索'))
    expect(stepBtn).toBeDefined()
    await stepBtn!.trigger('click')
    await flushPromises()

    expect(intentWorkflowApi.stepExploration).toHaveBeenCalledWith(
      expect.objectContaining({
        session_id: 'expsess_ios_test_99',
      })
    )
  })

  it('triggers convertExploration API and emits converted event', async () => {
    const mockDraft = {
      workflow_id: 'wf_from_exp_99',
      workflow_name: '工作流_探索 iOS 电商 App 加购与结算',
      nodes: [{ node_id: 'n1', node_type: 'mobile_ios' }],
      edges: [],
    }

    vi.spyOn(intentWorkflowApi, 'convertExploration').mockResolvedValue({
      message: '固化成功',
      workflow_draft: mockDraft,
    })

    const wrapper = mount(AutonomousExplorationDashboardDrawer, {
      props: {
        open: true,
        sessionId: 'expsess_ios_test_99',
      },
      global: { stubs },
    })
    await flushPromises()

    const convertBtn = wrapper.findAll('button').find((b) => b.text().includes('一键固化为工作流草稿'))
    expect(convertBtn).toBeDefined()
    await convertBtn!.trigger('click')
    await flushPromises()

    expect(intentWorkflowApi.convertExploration).toHaveBeenCalledWith({
      session_id: 'expsess_ios_test_99',
      workflow_name: expect.stringContaining('探索'),
    })
    expect(wrapper.emitted('converted')).toBeDefined()
    expect(wrapper.emitted('converted')![0][0]).toEqual(mockDraft)
  })
})
