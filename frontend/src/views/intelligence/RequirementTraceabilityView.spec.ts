import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import RequirementTraceabilityView from './RequirementTraceabilityView.vue'

const {
  caseList,
  impact,
  linkCase,
  parse,
  projectList,
  requirementCreate,
  requirementGet,
  requirementList,
  routerReplace,
} = vi.hoisted(() => ({
  caseList: vi.fn(),
  impact: vi.fn(),
  linkCase: vi.fn(),
  parse: vi.fn(),
  projectList: vi.fn(),
  requirementCreate: vi.fn(),
  requirementGet: vi.fn(),
  requirementList: vi.fn(),
  routerReplace: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { project_id: '1' } }),
  useRouter: () => ({ replace: routerReplace, push: vi.fn() }),
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ locale: ref('zh-CN'), t: (key: string) => key }),
}))
vi.mock('ant-design-vue', () => ({
  message: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { role: 'admin' } }),
}))
vi.mock('@/api', () => ({
  caseApi: { list: caseList },
  projectApi: { list: projectList },
  requirementsApi: {
    list: requirementList,
    get: requirementGet,
    impact,
    parse,
    create: requirementCreate,
    linkCase,
    update: vi.fn(),
    delete: vi.fn(),
    unlinkCase: vi.fn(),
  },
}))
vi.mock('@ant-design/icons-vue', () => {
  const iconStub = { setup: () => () => null }
  return {
    AimOutlined: iconStub,
    ArrowRightOutlined: iconStub,
    CheckCircleOutlined: iconStub,
    DeleteOutlined: iconStub,
    EditOutlined: iconStub,
    FileSearchOutlined: iconStub,
    LinkOutlined: iconStub,
    PlusOutlined: iconStub,
    ReloadOutlined: iconStub,
  }
})

const passthrough = defineComponent({
  setup: (_props, { slots }) => () => h('div', slots.default?.()),
})

const globalStubs = Object.fromEntries(
  ['AAlert', 'AButton', 'ACheckbox', 'ACheckboxGroup', 'ADrawer', 'AEmpty', 'AForm', 'AFormItem', 'AInput', 'APopconfirm', 'AProgress', 'ASelect', 'ASpin', 'ATag', 'ATextarea']
    .map((name) => [name, passthrough]),
)

const requirement = {
  id: 1,
  project_id: 1,
  requirement_code: 'REQ-001-00001',
  title: '登录需求',
  description: '用户可以登录系统',
  status: 'draft',
  priority: 'P1',
  acceptance_criteria: [{ id: 'AC-1', text: '登录成功进入首页', priority: 'P2', status: 'draft' }],
  source: 'manual',
  version: 1,
  creator_id: 7,
  owner_id: null,
  linked_case_count: 1,
  covered_criterion_count: 1,
  coverage_rate: 100,
  created_at: '2026-08-24T10:00:00Z',
  updated_at: '2026-08-24T10:00:00Z',
}

const detail = {
  ...requirement,
  links: [{
    id: 5,
    requirement_id: 1,
    case_id: 9,
    case_name: '登录主流程',
    case_code: 'ATP-API-0009',
    case_type: 'api',
    case_status: 'draft',
    review_status: 'pending',
    module_id: 2,
    module_name: '账号',
    relation_type: 'covers',
    criterion_ids: ['AC-1'],
    note: null,
    created_by: 7,
    created_at: '2026-08-24T10:00:00Z',
  }],
}

function mountView() {
  return mount(RequirementTraceabilityView, { global: { stubs: globalStubs } })
}

beforeEach(() => {
  vi.clearAllMocks()
  projectList.mockResolvedValue([{ id: 1, name: '核心项目', owner_id: 1, current_user_role: 'owner' }])
  requirementList.mockResolvedValue({ items: [requirement], total: 1, page: 1, page_size: 50 })
  requirementGet.mockResolvedValue(detail)
  impact.mockResolvedValue({ requirement_id: 1, requirement_version: 1, criteria_total: 1, criteria_covered: 1, coverage_rate: 100, linked_case_count: 1, impact_level: 'low', uncovered_criteria: [], candidate_cases: [] })
  caseList.mockResolvedValue([{ id: 9, name: '登录主流程', case_code: 'ATP-API-0009', case_type: 'api', status: 'draft', priority: 'P1', case_level: 'core', review_status: 'pending', automation_status: 'auto', tags: [], module_id: 2, creator_id: 7, is_ready_for_execution: true, created_at: '', updated_at: '' }])
  routerReplace.mockResolvedValue(undefined)
})

describe('RequirementTraceabilityView', () => {
  it('loads requirements, impact, and cases within the selected project', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(requirementList).toHaveBeenCalledWith({ project_id: 1, status: undefined, keyword: undefined })
    expect(caseList).toHaveBeenCalledWith({ project_id: 1 })
    expect(requirementGet).toHaveBeenCalledWith(1)
    expect(impact).toHaveBeenCalledWith(1)
    expect((wrapper.vm as any).selectedRequirement.title).toBe('登录需求')
    expect((wrapper.vm as any).coveredCriterionIds.has('AC-1')).toBe(true)
    wrapper.unmount()
  })

  it('turns parser output into an editable draft before persistence', async () => {
    parse.mockResolvedValue({
      title: '订单支付',
      description: '用户支付订单',
      acceptance_criteria: [{ id: 'AC-1', text: '支付成功', priority: 'P2', status: 'draft' }],
      keywords: ['支付'],
      warnings: ['请人工确认'],
    })
    const wrapper = mountView()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.parseText = '订单支付\n- 支付成功'
    await vm.parseDraft()

    expect(parse).toHaveBeenCalledWith({ project_id: 1, text: '订单支付\n- 支付成功' })
    expect(vm.draft.title).toBe('订单支付')
    expect(vm.draft.acceptance_criteria[0].text).toBe('支付成功')
    wrapper.unmount()
  })

  it('persists an edited requirement with only non-empty criteria', async () => {
    requirementCreate.mockResolvedValue(detail)
    const wrapper = mountView()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.openCreate()
    vm.draft.title = '新的支付需求'
    vm.draft.description = '支付流程'
    vm.draft.acceptance_criteria = [
      { id: 'AC-1', text: '支付成功', priority: 'P2', status: 'draft' },
      { id: 'AC-2', text: ' ', priority: 'P2', status: 'draft' },
    ]
    await vm.saveRequirement()

    expect(requirementCreate).toHaveBeenCalledWith(expect.objectContaining({
      project_id: 1,
      title: '新的支付需求',
      acceptance_criteria: [{ id: 'AC-1', text: '支付成功', priority: 'P2', status: 'draft' }],
    }))
    wrapper.unmount()
  })
})
