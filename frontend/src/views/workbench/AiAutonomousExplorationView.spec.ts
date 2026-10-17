import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AiAutonomousExplorationView from './AiAutonomousExplorationView.vue'
import { intentWorkflowApi } from '@/api/intentWorkflow'

const mockSessions = [
  {
    session_id: 'expsess_ios_real_01',
    platform: 'ios' as const,
    device_id: '00008101-IPHONE-REAL',
    goal: '探索电商 iOS 客户端首页推荐与加购流程',
    status: 'ACTIVE' as const,
    states_count: 5,
    transitions_count: 4,
    states: [],
    transitions: [],
    current_state_id: 'st_01',
    step_count: 4,
    max_steps: 25,
    started_at: '2026-10-17 12:00:00',
  },
  {
    session_id: 'expsess_web_02',
    platform: 'web' as const,
    device_id: 'chrome_headless_grid',
    goal: '遍历运营管理后台权限审批与组织架构',
    status: 'COMPLETED' as const,
    states_count: 12,
    transitions_count: 11,
    states: [],
    transitions: [],
    current_state_id: 'st_12',
    step_count: 11,
    max_steps: 20,
    started_at: '2026-10-17 11:30:00',
  },
]

const mockIntents = [
  {
    synthesis_id: 'syn_order_checkout_01',
    workflow_id: 'wf_order_checkout',
    workflow_name: '电商端到端综合履约与对账工作流',
    semantic_summary: '由业务意图一键推导',
    nodes: [
      { node_id: 'n1', node_name: 'HTTP 创建订单', node_type: 'http' },
      { node_id: 'n2', node_name: 'iOS 真机加购', node_type: 'mobile_ios' },
    ],
    edges: [{ edge_id: 'e1', source_node_id: 'n1', target_node_id: 'n2' }],
    variable_bindings: { n2: '{{n1.output.body.order_id}}' },
    slots: {
      raw_prompt: '接口创建订单后在 iOS 支付并在数据库对账',
      business_domain: 'ecommerce',
      protocols: ['HTTP', 'iOS', 'SQL'],
      actions: ['create', 'pay', 'verify'],
      extracted_entities: ['order_id'],
      suggested_node_count: 3,
      analyzed_at: '2026-10-17 12:00:00',
    },
    created_at: '2026-10-17 12:00:00',
  },
]

const stubs = {
  'a-button': { template: '<button type="button" @click="$emit(\'click\')"><slot /></button>' },
  'a-card': { template: '<div class="ant-card"><slot /></div>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-space': { template: '<div class="ant-space"><slot /></div>' },
  'a-tabs': { template: '<div class="ant-tabs"><slot /></div>' },
  'a-tab-pane': { template: '<div class="ant-tab-pane"><slot /></div>' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-input-search': {
    template: '<input class="ant-input-search" :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'a-modal': {
    template: '<div v-if="open" class="ant-modal"><slot /><button class="modal-ok-btn" @click="$emit(\'ok\')">确定</button></div>',
    props: ['open'],
  },
  'a-form': { template: '<form><slot /></form>' },
  'a-form-item': { template: '<div><slot /></div>' },
  'a-radio-group': { template: '<div><slot /></div>' },
  'a-radio-button': { template: '<button><slot /></button>' },
  'a-input': {
    template: '<input :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'a-textarea': {
    template: '<textarea :value="value" @input="$emit(\'update:value\', $event.target.value)" />',
    props: ['value'],
  },
  'a-input-number': {
    template: '<input type="number" :value="value" @input="$emit(\'update:value\', Number($event.target.value))" />',
    props: ['value'],
  },
  'a-table': {
    template: `
      <div class="ant-table">
        <div v-for="item in dataSource" :key="item.session_id || item.synthesis_id" class="table-row">
          <span>{{ item.session_id || item.synthesis_id }}</span>
          <span>{{ item.goal || item.workflow_name }}</span>
          <button class="action-btn" @click="$parent.$emit('action', item)">操作</button>
        </div>
      </div>
    `,
    props: ['dataSource', 'columns'],
  },
  IntentWorkflowGenerateModal: {
    template: '<div v-if="open" class="intent-workflow-generate-modal-stub" />',
    props: ['open'],
  },
  AutonomousExplorationDashboardDrawer: {
    template: '<div v-if="open" class="autonomous-exploration-dashboard-drawer-stub" />',
    props: ['open', 'sessionId'],
  },
}

describe('AiAutonomousExplorationView.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(intentWorkflowApi, 'listExplorationSessions').mockResolvedValue({
      total: 2,
      sessions: mockSessions as any,
    })
    vi.spyOn(intentWorkflowApi, 'listHistory').mockResolvedValue({
      total: 1,
      history: mockIntents as any,
    })
  })

  function createWrapper() {
    return mount(AiAutonomousExplorationView, {
      global: { stubs },
    })
  }

  it('renders workbench title and 4 Bento KPI cards', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('AI 智能意图驱动多端测试生成与多模态 VLM 自主探索中台')
    expect(wrapper.text()).toContain('意图工作流推导成功率')
    expect(wrapper.text()).toContain('99.2%')
    expect(wrapper.text()).toContain('多模态探索覆盖状态总数')
    expect(wrapper.text()).toContain('探索轨迹逆向工作流转化率')
    expect(wrapper.text()).toContain('94.8%')
    expect(wrapper.text()).toContain('探索中捕获异常缺陷数')
  })

  it('loads sessions and intent history into tables on mount', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    expect(intentWorkflowApi.listExplorationSessions).toHaveBeenCalled()
    expect(intentWorkflowApi.listHistory).toHaveBeenCalled()

    expect(wrapper.text()).toContain('expsess_ios_real_01')
    expect(wrapper.text()).toContain('探索电商 iOS 客户端首页推荐与加购流程')
  })

  it('opens IntentWorkflowGenerateModal when clicking 自然语言意图生成工作流', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const intentBtn = wrapper.findAll('header button').find((b) => b.text().includes('自然语言意图生成工作流'))
    expect(intentBtn).toBeDefined()
    await intentBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.intent-workflow-generate-modal-stub').exists()).toBe(true)
  })

  it('opens AutonomousExplorationDashboardDrawer when clicking action on a session', async () => {
    const wrapper = createWrapper()
    await flushPromises()

    const vm = wrapper.vm as any
    vm.openExplorationDrawer('expsess_ios_real_01')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.autonomous-exploration-dashboard-drawer-stub').exists()).toBe(true)
    expect(vm.selectedSessionId).toBe('expsess_ios_real_01')
  })

  it('opens start session modal and starts a new exploration session', async () => {
    vi.spyOn(intentWorkflowApi, 'startExploration').mockResolvedValue({
      message: '启动成功',
      session: {
        session_id: 'expsess_new_01',
        platform: 'ios',
        device_id: '00008101-IPHONE-REAL-DEMO',
        goal: '探索电商首页、分类导航与结算流程',
        status: 'ACTIVE',
        states_count: 1,
        transitions_count: 0,
        states: [],
        transitions: [],
        current_state_id: 's1',
        step_count: 0,
        max_steps: 25,
        started_at: '2026-10-17 12:00:00',
      },
    })

    const wrapper = createWrapper()
    await flushPromises()

    const startBtn = wrapper.findAll('header button').find((b) => b.text().includes('启动 VLM 自主探索'))
    expect(startBtn).toBeDefined()
    await startBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.ant-modal').exists()).toBe(true)

    // 点击确定提交
    const okBtn = wrapper.find('.modal-ok-btn')
    expect(okBtn.exists()).toBe(true)
    await okBtn.trigger('click')
    await flushPromises()

    expect(intentWorkflowApi.startExploration).toHaveBeenCalledWith(
      expect.objectContaining({
        platform: 'ios',
        device_id: '00008101-IPHONE-REAL-DEMO',
      })
    )
  })
})
