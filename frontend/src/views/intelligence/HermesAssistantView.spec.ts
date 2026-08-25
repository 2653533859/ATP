import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import HermesAssistantView from './HermesAssistantView.vue'

const {
  caseList,
  failureTop,
  generateDiagnosis,
  moduleList,
  projectList,
  reportOverview,
  routerPush,
  routerReplace,
  taskList,
  workbenchFailureDiagnosis,
} = vi.hoisted(() => ({
  caseList: vi.fn(),
  failureTop: vi.fn(),
  generateDiagnosis: vi.fn(),
  moduleList: vi.fn(),
  projectList: vi.fn(),
  reportOverview: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  taskList: vi.fn(),
  workbenchFailureDiagnosis: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { project_id: '1' } }),
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/api', () => ({
  caseApi: { list: caseList },
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
  ['AAlert', 'AButton', 'AEmpty', 'ASelect', 'ATag'].map((name) => [name, passthrough]),
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

  it('creates an editable, non-persisted test plan draft and links to plans', async () => {
    const wrapper = mountHermes()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.askPrompt('test_plan')
    expect(vm.planDraft.name).toContain('hermes.plan_default_name')
    expect(vm.planDraft.testPoints.length).toBe(2)
    vm.addPlanPoint()
    expect(vm.planDraft.testPoints).toHaveLength(3)
    vm.removePlanPoint(2)
    expect(vm.planDraft.testPoints).toHaveLength(2)
    vm.openPlans()
    expect(routerPush).toHaveBeenCalledWith('/plans?project_id=1')

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
