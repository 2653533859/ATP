import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import dayjs from 'dayjs'

import HermesAssistantView from './HermesAssistantView.vue'

const {
  caseList,
  createDraft,
  createSession,
  confirmDraft,
  failureTop,
  generateDiagnosis,
  governance,
  hermesQuery,
  orchestrate,
  moduleList,
  projectList,
  reportOverview,
  routerPush,
  routerReplace,
  sessions,
  taskList,
  workbenchFailureDiagnosis,
} = vi.hoisted(() => ({
  caseList: vi.fn(),
  createDraft: vi.fn(),
  createSession: vi.fn(),
  confirmDraft: vi.fn(),
  failureTop: vi.fn(),
  generateDiagnosis: vi.fn(),
  governance: vi.fn(),
  hermesQuery: vi.fn(),
  orchestrate: vi.fn(),
  moduleList: vi.fn(),
  projectList: vi.fn(),
  reportOverview: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  sessions: vi.fn(),
  taskList: vi.fn(),
  workbenchFailureDiagnosis: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { project_id: '1' } }),
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    locale: ref('zh-CN'),
    t: (key: string, params?: { version?: string }) =>
      key === 'hermes.governance_eval_set' ? `${key}:${params?.version || ''}` : key,
  }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  Modal: { confirm: vi.fn() },
}))
vi.mock('@/api', () => ({
  caseApi: { list: caseList },
  hermesApi: { query: hermesQuery, createSession, createDraft, confirmDraft, governance, orchestrate, sessions },
  projectApi: { list: projectList, getModules: moduleList },
  reportApi: { overview: reportOverview },
  runApi: { generateFailureDiagnosis: generateDiagnosis },
  statisticsApi: { failureTop },
  workbenchApi: { tasks: taskList, failureDiagnosis: workbenchFailureDiagnosis },
}))
vi.mock('@ant-design/icons-vue', () => {
  const iconStub = { setup: () => () => null }
  return {
    ArrowRightOutlined: iconStub,
    BulbOutlined: iconStub,
    CheckCircleOutlined: iconStub,
    CloseOutlined: iconStub,
    ExclamationCircleOutlined: iconStub,
    PlusOutlined: iconStub,
    ReloadOutlined: iconStub,
    RobotOutlined: iconStub,
  }
})

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const globalStubs = Object.fromEntries(
  ['AAlert', 'AButton', 'AEmpty', 'ARangePicker', 'ASelect', 'ATag'].map((name) => [name, passthrough]),
)

const failedCase = {
  id: 'case:5',
  task_type: 'case',
  run_id: 77,
  source_id: 5,
  project_id: 1,
  name: '登录失败',
  status: 'failed',
  created_at: '2026-08-24T10:00:00Z',
  detail_path: '/runs/77',
  can_retry: true,
  can_stop: false,
  metadata: {},
  error_message: 'status 500',
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue([{ id: 1, name: '核心项目', owner_id: 1, current_user_role: 'owner', ai_llm_config_id: 9 }])
  moduleList.mockResolvedValue([{ id: 10, name: '登录', project_id: 1, parent_id: null, sort_order: 0, created_at: '', children: [] }])
  caseList.mockResolvedValue([{ id: 5, name: '登录失败', automation_status: 'auto' }])
  taskList.mockResolvedValue({ items: [failedCase], total: 1, has_more: false })
  reportOverview.mockResolvedValue({
    project_id: 1,
    days: 30,
    total_cases: 12,
    executed_cases: 10,
    coverage_rate: 83,
    total_runs: 20,
    passed_runs: 17,
    failed_runs: 2,
    error_runs: 1,
    pass_rate: 85,
    avg_duration_ms: 320,
    open_defects: 2,
    defect_health_rate: 75,
    quality_score: 78,
    trend: [],
    recent_runs: [],
  })
  failureTop.mockResolvedValue([{ case_name: '登录失败', failure_count: 3 }])
  generateDiagnosis.mockResolvedValue({
    status: 'done',
    source: 'rule',
    summary: '服务返回 500',
    at: '2026-08-24T10:00:00Z',
    failed_step_count: 1,
    screenshot_count: 0,
    repair_suggestions: [{ step_index: 0, step_name: '请求登录接口', suggestion_type: 'update_request', target: 'status', suggested_change: '检查服务状态', evidence: 'HTTP 500', confidence: 0.9 }],
    error_samples: [],
  })
  workbenchFailureDiagnosis.mockResolvedValue({
    status: 'done',
    source: 'rule',
    summary: 'Android 设备前置操作失败',
    at: '2026-08-24T10:00:00Z',
    failed_step_count: 1,
    screenshot_count: 0,
    repair_suggestions: [],
    error_samples: [],
  })
  hermesQuery.mockResolvedValue({
    project_id: 1,
    query: '登录排查',
    conversation_id: 'hermes-session-1',
    history_used: 0,
    history_omitted: 0,
    context_chars: 0,
    context_budget: 6000,
    source_types: [],
    updated_from: null,
    updated_to: null,
    mode: 'project_retrieval',
    answer: '找到相关来源',
    sources: [{
      source_type: 'knowledge',
      source_id: 2,
      project_id: 1,
      title: '登录排查手册',
      excerpt: '先检查认证服务',
      source_ref: 'SOP-LOGIN',
      path: '/knowledge?project_id=1&knowledge_id=2',
      match_terms: ['登录'],
      match_score: 20,
      updated_at: '2026-08-25T10:00:00Z',
    }],
    generated_at: '2026-08-25T10:00:00Z',
  })
  createSession.mockResolvedValue({ id: 101 })
  sessions.mockResolvedValue([])
  createDraft.mockResolvedValue({ id: 'draft-1', status: 'pending_confirmation' })
  confirmDraft.mockResolvedValue({ draft_id: 'draft-1', status: 'confirmed', plan_id: 22 })
  governance.mockResolvedValue({
    prompt_version: 'hermes-v2',
    prompt_versions: ['hermes-v2'],
    evaluation_set: { id: 'hermes-core-v1', version: '2026-09-01', size: 5 },
    sessions: 2,
    assistant_messages: 3,
    citation_coverage: 0.8,
    refusal_rate: 0.2,
    no_result_rate: 0.2,
    helpful_count: 2,
    not_helpful_count: 1,
    feedback_total: 3,
    helpful_rate: 0.6667,
    average_latency_ms: 120,
    p95_latency_ms: 220,
    cost_tracking: { available: false, reason: 'not configured' },
  })
  orchestrate.mockResolvedValue({
    project_id: 1,
    conversation_id: 'hermes-session-1',
    query: '失败任务和质量趋势',
    status: 'matched',
    plans: [
      { tool: 'failed_tasks', arguments: { limit: 20 }, reason: '失败任务' },
      { tool: 'quality_trend', arguments: { days: 30, aggregate: 'daily' }, reason: '质量趋势' },
    ],
    steps: [
      {
        tool: 'failed_tasks',
        arguments: { limit: 20 },
        status: 'ok',
        duration_ms: 4,
        data: { count: 1 },
        evidence: [{ evidence_id: 'failed', source_ref: 'HERMES-TASK-1', title: '失败任务', excerpt: '脱敏', path: '/tasks/1' }],
      },
      {
        tool: 'quality_trend',
        arguments: { days: 30, aggregate: 'daily' },
        status: 'ok',
        duration_ms: 5,
        data: { items: [{ rate: 91 }] },
        evidence: [{ evidence_id: 'quality', source_ref: 'HERMES-QUALITY-DAILY-30', title: '质量趋势', excerpt: '脱敏', path: '/quality' }],
      },
    ],
    answer: '已根据你的问题自动读取：失败任务工具返回 1 条结果。质量趋势返回 1 个时间段，最近通过率为 91%。',
    generated_at: '2026-09-03T10:00:00Z',
    session_id: 101,
    message_index: 1,
  })
  routerReplace.mockResolvedValue(undefined)
})

function mountHermes() {
  return mount(HermesAssistantView, { global: { stubs: globalStubs } })
}

describe('HermesAssistantView', () => {
  it('loads project evidence and keeps the source APIs project-scoped', async () => {
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(projectList).toHaveBeenCalledOnce()
    expect(moduleList).toHaveBeenCalledWith(1)
    expect(caseList).toHaveBeenCalledWith({ project_id: 1 })
    expect(taskList).toHaveBeenCalledWith({ project_id: 1, limit: 100 })
    expect(reportOverview).toHaveBeenCalledWith({ project_id: 1, days: 30, recent_limit: 20 })
    expect(failureTop).toHaveBeenCalledWith({ project_id: 1, days: 30, top: 8 })
    expect(governance).toHaveBeenCalledWith(1)
    expect(wrapper.find('.governance-card').exists()).toBe(true)
    expect(wrapper.find('.governance-card').text()).toContain('80%')
    expect(wrapper.find('.governance-card').text()).toContain('2026-09-01')
    expect(vm.qualityScore).toBe(78)
    expect(vm.failedTasks).toHaveLength(1)
    expect(vm.messages[0].sources).toHaveLength(2)

    wrapper.unmount()
  })

  it('answers failed-task and quality prompts from loaded evidence', async () => {
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.askPrompt('failed_tasks')
    expect(vm.messages.at(-1).taskIds).toEqual(['case:5'])
    await vm.askPrompt('quality')
    expect(vm.messages.at(-1).text).toContain('hermes.answers.quality')
    expect(generateDiagnosis).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('sends free-form questions to project retrieval and keeps source links', async () => {
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.queryHermes('登录排查')

    expect(hermesQuery).toHaveBeenCalledWith({
      project_id: 1,
      query: '登录排查',
      limit: 8,
      conversation_id: expect.stringMatching(/^hermes-1-/),
      history: [],
      source_types: [],
      updated_from: undefined,
      updated_to: undefined,
      context_budget: 6000,
    })
    expect(vm.messages.at(-1).text).toBe('找到相关来源')
    expect(vm.messages.at(-1).sources[0].path).toBe('/knowledge?project_id=1&knowledge_id=2')
    expect(vm.querying).toBe(false)

    wrapper.unmount()
  })

  it('automatically orchestrates bounded read tools for a combined free-form request', async () => {
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.inputText = '失败任务和质量趋势'
    await vm.submitPrompt()

    expect(orchestrate).toHaveBeenCalledWith({
      project_id: 1,
      query: '失败任务和质量趋势',
      conversation_id: expect.stringMatching(/^hermes-1-/),
      session_id: undefined,
    })
    expect(vm.sessionId).toBe(101)
    expect(vm.messages.at(-1).text).toContain('自动读取')
    expect(vm.messages.at(-1).toolSteps).toEqual([
      { tool: 'failed_tasks', status: 'ok' },
      { tool: 'quality_trend', status: 'ok' },
    ])
    expect(wrapper.find('.message-tool-chain').exists()).toBe(true)
    expect(hermesQuery).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('keeps a clarification session and completes the pending read-only intent on the next turn', async () => {
    orchestrate
      .mockResolvedValueOnce({
        project_id: 1,
        conversation_id: 'hermes-session-1',
        query: '查看 case 的运行详情',
        status: 'needs_input',
        clarification: '请提供运行编号，我再读取对应运行详情。',
        plans: [],
        steps: [],
        answer: '请提供运行编号，我再读取对应运行详情。',
        generated_at: '2026-09-03T10:00:00Z',
        session_id: 101,
        message_index: 1,
      })
      .mockResolvedValueOnce({
        project_id: 1,
        conversation_id: 'hermes-session-1',
        query: '12',
        status: 'matched',
        plans: [{ tool: 'run_detail', arguments: { task_type: 'case', run_id: 12 }, reason: '补全运行详情' }],
        steps: [{
          tool: 'run_detail',
          arguments: { task_type: 'case', run_id: 12 },
          status: 'ok',
          duration_ms: 4,
          data: { task: { id: 12 } },
          evidence: [],
        }],
        answer: '已读取运行记录的脱敏执行摘要。',
        generated_at: '2026-09-03T10:00:01Z',
        session_id: 101,
        message_index: 3,
      })
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.inputText = '查看 case 的运行详情'
    await vm.submitPrompt()
    expect(vm.sessionId).toBe(101)
    expect(vm.messages.at(-1).text).toContain('运行编号')
    expect(vm.messages.at(-1).backendIndex).toBeUndefined()

    vm.inputText = '12'
    await vm.submitPrompt()

    expect(orchestrate).toHaveBeenNthCalledWith(2, expect.objectContaining({
      project_id: 1,
      query: '12',
      session_id: 101,
    }))
    expect(vm.messages.at(-1).toolSteps).toEqual([{ tool: 'run_detail', status: 'ok' }])
    expect(hermesQuery).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('restores a pending clarification conversation without a feedback target', async () => {
    sessions.mockResolvedValueOnce([{
      id: 101,
      updated_at: '2026-09-03T10:00:00Z',
      context_filters: { conversation_id: 'hermes-pending-1' },
      messages: [{
        role: 'assistant',
        kind: 'orchestration_clarification',
        content: '请提供运行编号，我再读取对应运行详情。',
        at: '2026-09-03T10:00:00Z',
      }],
    }])
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.messages).toHaveLength(1)
    expect(vm.messages[0].backendIndex).toBeUndefined()
    expect(vm.conversationId).toBe('hermes-pending-1')

    vm.inputText = '12'
    await vm.submitPrompt()

    expect(orchestrate).toHaveBeenCalledWith(expect.objectContaining({
      conversation_id: 'hermes-pending-1',
      query: '12',
      session_id: 101,
    }))

    wrapper.unmount()
  })

  it('drops a stale restored session after switching projects', async () => {
    let resolveFirstSessions!: (value: unknown) => void
    projectList.mockResolvedValue([
      { id: 1, name: '核心项目', owner_id: 1, current_user_role: 'owner', ai_llm_config_id: 9 },
      { id: 2, name: '隔离项目', owner_id: 1, current_user_role: 'owner', ai_llm_config_id: 9 },
    ])
    sessions.mockImplementationOnce(() => new Promise((resolve) => { resolveFirstSessions = resolve }))
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(sessions).toHaveBeenCalledWith(1)
    await vm.handleProjectChange(2)
    resolveFirstSessions([{
      id: 101,
      updated_at: '2026-09-03T10:00:00Z',
      context_filters: { conversation_id: 'hermes-pending-1' },
      messages: [{
        role: 'assistant',
        kind: 'orchestration_clarification',
        content: '旧项目追问不应恢复。',
      }],
    }])
    await flushPromises()

    expect(vm.selectedProjectId).toBe(2)
    expect(vm.sessionId).toBeNull()
    expect(vm.conversationId).not.toBe('hermes-pending-1')
    expect(vm.messages.some((message: { text: string }) => message.text === '旧项目追问不应恢复。')).toBe(false)

    wrapper.unmount()
  })

  it('sends bounded conversation history and the selected evidence filters', async () => {
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.appendMessage('user', '上一轮问题')
    vm.sourceTypes = ['knowledge']
    vm.dateRange = [dayjs('2026-08-01'), dayjs('2026-08-31')]
    vm.contextBudget = 4000
    await vm.queryHermes('当前问题')

    expect(hermesQuery).toHaveBeenCalledWith(expect.objectContaining({
      query: '当前问题',
      history: [{ role: 'user', content: '上一轮问题' }],
      source_types: ['knowledge'],
      updated_from: '2026-08-01',
      updated_to: '2026-08-31',
      context_budget: 4000,
    }))
    expect(vm.historyUsed).toBe(0)
    expect(vm.contextChars).toBe(0)

    wrapper.unmount()
  })

  it('starts a new project-bound conversation without retaining old messages', async () => {
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any
    const previousId = vm.conversationId

    vm.sessionId = 42
    vm.appendMessage('user', '不要保留')
    vm.startNewConversation()

    expect(vm.conversationId).not.toBe(previousId)
    expect(vm.sessionId).toBeNull()
    expect(vm.messages).toHaveLength(1)
    expect(vm.messages[0].isWelcome).toBe(true)

    wrapper.unmount()
  })

  it('drops a stale response when a new conversation starts while querying', async () => {
    let resolveQuery!: (value: unknown) => void
    hermesQuery.mockImplementationOnce(() => new Promise((resolve) => { resolveQuery = resolve }))
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any
    const pending = vm.queryHermes('旧问题')

    await flushPromises()
    vm.startNewConversation()
    resolveQuery({
      project_id: 1,
      query: '旧问题',
      conversation_id: 'hermes-old-session',
      history_used: 0,
      history_omitted: 0,
      context_chars: 0,
      context_budget: 6000,
      source_types: [],
      updated_from: null,
      updated_to: null,
      mode: 'project_retrieval',
      answer: '旧回答不应出现',
      sources: [],
      generated_at: '2026-08-25T10:00:00Z',
    })
    await pending

    expect(vm.messages.some((message: { text: string }) => message.text === '旧回答不应出现')).toBe(false)
    expect(vm.conversationId).not.toBe('hermes-old-session')
    expect(vm.querying).toBe(false)

    wrapper.unmount()
  })

  it('drops a stale error when a new conversation starts while querying', async () => {
    let rejectQuery!: (reason?: unknown) => void
    hermesQuery.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectQuery = reject }))
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any
    const pending = vm.queryHermes('旧问题')

    await flushPromises()
    vm.startNewConversation()
    rejectQuery(new Error('旧会话失败'))
    await pending

    expect(vm.messages.some((message: { text: string }) => message.text.includes('旧会话失败'))).toBe(false)
    expect(vm.querying).toBe(false)

    wrapper.unmount()
  })

  it('does not fall back a stale orchestration error into a new conversation', async () => {
    let rejectOrchestration!: (reason?: unknown) => void
    orchestrate.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectOrchestration = reject }))
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any
    const pending = vm.orchestratePrompt('旧问题')

    await flushPromises()
    vm.startNewConversation()
    rejectOrchestration(new Error('旧编排失败'))
    await pending

    expect(hermesQuery).not.toHaveBeenCalled()
    expect(vm.messages.some((message: { text: string }) => message.text.includes('旧编排失败'))).toBe(false)
    expect(vm.querying).toBe(false)

    wrapper.unmount()
  })

  it('creates an editable structured test plan draft and links to plans after confirmation', async () => {
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.askPrompt('test_plan')
    expect(vm.planDraft.name).toContain('hermes.plan_default_name')
    expect(vm.planDraft.testPoints.length).toBe(2)
    expect(vm.planDraft.scopeModules).toHaveLength(1)
    expect(vm.planDraft.caseDrafts).toHaveLength(1)
    expect(vm.planDraft.regressionScope).toHaveLength(1)
    expect(vm.planDraft.sources).toHaveLength(4)
    expect(vm.draftChangedCount).toBe(0)
    vm.addPlanPoint()
    expect(vm.planDraft.testPoints).toHaveLength(3)
    expect(vm.draftChangedCount).toBe(1)
    vm.removePlanPoint(2)
    expect(vm.planDraft.testPoints).toHaveLength(2)
    expect(vm.draftChangedCount).toBe(0)
    vm.openPlans()
    expect(routerPush).not.toHaveBeenCalled()
    await vm.confirmPlanDraft()
    expect(vm.draftConfirmed).toBe(true)
    expect(routerPush).toHaveBeenCalledWith(expect.objectContaining({
      path: '/plans',
      query: { project_id: '1', hermes_draft: '1' },
      state: expect.objectContaining({
        hermesPlanDraft: expect.objectContaining({
          projectId: 1,
          name: vm.planDraft.name,
          caseIds: [5],
          moduleIds: [10],
          regressionTaskIds: ['case:5'],
        }),
      }),
    }))

    wrapper.unmount()
  })

  it('bootstraps a persistent session before saving a draft from a new conversation', async () => {
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.askPrompt('test_plan')
    await vm.savePlanDraft()

    expect(createSession).toHaveBeenCalledWith(1, 'hermes.conversation_title')
    expect(vm.sessionId).toBe(101)
    expect(createDraft).toHaveBeenCalledWith(101, expect.objectContaining({ project_id: 1, draft_type: 'test_plan' }))

    wrapper.unmount()
  })

  it('calls the existing case diagnosis chain and exposes the result source', async () => {
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.explainFailure(failedCase)
    expect(generateDiagnosis).toHaveBeenCalledWith(77)
    expect(vm.diagnosis.result.summary).toBe('服务返回 500')
    expect(vm.messages.at(-1).sources[0].path).toBe('/runs/77?project_id=1')
    expect(vm.diagnosing).toBe(false)

    wrapper.unmount()
  })

  it('uses the unified workbench diagnosis for Android failures', async () => {
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any
    const androidTask = { ...failedCase, id: 'android:8', task_type: 'android', run_id: 88, detail_path: '/mobile-special/reports/88' }

    await vm.explainFailure(androidTask)

    expect(workbenchFailureDiagnosis).toHaveBeenCalledWith('android', 88)
    expect(vm.diagnosis.result.summary).toBe('Android 设备前置操作失败')
    expect(vm.diagnosing).toBe(false)
    wrapper.unmount()
  })

  it('clears project evidence and conversation when the selection is removed', async () => {
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleProjectChange(null)
    expect(vm.selectedProjectId).toBeNull()
    expect(vm.failedTasks).toHaveLength(0)
    expect(vm.reportOverview).toBeNull()
    expect(vm.loading).toBe(false)

    wrapper.unmount()
  })
})
