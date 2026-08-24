import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AIWorkbenchView from './AIWorkbenchView.vue'

const {
  aiFunnel,
  aiHealing,
  aiLLMList,
  caseList,
  datasetList,
  failureTop,
  mockList,
  moduleList,
  overview,
  projectList,
  routerPush,
  routerReplace,
  taskList,
  authRole,
  iconStub,
} = vi.hoisted(() => ({
  aiFunnel: vi.fn(),
  aiHealing: vi.fn(),
  aiLLMList: vi.fn(),
  caseList: vi.fn(),
  datasetList: vi.fn(),
  failureTop: vi.fn(),
  mockList: vi.fn(),
  moduleList: vi.fn(),
  overview: vi.fn(),
  projectList: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
  taskList: vi.fn(),
  authRole: { value: 'admin' },
  iconStub: { setup: () => () => null },
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
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: authRole.value } }),
}))
vi.mock('@/api', () => ({
  aiCaseGenerationApi: { getFunnelStats: aiFunnel },
  aiHealingStatsApi: { getStats: aiHealing },
  aiLLMConfigApi: { list: aiLLMList },
  caseApi: { list: caseList },
  datasetApi: { list: datasetList },
  mockRuleApi: { list: mockList },
  projectApi: { list: projectList, getModules: moduleList },
  statisticsApi: { overview, failureTop },
  workbenchApi: { tasks: taskList },
}))
vi.mock('@ant-design/icons-vue', () => ({
  AppstoreOutlined: iconStub,
  ArrowRightOutlined: iconStub,
  BranchesOutlined: iconStub,
  BulbOutlined: iconStub,
  CheckCircleOutlined: iconStub,
  DatabaseOutlined: iconStub,
  ExperimentOutlined: iconStub,
  FileSearchOutlined: iconStub,
  LockOutlined: iconStub,
  ReloadOutlined: iconStub,
  RobotOutlined: iconStub,
  SafetyCertificateOutlined: iconStub,
  SettingOutlined: iconStub,
  WarningOutlined: iconStub,
}))

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const globalStubs = Object.fromEntries(
  ['AAlert', 'AButton', 'AEmpty', 'ASelect', 'ATag'].map((name) => [name, passthrough]),
)

beforeEach(() => {
  vi.clearAllMocks()
  authRole.value = 'admin'
  projectList.mockResolvedValue([{ id: 1, name: '核心项目', owner_id: 1, current_user_role: 'owner', ai_llm_config_id: 9 }])
  moduleList.mockResolvedValue([{ id: 10, name: '登录', project_id: 1, parent_id: null, sort_order: 0, created_at: '', children: [] }])
  caseList.mockResolvedValue([{ id: 5, automation_status: 'manual' }, { id: 6, automation_status: 'auto' }])
  datasetList.mockResolvedValue([{ id: 3, name: '用户数据', project_id: 1, row_count: 10, schema_field_count: 2, format: 'json', storage_mode: 'database', validation_policy: 'soft', version: 1, created_at: '', updated_at: '' }])
  mockList.mockResolvedValue([{ id: 4, name: '用户 Mock', project_id: 1, method: 'GET', path: '/users', status_code: 200, response_headers: {}, response_body: '{}', match_conditions: {}, delay_ms: 0, is_enabled: true, render_template: false, record_requests: false, version: 1, recorded_samples: [], creator_id: 1, created_at: '', updated_at: '' }])
  overview.mockResolvedValue({ total_cases: 12, total_runs: 20, pass_rate: 85, recent_runs_7d: 4 })
  failureTop.mockResolvedValue([{ case_id: 5, project_id: 1, module_id: 10, case_name: '登录失败', case_type: 'api', failure_count: 3 }])
  taskList.mockResolvedValue({ items: [{ id: 'case:5', task_type: 'case', run_id: 77, source_id: 5, project_id: 1, name: '登录失败', status: 'failed', created_at: '2026-08-24T10:00:00Z', detail_path: '/runs/77', can_retry: true, can_stop: false, metadata: {}, error_message: 'status 500' }], total: 1, has_more: false })
  aiFunnel.mockResolvedValue({ generated_sessions: 5, generated_drafts: 8, saved_drafts: 3, failed_generations: 1, warning_count: 1, save_rate: 37.5, latest_event_at: null })
  aiHealing.mockResolvedValue({ total_feedback_count: 10, adopted_count: 6, rejected_count: 4, adopted_rate: 60, high_quality_example_count: 2, by_case_type: [], top_error_fingerprints: [], recent_trend: [], production_feedback: { regression_triggered_count: 0, regression_success_count: 0, regression_success_rate: 0, latest_feedback_aggregated_at: null } })
  aiLLMList.mockResolvedValue([{ id: 9, name: '主模型', provider: 'openai_compatible', endpoint: 'http://llm.test/v1', model_name: 'vision-model', default_params: {}, enabled: true, supports_vision: true, has_api_key: true, description: '', created_at: '', updated_at: '' }])
  routerReplace.mockResolvedValue(undefined)
})

function mountWorkbench() {
  return mount(AIWorkbenchView, { global: { stubs: globalStubs } })
}

describe('AIWorkbenchView', () => {
  it('loads project context, quality signals, AI funnel and healing feedback', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(projectList).toHaveBeenCalledOnce()
    expect(moduleList).toHaveBeenCalledWith(1)
    expect(datasetList).toHaveBeenCalledWith(1)
    expect(mockList).toHaveBeenCalledWith({ project_id: 1 })
    expect(caseList).toHaveBeenCalledWith({ project_id: 1 })
    expect(overview).toHaveBeenCalledWith({ project_id: 1, days: 30 })
    expect(failureTop).toHaveBeenCalledWith({ project_id: 1, days: 30, top: 8 })
    expect(taskList).toHaveBeenCalledWith({ project_id: 1, limit: 60 })
    expect(aiFunnel).toHaveBeenCalledWith({ project_id: 1, days: 30 })
    expect(vm.contextAssetCount).toBe(2)
    expect(vm.firstModuleId).toBe(10)
    expect(vm.coverageGapCount).toBe(1)
    expect(vm.passRate).toBe(85)
    expect(vm.modelState).toBe('ready')
    expect(vm.healingStats.adopted_rate).toBe(60)
    wrapper.unmount()
  })

  it('opens project-scoped generation flows without duplicating generation logic', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as any

    vm.openCaseGeneration()
    expect(routerPush).toHaveBeenCalledWith({ name: 'cases', query: { project_id: '1', module_id: '10', ai_generate: '1' } })
    vm.openDatasetGeneration()
    expect(routerPush).toHaveBeenCalledWith({ path: '/system/datasets', query: { project_id: '1' } })
    vm.openMockGeneration()
    expect(routerPush).toHaveBeenCalledWith({ path: '/mock-rules', query: { project_id: '1' } })
    wrapper.unmount()
  })

  it('clears project-scoped signals when the project is cleared', async () => {
    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as any

    await vm.handleProjectChange(null)

    expect(vm.selectedProjectId).toBeNull()
    expect(vm.datasets).toHaveLength(0)
    expect(vm.mockRules).toHaveLength(0)
    expect(vm.failureTop).toHaveLength(0)
    expect(vm.loading).toBe(false)
    wrapper.unmount()
  })

  it('keeps project signals available for viewers and skips admin-only APIs', async () => {
    authRole.value = 'viewer'
    projectList.mockResolvedValue([{ id: 1, name: '只读项目', owner_id: 1, current_user_role: 'viewer', ai_llm_config_id: 9 }])

    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.canModify).toBe(false)
    expect(vm.contextAssetCount).toBe(2)
    expect(aiFunnel).not.toHaveBeenCalled()
    expect(aiHealing).not.toHaveBeenCalled()
    expect(aiLLMList).not.toHaveBeenCalled()
    vm.openDatasetGeneration()
    expect(routerPush).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('blocks generation when the project has no AI model binding', async () => {
    projectList.mockResolvedValue([{ id: 1, name: '未配置项目', owner_id: 1, current_user_role: 'owner', ai_llm_config_id: null }])

    const wrapper = mountWorkbench()
    await flushPromises()
    const vm = wrapper.vm as any

    expect(vm.modelState).toBe('unconfigured')
    expect(vm.canGenerate).toBe(false)
    vm.openMockGeneration()
    expect(routerPush).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
