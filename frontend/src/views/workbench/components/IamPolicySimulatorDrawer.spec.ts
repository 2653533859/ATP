import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import IamPolicySimulatorDrawer from './IamPolicySimulatorDrawer.vue'

const mockPolicies = [
  {
    rule_id: 'rule_admin_all_allow',
    effect: 'allow' as const,
    principals: ['role:admin', 'project:owner'],
    resources: ['*'],
    actions: ['*'],
    description: '系统管理员与项目拥有者拥有无限制完全操作权限',
    enabled: true,
  },
  {
    rule_id: 'rule_editor_core_ops_allow',
    effect: 'allow' as const,
    principals: ['role:engineer', 'project:editor'],
    resources: ['case:*', 'suite:*'],
    actions: ['read', 'create', 'modify'],
    description: '研发工程师与项目编辑者可读写核心资产',
    enabled: true,
  },
  {
    rule_id: 'rule_viewer_mutation_deny',
    effect: 'deny' as const,
    principals: ['role:tester', 'project:viewer'],
    resources: ['*'],
    actions: ['modify', 'delete'],
    description: '访客与普通测试人员严禁修改或删除项目资产',
    enabled: true,
  },
]

const mockAllowResult = {
  allowed: true,
  decision_reason: '策略允许 (Explicit Allow): 研发工程师与项目编辑者可读写核心资产',
  matched_rule: 'rule_editor_core_ops_allow',
  resource_kind: 'case',
  action: 'modify',
}

const mockDenyResult = {
  allowed: false,
  decision_reason: '策略显式拒绝 (Explicit Deny): 访客与普通测试人员严禁修改或删除项目资产',
  matched_rule: 'rule_viewer_mutation_deny',
  resource_kind: 'case',
  action: 'delete',
}

const mockIdorResult = {
  allowed: false,
  decision_reason: '跨项目隔离拦截: 请求项目 (10) 与目标资源所属项目 (20) 不符',
  matched_rule: 'anti_idor_cross_project_isolation',
  resource_kind: 'case',
  action: 'read',
}

const mockListPolicies = vi.fn().mockResolvedValue({ total: 3, policies: mockPolicies })
const mockEvaluatePolicy = vi.fn().mockImplementation((data: any) => {
  if (data.project_id === 10 && data.resource_project_id === 20) {
    return Promise.resolve(mockIdorResult)
  }
  if (data.action === 'delete') {
    return Promise.resolve(mockDenyResult)
  }
  return Promise.resolve(mockAllowResult)
})

vi.mock('@/api/iamPolicy', () => ({
  iamPolicyApi: {
    listPolicies: () => mockListPolicies(),
    evaluatePolicy: (data: unknown) => mockEvaluatePolicy(data),
    registerPolicy: vi.fn(),
  },
}))

const globalStubs = {
  'a-drawer': { template: '<div class="ant-drawer"><slot name="title" /><slot /></div>' },
  'a-card': { template: '<div class="ant-card"><h4>{{ $attrs.title }}</h4><slot /><slot name="extra" /></div>' },
  'a-button': { template: '<button class="ant-btn"><slot /></button>' },
  'a-tag': { template: '<span class="ant-tag"><slot /></span>' },
  'a-space': { template: '<div><slot /></div>' },
  'a-form': { template: '<form><slot /></form>' },
  'a-form-item': { template: '<div class="form-item"><slot /></div>' },
  'a-select': { template: '<select><slot /></select>' },
  'a-select-option': { template: '<option><slot /></option>' },
  'a-input-number': { template: '<input type="number" />' },
  'a-alert': { template: '<div class="ant-alert"><h5>{{ $attrs.message }}</h5><p>{{ $attrs.description }}</p></div>' },
  'a-empty': { template: '<div class="ant-empty">{{ $attrs.description }}</div>' },
  'a-row': { template: '<div class="ant-row"><slot /></div>' },
  'a-col': { template: '<div class="ant-col"><slot /></div>' },
  'a-table': {
    props: ['dataSource'],
    template: `
      <div class="ant-table">
        <div v-for="item in dataSource" :key="item.rule_id" class="table-row">
          <span>{{ item.rule_id }}</span>
          <span>{{ item.effect }}</span>
          <span>{{ item.description }}</span>
        </div>
      </div>
    `,
  },
}

describe('IamPolicySimulatorDrawer.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders drawer header, loads policies, and performs initial evaluation', async () => {
    const wrapper = mount(IamPolicySimulatorDrawer, {
      props: { open: true },
      global: { stubs: globalStubs },
    })
    await flushPromises()

    expect(mockListPolicies).toHaveBeenCalled()
    expect(mockEvaluatePolicy).toHaveBeenCalled()
    expect(wrapper.text()).toContain('细粒度资源操作 RBAC 策略模拟器与 Anti-IDOR 诊断')
    expect(wrapper.text()).toContain('策略允许 (Explicit Allow)')
    expect(wrapper.text()).toContain('rule_editor_core_ops_allow')
    expect(wrapper.text()).toContain('同项目边界安全')
  })

  it('evaluates cross-project IDOR attempt and displays Anti-IDOR isolation badge', async () => {
    const wrapper = mount(IamPolicySimulatorDrawer, {
      props: { open: true },
      global: { stubs: globalStubs },
    })
    await flushPromises()

    const idorBtn = wrapper.findAll('button').find((b) => b.text().includes('跨项目越权 (Anti-IDOR)'))
    expect(idorBtn).toBeDefined()
    await idorBtn!.trigger('click')
    await flushPromises()

    expect(mockEvaluatePolicy).toHaveBeenCalledWith(
      expect.objectContaining({
        project_id: 10,
        resource_project_id: 20,
      })
    )

    expect(wrapper.text()).toContain('跨项目隔离拦截')
    expect(wrapper.text()).toContain('拦截跨项目平行越权')
  })

  it('evaluates viewer mutation attempt and displays Explicit Deny alert', async () => {
    const wrapper = mount(IamPolicySimulatorDrawer, {
      props: { open: true },
      global: { stubs: globalStubs },
    })
    await flushPromises()

    const denyBtn = wrapper.findAll('button').find((b) => b.text().includes('测试员修改用例 (显式拒绝)'))
    expect(denyBtn).toBeDefined()
    await denyBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('策略显式拒绝 (Explicit Deny)')
    expect(wrapper.text()).toContain('rule_viewer_mutation_deny')
  })
})
